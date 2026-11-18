#!/usr/bin/env python3
"""Create a SEPARATE V2-B trainer from the user's frozen baseline.

Hotfix M7.6B-r2: match Python statements using AST rather than exact whitespace.
Never edits the baseline trainer, frozen protocol, labels, or data.
"""
from __future__ import annotations

import argparse
import ast
import difflib
import hashlib
import json
import re
from pathlib import Path


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _one(items, label: str):
    if len(items) != 1:
        raise ValueError(f'{label}: expected exactly one AST match; found {len(items)}. '
                         'STOP and inspect local trainer; do not force-patch frozen code.')
    return items[0]


def _is_attr(node, root, attr):
    return (isinstance(node, ast.Attribute) and node.attr == attr and
            isinstance(node.value, ast.Name) and node.value.id == root)


def _is_keyword(call, name, expected):
    return any(kw.arg == name and isinstance(kw.value, ast.Constant) and
               kw.value.value == expected for kw in call.keywords)


def _is_check_cli(node):
    if not isinstance(node, ast.Expr) or not isinstance(node.value, ast.Call):
        return False
    c = node.value
    return (_is_attr(c.func, 'p', 'add_argument') and
            c.args and isinstance(c.args[0], ast.Constant) and
            c.args[0].value == '--check-only' and
            _is_keyword(c, 'action', 'store_true'))


def _is_check_branch(node):
    return isinstance(node, ast.If) and _is_attr(node.test, 'a', 'check_only')


def _is_train_loader(node):
    if not isinstance(node, ast.Assign) or len(node.targets) != 1 or not (
            isinstance(node.targets[0], ast.Name) and node.targets[0].id == 'train'):
        return False
    call = node.value
    if not (isinstance(call, ast.Call) and isinstance(call.func, ast.Name) and
            call.func.id == 'DataLoader'):
        return False
    if not call.args or not (isinstance(call.args[0], ast.Call) and
                            isinstance(call.args[0].func, ast.Name) and
                            call.args[0].func.id == 'SarWaterDataset'):
        return False
    dataset = call.args[0]
    if not dataset.args or not (isinstance(dataset.args[0], ast.Name) and
                                dataset.args[0].id == 'train_recs'):
        return False
    return _is_keyword(call, 'shuffle', True) and not any(
        kw.arg == 'sampler' for kw in call.keywords)


def _is_corrected_iou(original: str, tree: ast.AST) -> bool:
    hits = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if not isinstance(target, ast.Subscript) or not (
                        isinstance(target.value, ast.Name) and target.value.id == 'totals'):
                    continue
                slc = target.slice
                if isinstance(slc, ast.Constant) and slc.value == 'iou':
                    hits.append(node.value)
    if len(hits) != 1:
        return False
    val = hits[0]
    return (isinstance(val, ast.IfExp) and isinstance(val.orelse, ast.Call) and
            isinstance(val.orelse.func, ast.Name) and val.orelse.func.id == 'float' and
            len(val.orelse.args) == 1 and isinstance(val.orelse.args[0], ast.Constant) and
            val.orelse.args[0].value == 'nan')


def _line_indent(line: str) -> str:
    return line[:len(line) - len(line.lstrip(' \t'))]


