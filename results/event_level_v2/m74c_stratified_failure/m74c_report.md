# M7.4C — Full-Validation Stratified Failure Analysis

**Scope:** Retrospective, descriptive analysis of the existing V2 *development-validation* per-image predictions.
**No model trained/retrained, no checkpoint changed, no threshold tuning, no historical TEST / Bolivia / Thailand used.**
All IoU/recall metrics are fixed-threshold (0.50) and use only evaluable pixels.
Input per-image CSV SHA-256: `b868a536136775c3ef4d8d307d53f3be34a5acaa40f5fac6dd735ab5b1d33e03`.

## A. Full development-validation results (pixel-micro, 3 seeds per event)

| Event | Images / seed | Seed | Water IoU | Recall | Precision | False negatives |
|---|---:|---:|---:|---:|---:|---:|
| USA | 69 | 42 | 0.5289 | 0.6735 | 0.7112 | 262,687 |
| USA | 69 | 123 | 0.5367 | 0.7172 | 0.6808 | 227,521 |
| USA | 69 | 777 | 0.5494 | 0.7026 | 0.7158 | 239,301 |
| Sri Lanka | 42 | 42 | 0.7065 | 0.7588 | 0.9111 | 283,457 |
| Sri Lanka | 42 | 123 | 0.7011 | 0.7881 | 0.8639 | 249,096 |
| Sri Lanka | 42 | 777 | 0.3891 | 0.4067 | 0.9001 | 697,429 |
| Spain | 30 | 42 | 0.6940 | 0.8163 | 0.8224 | 186,702 |
| Spain | 30 | 123 | 0.7176 | 0.7708 | 0.9123 | 232,952 |
| Spain | 30 | 777 | 0.7057 | 0.8260 | 0.8289 | 176,823 |

## B. Stratification by ground-truth water fraction

Fractions defined as `GT water pixels / valid pixels`. Six fixed diagnostic bins are used:
`0%`; `(0%,1%)`; `[1%,5%)`; `[5%,20%)`; `[20%,90%)`; `[90%,100%]`.
A 0%-water image has undefined water recall. If TP+FP+FN = 0, IoU is undefined (NaN), **not** 1.
Stratum metrics below are **pixel-micro** (sum TP/FP/FN across images, then calculate ratios); this is different from averaging image IoUs.

| Sri Lanka stratum | Images | Seed | Micro IoU | Micro recall | FN pixels |
|---|---:|---:|---:|---:|---:|
| 0% water | 2 | 42 | 0.0000 | undefined | 0 |
| 0% water | 2 | 123 | 0.0000 | undefined | 0 |
| 0% water | 2 | 777 | 0.0000 | undefined | 0 |
| (0%, 1%) | 10 | 42 | 0.3679 | 0.4803 | 7,012 |
| (0%, 1%) | 10 | 123 | 0.3637 | 0.5774 | 5,702 |
| (0%, 1%) | 10 | 777 | 0.3588 | 0.4502 | 7,419 |
| [1%, 5%) | 12 | 42 | 0.2586 | 0.4018 | 38,607 |
| [1%, 5%) | 12 | 123 | 0.2494 | 0.4558 | 35,124 |
| [1%, 5%) | 12 | 777 | 0.2990 | 0.3740 | 40,405 |
| [5%, 20%) | 11 | 42 | 0.4252 | 0.4814 | 124,858 |
| [5%, 20%) | 11 | 123 | 0.4263 | 0.5280 | 113,655 |
| [5%, 20%) | 11 | 777 | 0.4211 | 0.4719 | 127,163 |
| [20%, 90%) | 5 | 42 | 0.6724 | 0.6967 | 110,652 |
| [20%, 90%) | 5 | 123 | 0.7018 | 0.7411 | 94,437 |
| [20%, 90%) | 5 | 777 | 0.6728 | 0.6808 | 116,442 |
| [90%, 100%] | 2 | 42 | 0.9911 | 0.9953 | 2,328 |
| [90%, 100%] | 2 | 123 | 0.9867 | 0.9996 | 178 |
| [90%, 100%] | 2 | 777 | 0.1745 | 0.1745 | 406,000 |

## C. Critical high-water failure: Sri Lanka, seed 777

- Extreme-high-water stratum (`>=90%`): **2 images**.
- Extreme-high-water micro recall: seed 42 **0.9953**, seed 123 **0.9996**, seed 777 **0.1745**.
- The **two most FN-heavy images** contribute **406,000/697,429 = 58.21%** of all Sri Lanka seed-777 false negatives.
- Those two images contain **491,814/1,175,411 = 41.84%** of all evaluable Sri Lanka GT-water pixels.

| Image | GT-water fraction | Seed42 recall | Seed123 recall | Seed777 recall | Seed777 FN |
|---|---:|---:|---:|---:|---:|
| Sri-Lanka_845821_S1Hand.tif | 97.42% | 0.9943 | 0.9996 | 0.1172 | 207,060 |
| Sri-Lanka_534068_S1Hand.tif | 98.14% | 0.9961 | 0.9997 | 0.2267 | 198,940 |

**Interpretation:** Evidence of concentration of seed-777 under-detection in nearly fully flooded development-validation images. This is descriptive, not proof of a particular physical or training mechanism. Do not drop seed 777.

## D. Important scientific interpretation limits

- Only three independent **development validation events** (USA, Sri Lanka, Spain) are represented. Pixels and image chips within events are dependent; they are not independent events.
- These data are already inspected during V2 development. Findings and any resulting model ideas are exploratory. A new untouched event is needed for confirmatory testing.
- The severe Sri Lanka case is assessed within the same event and the same image IDs for all three seeds, which avoids mixing distinct image sets, but does not isolate a causal training mechanism.
- `macro_image_iou` excludes undefined empty-union images. `micro_iou` weights by pixels, so large water-heavy images can dominate.
- No per-pixel predictive probability or image-level SAR rasters are included here: this stage cannot support entropy, calibration, or SAR radiometry claims.
- GT labels encode **surface water**, not necessarily newly inundated flood water.

## E. Next controlled development steps

1. Keep baseline protocol frozen and retain all 9 seed/checkpoint combinations.
2. Specify Model V2 candidates using literature and development-validation diagnostics only (e.g., improved coverage of large contiguous water), not historical TEST.
3. Train both baseline comparator and V2 with identical V2 folds/seeds and report event macro-IoU + sample SD across seeds.
4. Use new independent, label-validated geographic events for a final confirmation; Thailand needs co-registered high-quality GT to calculate comparable IoU.

## Output files

- `m74c_stratum_metrics.csv`: per-event/per-seed/per-stratum pixel-micro and image-macro metrics.
- `m74c_event_seed_metrics.csv`: whole-event pixel-micro metrics.
- `m74c_paired_per_image.csv`: paired per-image comparisons of all three seeds.
- `m74c_per_image_enriched.csv`: 423 original validation rows plus strata and counts.
- `m74c_sri_lanka_seed777_ranked_cases.csv`: ranking of Sri Lanka failures by seed-777 missed water.
- Four PNG figures for Sri Lanka and one CSV with input file checksums.

---
The script checks that each event contains identical images and GT across seeds, and that confusion matrices reconstruct the checkpoint-selected micro IoU.
