# M8.0B — DEV Uncertainty Reliability & Error Audit

**Status:** DESCRIPTIVE_DEV_ONLY — No model fitting, recalibration, threshold search or independent TEST.

- M8.0A source protocol fingerprint: `dff29456bb921df80dc4d6afd91b266eb830f04092a28c14fd0870a9806a2529`
- Whole-DEV image-level descriptive analysis: **141/141 validation chips from 3 events**.
- Pixel-level analyses: **9 specifically selected preview chips (3 per event)**; **not an unbiased sample**.
- Prediction rule remains P(water) >= 0.50. UQ values were not used to optimize any decision threshold.
- Pixel correlations do not imply independent samples because pixels within and across chips are spatially correlated.

## A. Event-level image correlations (within each DEV event)

Spearman rank correlation. Negative rho for IoU means higher UQ coincides with lower IoU; sign may differ by event.

| Event | Mean MI vs image error rate | Mean entropy vs image error rate | Mean MI vs image IoU |
|---|---:|---:|---:|
| USA | -0.754 | +0.774 | -0.400 |
| Sri-Lanka | +0.604 | +0.753 | +0.021 |
| Spain | +0.792 | +0.715 | +0.368 |

Do **not** pool the three events and claim that image-level MI is a causal or universally reliable error predictor. Mean UQ is affected by water prevalence and the location of boundaries.

## B. Selected nine-preview pixel-level audit (NOT the full validation population)

Top-10%-UQ capture is the share of all wrongly predicted pixels found after ranking pixels by an uncertainty score and selecting only its highest 10% within each preview image.
**10% is fixed in advance, not optimized.** Error enrichment compares the top-10% error rate to the image(s)' overall error rate.

| Event | Selected ECE (15 bins) | Entropy top-10% error capture | MI top-10% error capture | GT water with P<0.1 |
|---|---:|---:|---:|---:|
| USA | 0.1510 | 82.4% | 2.4% | 0.0% |
| Sri-Lanka | 0.3090 | 48.7% | 11.5% | 0.0% |
| Spain | 0.0195 | 46.4% | 34.5% | 21.4% |

Selected ECE is a pixel-weighted reliability summary from **nine selected cases**, not full-DEV ECE and not a guarantee of calibrated individual decisions.
High error-capture can result from focusing on boundaries; low MI can coincide with confidently wrong predictions, so visualize false-negative regions as well.

## C. Boundaries and reporting constraints

- **Cannot infer full 141-image pixel-level ECE/AUROC** from the 9 stored NPZ previews. Full pixel-level statements require rerunning fixed-checkpoint DEV-only inference over all 141 images, preserving original model/threshold.
- **Cannot conclude UQ helps safely reject or deploy predictions** on independent geography without a new untouched labeled event.
- The reported correlations are descriptive (no p-values or confidence intervals as if pixels were independent).
- The 9 previews were selected non-randomly; do not generalize their ECE/error-capture to the complete dataset.
- M8.0B uses no India/Paraguay/Ghana TEST, Bolivia, or Thailand data, and does not change M7.6A design or V2-B method.

## D. Recommended next research step

Return to **M7.6B**: implement the previously frozen TRAIN-only water-coverage sampler in a separate trainer, unit-test its sampling probabilities and masking rules, then smoke-test without accessing TEST. Next M7.6C: train 3 folds × 3 seeds; M7.6D: compare paired DEV results under frozen settings.

## Output files

- `m80b_image_level_correlations.csv`, `m80b_image_level_diagnostics.csv` — 141 DEV images
- `m80b_selected_preview_by_image.csv`, `m80b_selected_preview_by_event.csv` — 9 selected previews
- `m80b_selected_reliability_bins.csv` — event-level sampled reliability curves
- `m80b_image_error_vs_mi.png`, `m80b_selected_reliability.png`, `m80b_selected_error_capture.png` — figures
- `m80b_manifest.json` — source hashes and provenance