def make_derived(original: str) -> str:
    tree = ast.parse(original)
    if not _is_corrected_iou(original, tree):
        raise ValueError("Original trainer must use zero-union IoU = float('nan'); STOP.")
    main = _one([node for node in tree.body if isinstance(node, ast.FunctionDef) and
                 node.name == 'main'], 'main()')
    cli = _one([node for node in ast.walk(main) if _is_check_cli(node)],
               'check-only CLI')
    check = _one([node for node in ast.walk(main) if _is_check_branch(node)],
                 'check-only branch')
    train = _one([node for node in ast.walk(main) if _is_train_loader(node)],
                 'TRAIN DataLoader with shuffle=True')
    imp = _one([node for node in tree.body if isinstance(node, ast.ImportFrom) and
                node.module == 'torch.utils.data' and
                {'Dataset', 'DataLoader'}.issubset({item.name for item in node.names})],
               'torch.utils.data import')
    if not (cli.end_lineno < check.lineno < train.lineno):
        raise ValueError('Unexpected trainer structure: CLI, check-only, TRAIN order differs')

    lines = original.splitlines(keepends=True)
    start, end = train.lineno - 1, train.end_lineno
    existing = ''.join(lines[start:end])
    # Only change the named TRAIN loader; leave VALID/DataLoader and all other code intact.
    regex = r'\bshuffle\s*=\s*True\b'
    if len(re.findall(regex, existing)) != 1:
        raise ValueError('TRAIN DataLoader shuffle=True token not uniquely found')
    patched = re.sub(regex, 'sampler=v2b_sampler,shuffle=False', existing, count=1)
    if not patched.endswith('\n'):
        patched += '\n'
    indent = _line_indent(lines[start])
    sampler_build = (
        f'{indent}v2b_sampler=build_train_sampler(train_recs,a.data_root,a.output_dir,a.seed,\n'
        f'{indent}                                    project_root=Path(__file__).resolve().parent)\n'
    )
    smoke = (
        f'{indent}if a.v2b_sampler_smoke:\n'
        f'{indent}    if a.max_train or a.max_val:\n'
        f'{indent}        raise ValueError(\'Sampler smoke requires full TRAIN and VALID manifests: no --max-*\')\n'
        f'{indent}    sampler=build_train_sampler(train_recs,a.data_root,a.output_dir,a.seed,\n'
        f'{indent}                                project_root=Path(__file__).resolve().parent)\n'
        f'{indent}    loader=DataLoader(SarWaterDataset(train_recs,a.crop_size,True),\n'
        f'{indent}                      batch_size=a.batch_size,shuffle=False,\n'
        f'{indent}                      sampler=sampler,num_workers=0,pin_memory=False)\n'
        f'{indent}    x,y,v=next(iter(loader))\n'
        f'{indent}    assert x.shape[0] == a.batch_size and x.shape[1] == 2\n'
        f'{indent}    assert int(v.sum()) > 0 and bool(torch.isfinite(x).all())\n'
        f'{indent}    print(\'PASS: M7.6B REAL TRAIN weighted-sampler batch; shape=\',tuple(x.shape),\n'
        f'{indent}          \'valid=\',int(v.sum()),\'water=\',int((y.bool() & v.bool()).sum()))\n'
        f'{indent}    Path(a.output_dir).mkdir(parents=True,exist_ok=True)\n'
        f'{indent}    (Path(a.output_dir)/\'m76b_real_sampler_smoke.json\').write_text(json.dumps({{\n'
        f'{indent}        \'status\':\'PASS_REAL_TRAIN_BATCH_NO_OPTIMIZER\',\n'
        f'{indent}        \'fold\':a.data_root.resolve().name,\'seed\':a.seed,\n'
        f'{indent}        \'batch_shape\':list(x.shape),\'valid_pixels\':int(v.sum()),\n'
        f'{indent}        \'train_count\':len(train_recs),\'no_test_or_validation_metrics\':True}},\n'
        f'{indent}        indent=2)+\'\\n\',encoding=\'utf-8\')\n'
        f'{indent}    print(\'SMOKE ONLY: no model initialized/trained; no DEV metrics or TEST\')\n'
        f'{indent}    return\n'
    )
    cli_indent = _line_indent(lines[cli.lineno - 1])
    new_cli = (f"{cli_indent}p.add_argument('--v2b-sampler-smoke',action='store_true',\n"
               f"{cli_indent}               help='Sampler + real TRAIN DataLoader batch only; no training')\n")
    # Apply edits bottom-to-top so original AST line numbers remain valid.
    actions = [
        (imp.end_lineno, imp.end_lineno,
         'from m76b_water_sampler import build_train_sampler\n'),
        (cli.end_lineno, cli.end_lineno, new_cli),
        (check.lineno - 1, check.lineno - 1, smoke),
        (start, end, sampler_build + patched),
    ]
    for begin, finish, replacement in sorted(actions, reverse=True):
        lines[begin:finish] = [replacement]
    derived = ''.join(lines)
    compile(derived, 'train_v2b_coverage.py', 'exec')

    # Post-condition: model still has exactly one train and one valid loader.
    derived_tree = ast.parse(derived)
    if len([n for n in ast.walk(derived_tree) if isinstance(n, ast.ImportFrom) and
            n.module == 'm76b_water_sampler']) != 1:
        raise ValueError('Generated sampler import verification failed')
    if derived.count('build_train_sampler(') != 2:
        raise ValueError('Expected exactly two sampler calls (smoke + TRAIN)')
    if 'sampler=v2b_sampler,shuffle=False' not in derived:
        raise ValueError('Generated TRAIN DataLoader verification failed')
    return derived


