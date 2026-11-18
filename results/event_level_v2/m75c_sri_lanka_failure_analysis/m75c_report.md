# M7.5C — Sri Lanka Per-Image Failure Analysis (DEV ONLY)

**Scope:** Frozen Sri Lanka development validation (42 chips). Existing six checkpoints only.
**No** model training, TEST/Bolivia/Thailand access, threshold search, or model selection on TEST.
**Metric:** water-class IoU (undefined/NaN if no water in GT and prediction); recall undefined for zero GT-water images.
**Comparison unit:** matched image within seed; repeated seeds/images are not independent events.

## Aggregate performance from recomputed DEV pixels

| Seed | Method | Valid images | Micro IoU | Micro Recall | Mean per-image IoU (defined only) |
|---:|---|---:|---:|---:|---:|
| 42 | baseline | 42 | 0.70651 | 0.75884 | 0.37248 |
| 42 | v2a | 42 | 0.68012 | 0.71702 | 0.36451 |
| 123 | baseline | 42 | 0.70107 | 0.78808 | 0.37846 |
| 123 | v2a | 42 | 0.57917 | 0.76900 | 0.35286 |
| 777 | baseline | 42 | 0.38909 | 0.40665 | 0.33653 |
| 777 | v2a | 42 | 0.38657 | 0.42595 | 0.33575 |

## Within-seed per-image deltas

Delta = V2-A IoU − Baseline IoU on the exact same image. NaN/undefined IoUs are not ranked.

### Seed 42

| Image | GT-water % | Baseline IoU | V2-A IoU | Delta |
|---|---:|---:|---:|---:|
| Sri-Lanka_321316_S1Hand.tif | 36.97% | 0.8283 | 0.4964 | -0.3319 |
| Sri-Lanka_152185_S1Hand.tif | 0.84% | 0.6280 | 0.5723 | -0.0557 |
| Sri-Lanka_847275_S1Hand.tif | 21.81% | 0.6993 | 0.6794 | -0.0199 |
| Sri-Lanka_132922_S1Hand.tif | 6.81% | 0.0505 | 0.0324 | -0.0181 |
| Sri-Lanka_163406_S1Hand.tif | 1.93% | 0.5514 | 0.5338 | -0.0177 |
| Sri-Lanka_551926_S1Hand.tif | 7.48% | 0.5578 | 0.5407 | -0.0171 |
| Sri-Lanka_63307_S1Hand.tif | 2.67% | 0.0158 | 0.0024 | -0.0134 |
| Sri-Lanka_916628_S1Hand.tif | 31.36% | 0.5770 | 0.5648 | -0.0123 |

### Seed 123

| Image | GT-water % | Baseline IoU | V2-A IoU | Delta |
|---|---:|---:|---:|---:|
| Sri-Lanka_713926_S1Hand.tif | 30.72% | 0.9158 | 0.3713 | -0.5445 |
| Sri-Lanka_845821_S1Hand.tif | 97.42% | 0.9875 | 0.8435 | -0.1440 |
| Sri-Lanka_321316_S1Hand.tif | 36.97% | 0.8444 | 0.7474 | -0.0971 |
| Sri-Lanka_612594_S1Hand.tif | 16.45% | 0.9001 | 0.8182 | -0.0819 |
| Sri-Lanka_152185_S1Hand.tif | 0.84% | 0.4738 | 0.3999 | -0.0739 |
| Sri-Lanka_63307_S1Hand.tif | 2.67% | 0.0824 | 0.0307 | -0.0517 |
| Sri-Lanka_883641_S1Hand.tif | 5.15% | 0.6720 | 0.6205 | -0.0515 |
| Sri-Lanka_534068_S1Hand.tif | 98.14% | 0.9859 | 0.9423 | -0.0436 |

### Seed 777

| Image | GT-water % | Baseline IoU | V2-A IoU | Delta |
|---|---:|---:|---:|---:|
| Sri-Lanka_152185_S1Hand.tif | 0.84% | 0.6555 | 0.4785 | -0.1770 |
| Sri-Lanka_713926_S1Hand.tif | 30.72% | 0.9533 | 0.8228 | -0.1305 |
| Sri-Lanka_321316_S1Hand.tif | 36.97% | 0.8476 | 0.7668 | -0.0808 |
| Sri-Lanka_233609_S1Hand.tif | 2.67% | 0.2733 | 0.2229 | -0.0505 |
| Sri-Lanka_883641_S1Hand.tif | 5.15% | 0.7524 | 0.7092 | -0.0432 |
| Sri-Lanka_956740_S1Hand.tif | 3.92% | 0.8573 | 0.8165 | -0.0408 |
| Sri-Lanka_534068_S1Hand.tif | 98.14% | 0.2267 | 0.1898 | -0.0369 |
| Sri-Lanka_922192_S1Hand.tif | 0.43% | 0.2400 | 0.2111 | -0.0289 |

