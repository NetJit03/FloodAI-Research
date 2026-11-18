#!/usr/bin/env python3
"""M7.6B DEV-only audit gate after sampler audit and real TRAIN-batch smoke.

No training, no checkpoint evaluation, no TEST access. This is an implementation
readiness check, NOT a research performance claim.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from m76b_water_sampler import EXPECTED, BINS, check_frozen, sha256


def rows(path):
    if not path.is_file():
        raise FileNotFoundError(path)
    with path.open(newline='', encoding='utf-8') as f:
        return list(csv.DictReader(f))


def gate(root: Path) -> dict:
    frozen=check_frozen(root)
    base=root/'results/event_level_v2/m76b_implementation_audit'
    impl=base/'m76b_trainer_implementation.json'
    if not impl.is_file():
        raise FileNotFoundError('No derived trainer implementation manifest: ' + str(impl))
    setup=json.loads(impl.read_text(encoding='utf-8'))
    trainer=root/setup['v2b_trainer']
    original=root/setup['source_trainer']
    if not original.is_file() or sha256(original) != setup['source_trainer_sha256']:
        raise ValueError('Frozen original trainer changed since V2-B creation: STOP')
    if not trainer.is_file() or sha256(trainer) != setup['v2b_trainer_sha256']:
        raise ValueError('Derived V2-B trainer changed since creation: STOP')
    if setup['design_fingerprint'] != frozen['design_fingerprint']:
        raise ValueError('Implementation and frozen design mismatch')
    evidence = []
    for fold, (n, _, _) in EXPECTED.items():
        folder=base/fold
        manifest=json.loads((folder/'m76b_sampler_manifest.json').read_text(encoding='utf-8'))
        smoke=json.loads((folder/'m76b_real_sampler_smoke.json').read_text(encoding='utf-8'))
        weight=rows(folder/'m76b_train_sampling_weights.csv')
        groups=rows(folder/'m76b_sampling_by_bin.csv')
        probe=rows(folder/'m76b_three_epoch_sampling_probe.csv')
        if not (manifest['fold'] == fold and manifest['n_train'] == n and
                manifest['num_samples_per_epoch'] == n and
                manifest['replacement'] is True and
                manifest['design_fingerprint'] == frozen['design_fingerprint'] and
                manifest['trainer_v2b_sha256'] == sha256(trainer) and
                len(weight) == n and len(groups) == 5 and len(probe) == 15):
            raise ValueError('Unexpected sampler evidence: ' + fold)
        if ([r['bin'] for r in groups] != list(BINS) or
            not all(int(r['n_images']) > 0 for r in groups) or
            abs(sum(float(r['draw_probability_mass']) for r in groups) - 1) > 1e-10 or
            abs(sum(float(r['draw_probability']) for r in weight) - 1) > 1e-10):
            raise ValueError('Probability mass/bin evidence failed: ' + fold)
        if not (smoke['status'] == 'PASS_REAL_TRAIN_BATCH_NO_OPTIMIZER' and
                smoke['fold'] == fold and smoke['train_count'] == n and
                smoke['valid_pixels'] > 0 and smoke['batch_shape'][1] == 2 and
                smoke['no_test_or_validation_metrics'] is True):
            raise ValueError('Real TRAIN sampler smoke not passed: ' + fold)
        evidence.append({'fold':fold,'train_count':n,'seed_smoke':smoke['seed'],
                         'real_batch_shape':smoke['batch_shape'],
                         'sampler_bins':{r['bin']:int(r['n_images']) for r in groups}})
    result={'status':'PASS_M76B_READY_FOR_M76C_FULL_TRAIN',
            'design_fingerprint':frozen['design_fingerprint'],
            'baseline_trainer_sha256':sha256(original),
            'v2b_trainer_sha256':sha256(trainer),
            'folds':evidence,
            'warning':'No optimizer training in M7.6B; independent TEST not accessed.'}
    out=base/'m76b_gate_result.json'
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('PASS: M7.6B V2-B source/frozen design + all 3 REAL sampler smoke tests')
    print('NEXT: M7.6C 3 folds x 3 seeds, full training; do not use --max-train/--max-val')
    print('Saved:',out)
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--project-root',type=Path,default=Path('.'))
    a=p.parse_args()
    gate(a.project_root.resolve())


if __name__=='__main__':
    main()
