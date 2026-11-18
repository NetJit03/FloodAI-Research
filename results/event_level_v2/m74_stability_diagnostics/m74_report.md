# M7.4 — Read-only development validation stability diagnostic

- Status: checkpoint/history consistency checked; no training or parameter tuning.
- Data isolation: only pre-existing V2 development folds; historical tests excluded.
- Fixed classification threshold: 0.5 from checkpoints.

| Validation event | IoU mean | Sample SD | seed 42 | seed 123 | seed 777 |
|---|---:|---:|---:|---:|---:|
| USA | 0.5383 | 0.0103 | 0.5289 | 0.5367 | 0.5494 |
| Sri Lanka | 0.5989 | 0.1817 | 0.7065 | 0.7011 | 0.3891 |
| Spain | 0.7058 | 0.0118 | 0.6940 | 0.7176 | 0.7057 |

## Observations

- The Sri Lanka fold is unusually sensitive to training seed, primarily at seed 777.
- IoU and recall fluctuations are descriptive; do not infer a causal mechanism from them alone.
- All nine seeds/folds should remain in the report; do not exclude seed 777.
- Selection remains VALID-only and fixed; do not revisit historical TEST for tuning.

## Development validation per-image analysis

- Reconstructed micro IoU (same fixed checkpoint, same 0.5 threshold):

| Event | Seed | Images | IoU | Matches history |
|---|---:|---:|---:|---|
| USA | 42 | 69 | 0.5289 | True |
| USA | 123 | 69 | 0.5367 | True |
| USA | 777 | 69 | 0.5494 | True |
| Sri Lanka | 42 | 42 | 0.7065 | True |
| Sri Lanka | 123 | 42 | 0.7011 | True |
| Sri Lanka | 777 | 42 | 0.3891 | True |
| Spain | 42 | 30 | 0.6940 | True |
| Spain | 123 | 30 | 0.7176 | True |
| Spain | 777 | 30 | 0.7057 | True |

- Top 10 Sri Lanka images with largest positive IoU gap from seeds 42/123 to 777 (GT-water images only):

| Image | GT water pixels | Mean(42,123) minus 777 IoU | Seed 777 recall |
|---|---:|---:|---:|
| Sri-Lanka_845821_S1Hand.tif | 234546 | 0.8718 | 0.1172 |
| Sri-Lanka_534068_S1Hand.tif | 257268 | 0.7621 | 0.2267 |
| Sri-Lanka_400518_S1Hand.tif | 2380 | 0.1038 | 0.4361 |
| Sri-Lanka_236030_S1Hand.tif | 1713 | 0.0737 | 0.5435 |
| Sri-Lanka_916628_S1Hand.tif | 81524 | 0.0503 | 0.5754 |
| Sri-Lanka_132922_S1Hand.tif | 17843 | 0.0502 | 0.0286 |
| Sri-Lanka_748447_S1Hand.tif | 1219 | 0.0488 | 0.3667 |
| Sri-Lanka_1038087_S1Hand.tif | 18112 | 0.0476 | 0.1705 |
| Sri-Lanka_63307_S1Hand.tif | 7005 | 0.0438 | 0.0053 |
| Sri-Lanka_849649_S1Hand.tif | 1892 | 0.0418 | 0.6115 |
