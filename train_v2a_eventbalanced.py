#!/usr/bin/env python3
"""M7.5A V2-A experiment: event-balanced TRAIN sampling, otherwise frozen V1.

Imports all training architecture, preprocessing, augmentation, loss, and
validation logic from the user's unchanged train_sar_unet.py. This separate
file never edits the frozen baseline. Runs DEV folds only, not TEST.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import random
from collections import Counter, defaultdict, deque
from pathlib import Path

import numpy as np
import torch
from torch.utils.data import DataLoader, Sampler


EXPECTED = {
    'dev_fold_01_usa': (174, 69, 'USA'),
    'dev_fold_02_sri_lanka': (201, 42, 'Sri-Lanka'),
    'dev_fold_03_spain': (213, 30, 'Spain'),
}
HISTORICAL_TEST = {'India', 'Paraguay', 'Ghana', 'Bolivia'}
ALLOWED_SOURCE = {'Mekong', 'Nigeria', 'Pakistan', 'Somalia', 'Spain', 'Sri-Lanka', 'USA'}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def development_smoke_subset(records, n: int):
    """Take a deterministic cross-event slice, SMOKE only (never full research)."""
    groups = defaultdict(deque)
    for record in records:
        groups[record[2]].append(record)
    out = []
    while len(out) < n and any(groups.values()):
        for event in sorted(groups):
            if groups[event] and len(out) < n:
                out.append(groups[event].popleft())
    return out


def calculate_weights(events: list[str]) -> np.ndarray:
    if not events:
        raise ValueError('At least one training record is needed')
    counts = Counter(events)
    if not all(isinstance(e, str) and e for e in events):
        raise ValueError('Event ids must be nonempty strings')
    k = len(counts)
    # Sum of weights for each event == 1 / number of events.
    return np.asarray([1.0 / (k * counts[e]) for e in events], dtype=np.float64)


class TrackedBalancedSampler(Sampler[int]):
    """Exactly len(training records) samples per epoch, replacement=True.

    One independent RNG initialized from the experiment seed is used for
    sampling across epochs. Training-crop RNG is still the original trainer's.
    """
    def __init__(self, events: list[str], seed: int):
        self.events = events
        self.weights = torch.from_numpy(calculate_weights(events).copy())
        self.generator = torch.Generator().manual_seed(seed)
        self.last_counts: dict[str, int] = {}

    def __len__(self):
        return len(self.events)

    def __iter__(self):
        idxs = torch.multinomial(self.weights, len(self.events), replacement=True,
                                 generator=self.generator).tolist()
        self.last_counts = dict(Counter(self.events[i] for i in idxs))
        return iter(idxs)


def self_test():
    events = ['Alpha'] * 6 + ['Beta'] * 2
    w = calculate_weights(events)
    assert len(w) == 8 and abs(sum(w[:6]) - 0.5) < 1e-12
    assert abs(sum(w[6:]) - 0.5) < 1e-12
    s1 = TrackedBalancedSampler(events, 19)
    s2 = TrackedBalancedSampler(events, 19)
    assert list(iter(s1)) == list(iter(s2))
    assert sum(s1.last_counts.values()) == len(events)
    assert len(set(s1.last_counts).difference({'Alpha', 'Beta'})) == 0
    print('PASS M7.5A V2-A sampler: equal event mass, reproducible draws, epoch size fixed')


def ensure_local_trainer_is_fixed(trainer):
    # Pure CPU, synthetic all-land validation case. A no-water union must have
    # undefined water IoU, never artificially perfect IoU=1.
    class AlwaysLand(torch.nn.Module):
        def forward(self, x):
            return torch.full((x.shape[0], 1, x.shape[2], x.shape[3]),
                              -100., dtype=x.dtype, device=x.device)

    fake = (torch.zeros((1, 2, 8, 8)), torch.zeros((1, 1, 8, 8)),
            torch.ones((1, 1, 8, 8)))
    metric = trainer.evaluate(AlwaysLand(), [fake], 'cpu', threshold=.5)
    if not math.isnan(float(metric['iou'])):
        raise RuntimeError('LOCAL trainer still gives IoU=1 for an empty union. '
                           'Use the already-audited IoU fix in your LOCAL '
                           'train_sar_unet.py before V2-A; do not copy an old trainer.')


def validate_folds(trainer, root: Path):
    if root.name not in EXPECTED:
        raise ValueError(f'DEV root must end in one of {list(EXPECTED)}; got {root}')
    expected_train, expected_val, expected_val_event = EXPECTED[root.name]
    rows = trainer.inspect_splits(root)
    train, valid = rows['train'], rows['valid']
    if (len(train), len(valid)) != (expected_train, expected_val):
        raise RuntimeError('Unexpected DEV counts; verify original V2 manifests')
    if rows['test'] or rows['bolivia']:
        raise RuntimeError('Refusing to run: development test/bolivia CSV stubs not empty')
    tr_events = {r[2] for r in train}
    val_events = {r[2] for r in valid}
    if tr_events & val_events or val_events != {expected_val_event}:
        raise RuntimeError('Event-disjoint validation violated')
    if (tr_events | val_events) - ALLOWED_SOURCE or (tr_events | val_events) & HISTORICAL_TEST:
        raise RuntimeError('Unexpected / historical TEST event in development')
    return train, valid


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--self-test', action='store_true')
    p.add_argument('--data-root', type=Path, default=None)
    p.add_argument('--output-dir', type=Path, default=None)
    p.add_argument('--epochs', type=int, default=25)
    p.add_argument('--batch-size', type=int, default=2)
    p.add_argument('--crop-size', type=int, default=256)
    p.add_argument('--base-channels', type=int, default=16)
    p.add_argument('--lr', type=float, default=0.0003)
    p.add_argument('--patience', type=int, default=6)
    p.add_argument('--seed', type=int, default=42)
    p.add_argument('--max-train', type=int, default=0, help='SMOKE ONLY; not a final result')
    p.add_argument('--max-val', type=int, default=0, help='SMOKE ONLY; not a final result')
    p.add_argument('--check-only', action='store_true')
    p.add_argument('--device', choices=('auto','mps','cpu','cuda'), default='auto')
    args = p.parse_args()
    if args.self_test:
        self_test()
        return
    if args.data_root is None:
        p.error('--data-root is required for project checks/training')
    if args.output_dir is None and not args.check_only:
        p.error('--output-dir required for training')
    if args.seed not in (42,123,777):
        p.error('pre-registered seeds are 42, 123, 777')
    if (args.epochs < 1 or args.batch_size < 1 or args.crop_size != 256 or
        args.base_channels != 16 or args.lr != .0003 or args.patience != 6 or
        args.max_train < 0 or args.max_val < 0):
        p.error('Use frozen settings: crop=256, base=16, lr=0.0003, patience=6, batch>=1, epochs>=1')
    if not args.check_only and not (args.max_train or args.max_val) and (args.epochs != 25 or args.batch_size != 2):
        p.error('Full experiments must use --epochs 25 --batch-size 2; subset SMOKE can override')

    # The user's LOCAL version is authoritative: this artifact deliberately
    # does not bundle a replacement of the frozen trainer.
    import train_sar_unet as base
    ensure_local_trainer_is_fixed(base)
    root = args.data_root.resolve()
    train_records, val_records = validate_folds(base, root)
    if args.max_train: train_records = development_smoke_subset(train_records, args.max_train)
    if args.max_val: val_records = val_records[:args.max_val]
    if not train_records or not val_records:
        raise RuntimeError('No train / validation samples in requested slice')
    base.seed_all(args.seed)
    sampler = TrackedBalancedSampler([r[2] for r in train_records], args.seed)
    events = Counter(r[2] for r in train_records)
    print('V2-A event-balanced weights (total probability/event):',
          {e: round(sum(sampler.weights[i].item() for i,r in enumerate(train_records) if r[2]==e), 6)
           for e in sorted(events)})
    print('Training records:', len(train_records), 'Validation records:', len(val_records))
    if args.check_only:
        x, y, v = base.SarWaterDataset(train_records, crop_size=256, augment=True)[0]
        print('Sample shape:', tuple(x.shape), 'label:', tuple(y.shape), 'valid:', int(v.sum()))
        print('PASS V2-A DEV root, local zero-union IoU, train-only sampler, no TEST')
        return
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise FileExistsError(f'Refusing to overwrite existing experiment folder: {args.output_dir}')
    if args.device == 'auto':
        device = 'mps' if torch.backends.mps.is_available() else (
                 'cuda' if torch.cuda.is_available() else 'cpu')
    else:
        device = args.device
    if device == 'mps' and not torch.backends.mps.is_available():
        raise RuntimeError('MPS requested but not available')
    if device == 'cuda' and not torch.cuda.is_available():
        raise RuntimeError('CUDA requested but not available')
    smoke = bool(args.max_train or args.max_val or args.epochs != 25)
    if smoke:
        print('WARNING: SMOKE / SUBSET RUN. Do not report as research results.')
    print('Device:', device, '| fold:', root.name, '| seed:', args.seed)
    train = DataLoader(base.SarWaterDataset(train_records, args.crop_size, True),
                       batch_size=args.batch_size, sampler=sampler,
                       num_workers=0, pin_memory=False)
    valid = DataLoader(base.SarWaterDataset(val_records, augment=False),
                       batch_size=1, shuffle=False, num_workers=0, pin_memory=False)
    model = base.SmallUNet(args.base_channels).to(device)
    optim = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=1e-4)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    h_path = args.output_dir / 'history.csv'
    exposure_path = args.output_dir / 'sampled_events_by_epoch.csv'
    best, bad = -1., 0
    with h_path.open('w', newline='') as h, exposure_path.open('w', newline='') as e:
        hw = csv.writer(h)
        ew = csv.writer(e)
        hw.writerow(['epoch','train_loss','val_loss','val_iou','val_f1','val_recall','val_precision'])
        ew.writerow(['epoch','event','source_count','sampled_count'])
        for epoch in range(1, args.epochs+1):
            model.train()
            total = 0.
            for x, y, v in train:
                x,y,v = x.to(device), y.to(device), v.to(device)
                optim.zero_grad(set_to_none=True)
                logits = model(x)
                loss = base.masked_bce_dice(logits,y,v)
                loss.backward()
                optim.step()
                total += float(loss.item())
            for name in sorted(events):
                ew.writerow([epoch,name,events[name],sampler.last_counts.get(name,0)])
            assert sum(sampler.last_counts.values()) == len(train_records)
            m = base.evaluate(model, valid, device, threshold=.5)
            hw.writerow([epoch,total/max(1,len(train)),m['loss'],m['iou'],m['f1'],m['recall'],m['precision']])
            h.flush(); e.flush()
            print(f"Epoch {epoch:02d} | val IoU={m['iou']:.5f} | val recall={m['recall']:.5f}", flush=True)
            if math.isfinite(float(m['iou'])) and m['iou'] > best + 1e-5:
                best, bad = m['iou'],0
                torch.save({'model_state':model.state_dict(),'architecture':'SmallUNet',
                            'base_channels':args.base_channels,'db_min':[-35.,-40.],
                            'db_max':[5.,0.],
                            'label_scheme':{'ignore':-1,'non_water':0,'water':1},
                            'threshold':.5,'epoch':epoch,'validation_metrics':m,
                            'seed':args.seed,'train_count':len(train_records),
                            'valid_count':len(val_records),
                            'experiment':'M7.5A_V2A_eventbalanced',
                            'sampler':'inverse_event_frequency_replacement',
                            'smoke':smoke}, args.output_dir/'best_sar_unet.pt')
            else:
                bad += 1
                if bad >= args.patience:
                    print('Early stopping: no improvement for',args.patience,'epochs')
                    break
    metadata = {'experiment':'M7.5A_V2A_eventbalanced','smoke':smoke,
                'fold':root.name,'seed':args.seed,'source_root':str(root),
                'n_train':len(train_records),'n_val':len(val_records),
                'train_events':events,'validation_events':sorted({r[2] for r in val_records}),
                'sampler':'probability_per_image = 1/(n_training_events * number_of_images_in_event)',
                'replacement':True,'draws_per_epoch':len(train_records),
                'main_change_vs_v1':'TRAIN sampling only, no architecture/loss/preprocessing change',
                'model_selection':'valid pixel-micro IoU','threshold':0.5,
                'max_epochs':args.epochs,'batch_size':args.batch_size,'crop_size':args.crop_size,
                'base_channels':args.base_channels,'learning_rate':args.lr,
                'patience':args.patience,'best_dev_iou':best,
                'train_source_sha256':sha256(Path(base.__file__)),
                'v2_source_sha256':sha256(Path(__file__)),
                'note':'Development validation only, NOT final independent generalization evidence'}
    (args.output_dir/'run_config_v2a.json').write_text(json.dumps(metadata,indent=2,default=str))
    print('V2-A complete; best DEV validation IoU:',round(best,5))
    print('Saved outputs:',args.output_dir)

if __name__ == '__main__':
    main()
