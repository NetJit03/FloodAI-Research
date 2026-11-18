# M7.5D — V2-B design audit (DEV ONLY)

**Status: DATA AUDIT COMPLETE; MODEL V2-B DESIGN NOT YET FROZEN.**
No model fitting, no checkpoint selection, no threshold search and no TEST/Bolivia/Thailand access.
All case metrics are reused from M7.5C (existing checkpoints and threshold 0.5).

## TRAIN-only water-coverage inventory

| Development fold | Train images | Zero water | (0,1%) | [1%,10%) | [10%,50%) | >=50% |
|---|---:|---:|---:|---:|---:|---:|
| dev_fold_01_usa | 174 | 14 | 38 | 70 | 36 | 16 |
| dev_fold_02_sri_lanka | 201 | 12 | 55 | 80 | 40 | 14 |
| dev_fold_03_spain | 213 | 14 | 59 | 85 | 42 | 13 |

### Notes on image-based sampling
- Full-chip water coverage can differ from water coverage in randomly cropped 256x256 patches.
- Rare water-coverage bins might be excessively repeated by a class-balanced sampler with replacement.
- Candidate mixture probabilities are diagnostics ONLY, not authorization to modify the frozen baseline.
- Check how many unique images appear in >=50% water before deciding whether the sampling hypothesis is practical.

## Sri Lanka three-case DEV audit

| Image | GT-water % | VV water-land median gap (TIFF units) | VH gap (TIFF units) |
|---|---:|---:|---:|
| Sri-Lanka_534068_S1Hand.tif | 98.14% | -0.099 | -8.247 |
| Sri-Lanka_845821_S1Hand.tif | 97.42% | -1.831 | -9.379 |
| Sri-Lanka_713926_S1Hand.tif | 30.72% | -9.819 | -8.607 |

M7.5C prediction diagnostics for the three cases:

| Case | Method | Seed | Water recall | IoU | Predicted-water % | FP | FN |
|---|---|---:|---:|---:|---:|---:|---:|
| Sri-Lanka_534068_S1Hand.tif | baseline | 42 | 0.9961 | 0.9917 | 98.19% | 1138 | 997 |
| Sri-Lanka_534068_S1Hand.tif | v2a | 42 | 0.9917 | 0.9835 | 98.15% | 2151 | 2123 |
| Sri-Lanka_534068_S1Hand.tif | baseline | 123 | 0.9997 | 0.9859 | 99.47% | 3577 | 89 |
| Sri-Lanka_534068_S1Hand.tif | v2a | 123 | 0.9452 | 0.9423 | 93.06% | 778 | 14101 |
| Sri-Lanka_534068_S1Hand.tif | baseline | 777 | 0.2267 | 0.2267 | 22.25% | 1 | 198940 |
| Sri-Lanka_534068_S1Hand.tif | v2a | 777 | 0.1898 | 0.1898 | 18.63% | 14 | 208443 |
| Sri-Lanka_845821_S1Hand.tif | baseline | 42 | 0.9943 | 0.9903 | 97.26% | 947 | 1331 |
| Sri-Lanka_845821_S1Hand.tif | v2a | 42 | 0.9933 | 0.9884 | 97.24% | 1147 | 1577 |
| Sri-Lanka_845821_S1Hand.tif | baseline | 123 | 0.9996 | 0.9875 | 98.57% | 2870 | 89 |
| Sri-Lanka_845821_S1Hand.tif | v2a | 123 | 0.8455 | 0.8435 | 82.58% | 531 | 36249 |
| Sri-Lanka_845821_S1Hand.tif | baseline | 777 | 0.1172 | 0.1172 | 11.43% | 28 | 207060 |
| Sri-Lanka_845821_S1Hand.tif | v2a | 777 | 0.1533 | 0.1533 | 14.95% | 50 | 198591 |
| Sri-Lanka_713926_S1Hand.tif | baseline | 42 | 0.9762 | 0.9460 | 30.96% | 2567 | 1920 |
| Sri-Lanka_713926_S1Hand.tif | v2a | 42 | 0.9686 | 0.9528 | 30.26% | 1335 | 2526 |
| Sri-Lanka_713926_S1Hand.tif | baseline | 123 | 0.9924 | 0.9158 | 33.05% | 6732 | 610 |
| Sri-Lanka_713926_S1Hand.tif | v2a | 123 | 0.9998 | 0.3713 | 82.69% | 136259 | 19 |
| Sri-Lanka_713926_S1Hand.tif | baseline | 777 | 0.9747 | 0.9533 | 30.63% | 1808 | 2040 |
| Sri-Lanka_713926_S1Hand.tif | v2a | 777 | 0.9948 | 0.8228 | 36.98% | 16832 | 419 |

## Proposed V2-B decision gate (manual sign-off required)
1. Inspect train-by-fold counts and rare-bin expected repeat exposures. If >=50%-water bins are extremely small, do not over-weight them without safeguards.
2. Inspect the three GT/VV/VH figures and verify masks, SAR units/order and any suspicious image-label patterns.
3. Re-check V2-A source/actual checkpoint provenance; the earlier M7.5C manifest noted missing run_config.json for 3 V2-A checkpoints.
4. Decide exactly ONE training change. Candidate: predeclared water-coverage-aware image sampler; keep baseline architecture, loss, normalization, optimizer, folds, seeds and threshold fixed.
5. Freeze a separate V2-B protocol BEFORE new training. Evaluate on 3 DEV validation events x seeds 42/123/777. Historical TEST/Bolivia/Thailand remain excluded.

**Limitations:** Observed training coverage and case correlations are not causal identification. These same DEV events informed the method and cannot be called untouched confirmatory testing.
Ground-truth surface water is not automatically newly inundated flood water.
