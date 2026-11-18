# M7.3 — Multi-Seed Baseline Validation Summary

- Source: fixed V2 development folds, full runs of SmallUNet baseline.
- Seeds: 42, 123, 777; selection by best VALIDATION micro water IoU per fold.
- No TEST or Bolivia or Thailand data were evaluated here.
- Different seeds of the same development events are not independent geographic samples.
- SD uses sample standard deviation (ddof=1), with n=3.

## Best validation IoU per fold and seed

| Event | Seed 42 | Seed 123 | Seed 777 | Mean | Sample SD |
|---|---:|---:|---:|---:|---:|
| USA | 0.5289 | 0.5367 | 0.5494 | 0.5383 | 0.0103 |
| Sri Lanka | 0.7065 | 0.7011 | 0.3891 | 0.5989 | 0.1817 |
| Spain | 0.6940 | 0.7176 | 0.7057 | 0.7058 | 0.0118 |

## Macro average across validation events, per seed

| Seed | Macro mean validation IoU |
|---|---:|
| 42 | 0.6431 |
| 123 | 0.6518 |
| 777 | 0.5481 |

**Across-seed mean of the three macro means:** 0.6143
**Across-seed sample SD of macro means:** 0.0576

## Interpretation constraints

- A single poorly performing seed on Sri Lanka is evidence of seed sensitivity in this setup, not proof of domain shift or its cause.
- Keep all nine runs, including outliers. Do not select/drop seeds on the basis of these validation metrics.
- Before comparing V1 and V2, use identical folds, random seeds, and frozen evaluation policy.
- Fresh independent event-level held-out data are required for a definitive generalization claim.
