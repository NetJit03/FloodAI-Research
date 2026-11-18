M7.4 Baseline Stability Diagnostics (development validation only)
==================================================================

Purpose: understand variability across seeds, especially Sri Lanka seed 777.
Read-only: DOES NOT train, tune threshold, calibrate, access historical TEST,
Bolivia, or Thai data, or change frozen protocol inputs.

Install:
  cd ~/Projects/FloodAI-Research
  unzip -o ~/Downloads/M74_Baseline_Stability.zip -d .
  source .venv/bin/activate

Verify freeze first:
  python m70d_freeze_protocol.py verify --project-root .

Step A - quick check of training curves, checkpoint metadata, CSVs:
  python m74_baseline_stability.py

Step B - run all 9 checkpoint predictions on V2 development VALID ONLY:
  python m74_baseline_stability.py --inspect-images --device mps

If MPS causes runtime issues, rerun Step B with --device cpu.

Output:
  results/event_level_v2/m74_stability_diagnostics/m74_report.md
  results/event_level_v2/m74_stability_diagnostics/m74_selected_checkpoints.csv
  results/event_level_v2/m74_stability_diagnostics/m74_all_history.csv
  results/event_level_v2/m74_stability_diagnostics/m74_<fold>_training_curves.png

After --inspect-images, also:
  m74_development_validation_per_image.csv
  m74_development_validation_micro.csv
  m74_sri_lanka_image_comparison.csv

NOTE: Historical tests India/Paraguay/Ghana already inspected previously;
do NOT use them for model selection. V2 is not an independent final-test result.
