M7.3 — Multi-Seed Baseline Summary (read-only)

1. Put m73_multiseed_summary.py in the FloodAI-Research project root.
2. Run:
   cd ~/Projects/FloodAI-Research
   source .venv/bin/activate
   python m70d_freeze_protocol.py verify --project-root .
   python m73_multiseed_summary.py

Expected folder structure:
  results/event_level_v2/baseline_seed{42,123,777}/dev_fold_0{1,2,3}_*/
      history.csv
      best_sar_unet.pt

Produces:
  results/event_level_v2/m73_multiseed_summary/m73_run_summary.csv
  results/event_level_v2/m73_multiseed_summary/m73_event_summary.csv
  results/event_level_v2/m73_multiseed_summary/m73_seed_summary.csv
  results/event_level_v2/m73_multiseed_summary/m73_results.md
  results/event_level_v2/m73_multiseed_summary/m73_multiseed_iou.png (if matplotlib installed)

It verifies each checkpoint's seed, counts, threshold, best epoch and IoU
against the corresponding history. No training or test evaluation is performed.
