# M7.4B — Sri Lanka high-water failure diagnostics

**Scope:** retrospective, development VALID only. No retraining, model selection, threshold search or calibration.
No historical TEST, Bolivia or Thailand data used.
Frozen threshold: **0.50**; probability scale identical for all plots.
All six image/seed confusion rows match existing M7.4 audit CSV.

| Image | Seed | GT-water pixels | GT-water fraction | IoU | FN | GT water with P<0.1 |
|---|---:|---:|---:|---:|---:|---:|
| Sri-Lanka_534068_S1Hand.tif | 42 | 257,268 | 98.1% | 0.9917 | 997 | 0.0% |
| Sri-Lanka_534068_S1Hand.tif | 123 | 257,268 | 98.1% | 0.9859 | 89 | 0.0% |
| Sri-Lanka_534068_S1Hand.tif | 777 | 257,268 | 98.1% | 0.2267 | 198,940 | 33.9% |
| Sri-Lanka_845821_S1Hand.tif | 42 | 234,546 | 97.4% | 0.9903 | 1,331 | 0.0% |
| Sri-Lanka_845821_S1Hand.tif | 123 | 234,546 | 97.4% | 0.9875 | 89 | 0.0% |
| Sri-Lanka_845821_S1Hand.tif | 777 | 234,546 | 97.4% | 0.1172 | 207,060 | 45.7% |

## Interpretation guardrails

- Do not remove the two chips or seed 777 from primary results.
- This targeted diagnosis is a follow-up to observed development variation; it is not an independent final test.
- Probability comparison is descriptive; it does not prove a causal failure mechanism.
- Label 0 is valid land even if TIFF metadata states NoData=0; check geographic imagery before alleging label error.
- Keep frozen trainer, evaluator, source TIFFs, manifests and checkpoints unchanged.
- Source-file freeze verification can be run separately with m70d_freeze_protocol.py verify.