def self_test():
    # Use real archived baseline structure with the corrected IoU rule, if possible;
    # otherwise a tiny fixture is used. Both whitespace variants must pass.
    demo = ("from torch.utils.data import Dataset, DataLoader\n"
            "def main():\n"
            "    p.add_argument('--check-only',action='store_true')\n"
            "    if a.check_only:\n"
            "        return\n"
            "    train=DataLoader(SarWaterDataset(train_recs,a.crop_size,True),batch_size=a.batch_size,\n"
            "                     shuffle=True,num_workers=0,pin_memory=False)\n"
            "    totals['iou']=tp / union if union else float('nan')\n")
    d1 = make_derived(demo)
    assert '--v2b-sampler-smoke' in d1 and 'sampler=v2b_sampler,shuffle=False' in d1
    spaced = (demo.replace("p.add_argument('--check-only',action='store_true')",
                           'p.add_argument( "--check-only", action = "store_true" )')
                  .replace('    train=DataLoader(', '    train = DataLoader(')
                  .replace('shuffle=True', 'shuffle = True')
                  .replace('    if a.check_only:', '    if (a.check_only):'))
    d2 = make_derived(spaced)
    assert '--v2b-sampler-smoke' in d2 and 'sampler=v2b_sampler,shuffle=False' in d2
    assert "else float('nan')" in d2
    try:
        make_derived(demo.replace("float('nan')", '1.0'))
        raise AssertionError('Unsafe union handling was accepted')
    except ValueError:
        pass
    print('PASS: M7.6B hotfix r2: AST-based CLI, branch, TRAIN loader; formatting variants')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--project-root', type=Path, default=Path('.'))
    p.add_argument('--source', default='train_sar_unet.py')
    p.add_argument('--target', default='train_v2b_coverage.py')
    p.add_argument('--self-test', action='store_true')
    a = p.parse_args()
    if a.self_test:
        self_test()
        return
    root = a.project_root.resolve()
    from m76b_water_sampler import check_frozen
    frozen = check_frozen(root)
    source = root / a.source
    target = root / a.target
    if source.resolve() == target.resolve():
        raise ValueError('Refusing to overwrite baseline trainer')
    if not source.is_file():
        raise FileNotFoundError(source)
    orig = source.read_text(encoding='utf-8')
    derived = make_derived(orig)
    if target.exists():
        if target.read_text(encoding='utf-8') != derived:
            raise FileExistsError(f'Target differs: {target}; refusing overwrite')
        print('PASS: existing V2-B trainer matches generated patch; no overwrite')
    else:
        target.write_text(derived, encoding='utf-8')
        print('Created separate V2-B trainer:', target)
    dest = root / 'results/event_level_v2/m76b_implementation_audit'
    dest.mkdir(parents=True, exist_ok=True)
    diff = ''.join(difflib.unified_diff(orig.splitlines(keepends=True),
                                       derived.splitlines(keepends=True),
                                       fromfile=a.source, tofile=a.target))
    (dest / 'm76b_baseline_to_v2b.patch').write_text(diff, encoding='utf-8')
    manifest = {
        'status': 'IMPLEMENTED_PENDING_REAL_SMOKE_AND_AUDIT',
        'generator_version': 'M7.6B-r2-AST',
        'design_fingerprint': frozen['design_fingerprint'],
        'source_trainer': a.source, 'source_trainer_sha256': sha256(source),
        'v2b_trainer': a.target, 'v2b_trainer_sha256': sha256(target),
        'only_training_treatment_changed': 'TRAIN image-index weighted sampling',
        'required_next_steps': ['M7.0D verify', 'M7.6A verify',
                                'M7.6B sampler --audit-all', 'M7.6B real --v2b-sampler-smoke'],
        'no_source_overwrite': True,
    }
    (dest / 'm76b_trainer_implementation.json').write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('PATCH:', dest / 'm76b_baseline_to_v2b.patch')
    print('SHA-256 original:', manifest['source_trainer_sha256'])
    print('SHA-256 V2-B:', manifest['v2b_trainer_sha256'])
    print('STATUS: V2-B created; NOT TRAINED; NOT YET FULL-RUN APPROVED')


if __name__ == '__main__':
    main()
