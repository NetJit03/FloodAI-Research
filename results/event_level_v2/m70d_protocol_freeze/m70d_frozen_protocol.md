# M7.0D — FROZEN baseline protocol

- Status: **FROZEN (manual sign-offs + fingerprint match)**
- Recorded at (UTC): 2026-11-16T02:26:51.045221+00:00
- SHA-256 fingerprint: `dff29456bb921df80dc4d6afd91b266eb830f04092a28c14fd0870a9806a2529`
- Trainer SHA-256: `818a30be6880171509cc721f5436a5500d8b778997ec8f45991636569cae2a55`
- Evaluator SHA-256: `6fb8b3f7c897ff215875eca6a6cb6d3cfdc15f35c4807daf50ecc94972709427`
- Trainer hash changed since M6.5D-3: **True** (expected if IoU code was edited; inspect the change)

## Frozen development folds

| Fold | Train | Valid | Validation event |
|---|---:|---:|---|
| dev_fold_01_usa | 174 | 69 | USA |
| dev_fold_02_sri_lanka | 201 | 42 | Sri-Lanka |
| dev_fold_03_spain | 213 | 30 | Spain |

## Method and policy

- Source: Sen1Floods11 hand-labeled pairs; **243 unique chips / 7 events**
- Input: VV/VH; output: surface-water probability and fixed-threshold mask
- Label semantics: `-1` ignore; `0` land; `1` water; finite SAR required; label nodata metadata MUST NOT erase land=0
- Fixed VV range: [-35.0, 5.0] dB; VH range: [-40.0, 0.0] dB
- Training: max 25 epochs, batch 2, crop 256, SmallUNet base 16, AdamW learning rate 0.0003, patience 6
- Future seeds: 42, 123, 777 (each fold trained separately); **no --max-train/--max-val** for full runs
- Checkpoint selected ONLY using VALID micro water IoU; 0.5 threshold fixed
- Empty-union IoU: NaN, not 1.0; report count of undefined per-image IoU
- Primary method comparison: macro average of three validation-event IoUs
- Historical India / Paraguay / Ghana test events excluded from V2 development; Bolivia already inspected, not pristine
- Thailand: diagnostic pilot; not a comparable test without aligned independent surface-water GT
- No TEST-based fitting, threshold tuning, recalibration or architecture selection
- V1 versus V2: train both on identical V2 folds and seeds
- Cryptographic hashes record exact inputs. They do not, by themselves, validate label quality or measurement units.

## Manual sign-offs

1. Confirm original official data provenance, local TIFF conversion history, VV/VH order, and dB numeric units.
2. Compare trainer and evaluator, especially fixed normalization, valid pixel policy, and zero-union IoU NaN behavior.
3. Confirm TRAIN-only augmentation, validation-only early stopping, full fold runs, selection rule, seeds, threshold and output policy.
4. Confirm no India/Paraguay/Ghana, Bolivia or Thai data were used for V2 development/tuning.
5. After any source/CSV/TIFF edits, **a new protocol version, re-audit and re-freeze are necessary**.

## Limitation

A frozen protocol is not a final model or independent test. This script does **not** train or evaluate any model.
