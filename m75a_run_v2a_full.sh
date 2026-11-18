#!/usr/bin/env bash
# M7.5A DEV-only full experiments. Runs sequentially; nothing asynchronous.
set -euo pipefail
cd "$(dirname "$0")"
DEVICE="${DEVICE:-mps}"

# Avoid editing, overwriting or training on frozen historical TEST data.
python m70d_freeze_protocol.py verify --project-root .
python m75a_preflight.py \
  --roots-dir data/sen1floods11/v2_development_roots \
  --out-dir results/event_level_v2/m75a_design_preflight

for seed in 42 123 777; do
  for fold in dev_fold_01_usa dev_fold_02_sri_lanka dev_fold_03_spain; do
    echo "=== V2-A FULL seed=${seed} fold=${fold} ==="
    python train_v2a_eventbalanced.py \
      --data-root "data/sen1floods11/v2_development_roots/${fold}" \
      --output-dir "results/event_level_v2/v2a_eventbalanced_seed${seed}/${fold}" \
      --epochs 25 \
      --batch-size 2 \
      --crop-size 256 \
      --base-channels 16 \
      --lr 0.0003 \
      --patience 6 \
      --seed "${seed}" \
      --device "${DEVICE}"
  done
done
python m75a_compare_v2a_dev.py
