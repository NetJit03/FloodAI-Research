# M6.5B — Failure Mechanism Evidence Audit

**Scope:** retrospective diagnostics based on pre-existing fold-specific test outputs. No retraining, threshold search, recalibration or model selection was performed.

## A. Cross-event metrics (three different model checkpoints)

| Event | n | IoU | Recall | ECE | Brier | NLL | GT water P<0.1 | FN with P<0.1 / all FN |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| India | 68 | 0.5169 | 0.5793 | 0.0289 | 0.0560 | 0.2118 | 31.35% | 74.53% |
| Paraguay | 66 | 0.5444 | 0.6507 | 0.0744 | 0.0393 | 0.1754 | 6.35% | 18.17% |
| Ghana | 48 | 0.3925 | 0.4359 | 0.0184 | 0.0346 | 0.1317 | 34.85% | 61.79% |

ECE/Brier/NLL summarize all evaluable pixels. Low global error does not imply good water recall, especially when land is prevalent.

## B. Ghana SAR class separation (only chips containing both classes)

- Rows in separability file: **27**; rows with finite VV/VH gaps: **27**.
- VV median(water) − median(land): median across usable chips = **-4.282** raw TIFF units.
- VH median(water) − median(land): median across usable chips = **-5.319** raw TIFF units.
- VV negative / positive median gap chips: **25 / 2**.
- VH negative / positive median gap chips: **26 / 1**.
- Rows with a missing comparison class in the separability file: **0**. A separate audit is needed to explain excluded chips; a single-class chip can still be useful for segmentation evaluation.
- SAR intensity separation here is label-conditional and descriptive, not a causal explanation of errors.

## C. Fold 3 normalization clipping (evaluable pixels)

Percentages below are the **CSV's percentage-point values** (not unit fractions).

| Event | Split | Pol. | Evaluable pixels | Clipped (%) |
|---|---|---|---:|---:|
| Ghana | test | VH | 9188240 | 0.2235 |
| Ghana | test | VV | 9188240 | 0.0040 |
| Cambodia | train | VH | 7129920 | 1.3173 |
| Cambodia | train | VV | 7129920 | 0.0495 |
| India | train | VH | 14952415 | 0.3759 |
| India | train | VV | 14952415 | 0.1147 |
| Nigeria | train | VH | 4020518 | 0.7458 |
| Nigeria | train | VV | 4020518 | 0.0065 |
| Pakistan | train | VH | 5375862 | 0.2063 |
| Pakistan | train | VV | 5375862 | 0.0201 |
| Paraguay | train | VH | 16626431 | 0.1453 |
| Paraguay | train | VV | 16626431 | 0.0057 |
| Somalia | train | VH | 5374091 | 0.0940 |
| Somalia | train | VV | 5374091 | 0.0077 |
| Sri-Lanka | train | VH | 9963261 | 0.0472 |
| Sri-Lanka | train | VV | 9963261 | 0.0755 |
| USA | train | VH | 17638830 | 0.2450 |
| USA | train | VV | 17638830 | 0.0323 |
| Spain | valid | VH | 7727802 | 1.2698 |
| Spain | valid | VV | 7727802 | 0.3646 |

- Ghana VV clipped: **0.0040%**; Ghana VH clipped: **0.2235%**.
- A small aggregate clipping share would make pervasive clipping an unlikely sole explanation for Ghana's recall gap, but does not rule out local effects.

## D. Fold 3 calibration and spatial uncertainty inventory

- Calibration by split: **found: 2 rows**.
- Spatial selected-image metrics: **found: 3 rows**.
- valid: Recall 0.8082, ECE 0.0116, Brier 0.0359
- test: Recall 0.4359, ECE 0.0184, Brier 0.0346
- Single-model binary predictive entropy is low when P(water) is near 0 **or** 1. It cannot identify confidently wrong predictions without additional evidence.
- Inspect stored spatial maps for where false negatives co-occur with low entropy; do not infer coverage from only three selected images.

## E. Interpretive limits and next research steps

1. Each held-out event was evaluated by a different checkpoint trained on a different set of source events. Differences are descriptive, not a controlled causal estimate of domain shift.
2. These TEST findings are already examined. Do not optimize thresholds, preprocessing ranges, model choice or hyperparameters from them.
3. New method candidates should be motivated by the literature and validated on independent development events. Reserve untouched events for final confirmation.
4. Re-check label conventions, SAR finite masks and pixel grids when interpreting specific failure regions.
5. Ground-truth 'water' is surface water, not necessarily newly inundated land.

## Inputs inspected

- `results/event_level_v1/cross_event_reliability/cross_event_reliability_summary.csv`
- `results/event_level_v1/ghana_sar_diagnostics/ghana_all_image_sar_separability.csv`
- `results/event_level_v1/normalization_audit_fold03/clipping_by_event.csv`
- `results/event_level_v1/calibration_fold03/calibration_by_split.csv` (optional)
- `results/event_level_v1/spatial_uncertainty_fold03/spatial_uncertainty_selected_images.csv` (optional)
