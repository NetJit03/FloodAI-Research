# M6.5D Preflight — PROPOSED, NOT FINALIZED

- Source: `data/sen1floods11`
- Original three event-disjoint folds: **PASS** for CSV counts, no duplicate chips and no event overlap
- Development pool: **243 chips / 7 events**
- Excluded from V2 development: India, Paraguay, Ghana (historical V1 test events)
- Bolivia: pre-existing holdout, previously inspected (not pristine)
- Thailand: diagnostic reference only, not a comparable test ground truth
- No source CSV, TIFF, checkpoint, or original split modified.

## Development event inventory

- Cambodia: 30 chips
- Nigeria: 18 chips
- Pakistan: 28 chips
- Somalia: 26 chips
- Spain: 30 chips
- Sri-Lanka: 42 chips
- USA: 69 chips

## Proposed event-disjoint development folds

- dev_fold_01_usa: train 174 chips / 6 events; validate 69 chips / USA
- dev_fold_02_sri_lanka: train 201 chips / 6 events; validate 42 chips / Sri-Lanka
- dev_fold_03_spain: train 213 chips / 6 events; validate 30 chips / Spain

## Methodological warnings

- These 3 validation folds are intended for V2 model development, not final independent evaluation.
- V1 and V2 must be retrained under identical V2 development splits before comparing methods fairly.
- Do not choose V2 hyperparameters, thresholds or normalization from prior India/Paraguay/Ghana tests.
- Final confirmation requires newly independent, appropriately labeled event(s).
- Confirm SAR numeric units and valid masks before implementing radiometric augmentation.
- The manifests need corresponding training data-root links and an explicit split loader; do NOT pass them directly as --data-root.
- Report event-level results; pixels are spatially correlated and do not provide independent sample counts.
