# M7.5B — Paired DEV Validation Audit

- Status: **COMPLETE_WITH_WARNINGS**
- Results root: `/Users/netinho/Projects/FloodAI-Research/results/event_level_v2`
- Methods: Baseline small U-Net vs V2-A event-balanced sampling
- Scope: **DEVELOPMENT VALIDATION ONLY** (USA, Sri Lanka, Spain), no TEST or Bolivia/Thailand opened
- Unit of comparison: matched fold × random seed (9 paired runs); all metrics are water IoU
- Selection reconstructed from history: retain first epoch with IoU improvement > 1e-5; max 25 epochs
- Prespecified binary decision threshold: 0.5; not tuned here

## Fold × seed pairing

| Event | Seed | Baseline IoU | V2-A IoU | Delta | Epochs B/V2A | Complete |
|---|---:|---:|---:|---:|---|---|
| USA | 42 | 0.52888 | 0.54423 | 0.01535 | 1/2 | True |
| Sri Lanka | 42 | 0.70651 | 0.68012 | -0.02639 | 4/4 | True |
| Spain | 42 | 0.69395 | 0.69104 | -0.00291 | 9/2 | True |
| USA | 123 | 0.53673 | 0.52468 | -0.01205 | 6/3 | True |
| Sri Lanka | 123 | 0.70107 | 0.57917 | -0.12190 | 8/8 | True |
| Spain | 123 | 0.71763 | 0.71699 | -0.00063 | 10/9 | True |
| USA | 777 | 0.54936 | 0.54525 | -0.00412 | 9/9 | True |
| Sri Lanka | 777 | 0.38909 | 0.38657 | -0.00252 | 4/4 | True |
| Spain | 777 | 0.70574 | 0.71318 | 0.00744 | 10/3 | True |

## Macro (equal weighting for three development events)

| Seed | Baseline macro IoU | V2-A macro IoU | Paired delta | Complete |
|---:|---:|---:|---:|---|
| 42 | 0.64312 | 0.63846 | -0.00465 | True |
| 123 | 0.65181 | 0.60695 | -0.04486 | True |
| 777 | 0.54807 | 0.54833 | 0.00027 | True |

**Across-seed mean macro IoU:** Baseline **0.614330**, V2-A **0.597915**, paired delta **-0.016414**.
**Sample SD across seed-level macros:** Baseline 0.057551, V2-A 0.045741, paired delta 0.024756.

## Event-level means over matched seeds

| Event | Baseline | V2-A | Mean paired delta | N seeds |
|---|---:|---:|---:|---:|
| USA | 0.53832 | 0.53805 | -0.00027 | 3 |
| Sri Lanka | 0.59889 | 0.54862 | -0.05027 | 3 |
| Spain | 0.70577 | 0.70707 | 0.00130 | 3 |

## Checkpoint and configuration integrity

| Method | Event | Seed | Status | Errors | Warnings |
|---|---|---:|---|---:|---:|
| baseline | USA | 42 | PASS | 0 | 0 |
| baseline | Sri Lanka | 42 | PASS | 0 | 0 |
| baseline | Spain | 42 | PASS | 0 | 0 |
| baseline | USA | 123 | PASS | 0 | 0 |
| baseline | Sri Lanka | 123 | PASS | 0 | 0 |
| baseline | Spain | 123 | PASS | 0 | 0 |
| baseline | USA | 777 | PASS | 0 | 0 |
| baseline | Sri Lanka | 777 | PASS | 0 | 0 |
| baseline | Spain | 777 | PASS | 0 | 0 |
| v2a | USA | 42 | PASS_WITH_WARNINGS | 0 | 1 |
| v2a | Sri Lanka | 42 | PASS_WITH_WARNINGS | 0 | 1 |
| v2a | Spain | 42 | PASS_WITH_WARNINGS | 0 | 1 |
| v2a | USA | 123 | PASS_WITH_WARNINGS | 0 | 1 |
| v2a | Sri Lanka | 123 | PASS_WITH_WARNINGS | 0 | 1 |
| v2a | Spain | 123 | PASS_WITH_WARNINGS | 0 | 1 |
| v2a | USA | 777 | PASS_WITH_WARNINGS | 0 | 1 |
| v2a | Sri Lanka | 777 | PASS_WITH_WARNINGS | 0 | 1 |
| v2a | Spain | 777 | PASS_WITH_WARNINGS | 0 | 1 |

### v2a / USA / seed 42
- CHECK MANUALLY: run_config.json missing: some full-run parameters cannot be confirmed

### v2a / Sri Lanka / seed 42
- CHECK MANUALLY: run_config.json missing: some full-run parameters cannot be confirmed

### v2a / Spain / seed 42
- CHECK MANUALLY: run_config.json missing: some full-run parameters cannot be confirmed

### v2a / USA / seed 123
- CHECK MANUALLY: run_config.json missing: some full-run parameters cannot be confirmed

### v2a / Sri Lanka / seed 123
- CHECK MANUALLY: run_config.json missing: some full-run parameters cannot be confirmed

### v2a / Spain / seed 123
- CHECK MANUALLY: run_config.json missing: some full-run parameters cannot be confirmed

### v2a / USA / seed 777
- CHECK MANUALLY: run_config.json missing: some full-run parameters cannot be confirmed

### v2a / Sri Lanka / seed 777
- CHECK MANUALLY: run_config.json missing: some full-run parameters cannot be confirmed

### v2a / Spain / seed 777
- CHECK MANUALLY: run_config.json missing: some full-run parameters cannot be confirmed

## Scientific interpretation and limits

1. These are **DEV** comparisons only; not independent TEST performance, not an unbiased generalization estimate and not a causal mechanism test.
2. Seeds share the same underlying validation event; 9 runs are **not nine independent geographic events**. Avoid formal significance claims from treating them as independent.
3. Event-balanced sampling is the intended change. If checkpoint/config metadata or source review does not establish all other controls, mark the comparison as only *partially audited*.
4. Checkpoint metadata inspection uses safe `torch.load(weights_only=True)` only. A missing field yields a warning; a mismatch yields an error. Warnings require manual source review.
5. No historical India/Paraguay/Ghana TEST, Bolivia, Thai pilot, or held-out labels were accessed. Preserve those boundaries for future independent evaluation.
6. Do not choose a new threshold, hyperparameter, or model based on historical TEST results. Record this audit as DEV-only evidence.

- Figure: /Users/netinho/Projects/FloodAI-Research/results/event_level_v2/m75b_validation_comparison_audit/m75b_pair_deltas.png