## Failure-stratification summary

Descriptive only. Each image is reused over three seeds; these are not independent geographic events.

| Method | Seed | GT-water group | Images | Mean defined per-image IoU | Mean defined recall |
|---|---:|---|---:|---:|---:|
| baseline | 42 | (0, 1%) GT water | 10 | 0.2784 | 0.3716 |
| baseline | 42 | >=10% GT water | 10 | 0.6269 | 0.6495 |
| baseline | 42 | [1%, 10%) GT water | 20 | 0.3296 | 0.4292 |
| baseline | 42 | zero GT water | 2 | 0.0000 | nan |
| baseline | 123 | (0, 1%) GT water | 10 | 0.2963 | 0.4501 |
| baseline | 123 | >=10% GT water | 10 | 0.6426 | 0.6796 |
| baseline | 123 | [1%, 10%) GT water | 20 | 0.3253 | 0.4827 |
| baseline | 123 | zero GT water | 2 | 0.0000 | nan |
| baseline | 777 | (0, 1%) GT water | 10 | 0.2690 | 0.3479 |
| baseline | 777 | >=10% GT water | 10 | 0.4629 | 0.4765 |
| baseline | 777 | [1%, 10%) GT water | 20 | 0.3239 | 0.4079 |
| baseline | 777 | zero GT water | 2 | 0.0000 | nan |
| v2a | 42 | (0, 1%) GT water | 10 | 0.2885 | 0.3854 |
| v2a | 42 | >=10% GT water | 10 | 0.5899 | 0.6008 |
| v2a | 42 | [1%, 10%) GT water | 20 | 0.3263 | 0.4102 |
| v2a | 42 | zero GT water | 2 | 0.0000 | nan |
| v2a | 123 | (0, 1%) GT water | 10 | 0.2931 | 0.4615 |
| v2a | 123 | >=10% GT water | 10 | 0.5504 | 0.6924 |
| v2a | 123 | [1%, 10%) GT water | 20 | 0.3192 | 0.5160 |
| v2a | 123 | zero GT water | 2 | 0.0000 | nan |
| v2a | 777 | (0, 1%) GT water | 10 | 0.2888 | 0.4637 |
| v2a | 777 | >=10% GT water | 10 | 0.4563 | 0.4971 |
| v2a | 777 | [1%, 10%) GT water | 20 | 0.3325 | 0.4638 |
| v2a | 777 | zero GT water | 2 | 0.0000 | nan |

## Run provenance and limitations

- Checkpoints were reused unchanged with frozen threshold 0.5 and train_sar_unet.py preprocessing.
- Original frozen protocol must remain unchanged. Source-configuration verification is still manual where V2-A run_config.json is missing.
- V2-A checkpoint folders without run_config.json: **3** / 3 for Sri Lanka.
- Do not infer causality from group differences or Gradients/XAI; no XAI was run in this analysis.
- Proposed V2-B should be one change based on DEV evidence, followed by same 3 folds × 3 seeds and a frozen protocol.
- Keep historical TEST events out of development and reserve independent, appropriately labeled events for final evaluation.

## Checkpoints

- `baseline seed=42`: `results/event_level_v2/baseline_seed42/dev_fold_02_sri_lanka/best_sar_unet.pt`
- `v2a seed=42`: `results/event_level_v2/v2a_eventbalanced_seed42/dev_fold_02_sri_lanka/best_sar_unet.pt`
- `baseline seed=123`: `results/event_level_v2/baseline_seed123/dev_fold_02_sri_lanka/best_sar_unet.pt`
- `v2a seed=123`: `results/event_level_v2/v2a_eventbalanced_seed123/dev_fold_02_sri_lanka/best_sar_unet.pt`
- `baseline seed=777`: `results/event_level_v2/baseline_seed777/dev_fold_02_sri_lanka/best_sar_unet.pt`
- `v2a seed=777`: `results/event_level_v2/v2a_eventbalanced_seed777/dev_fold_02_sri_lanka/best_sar_unet.pt`
