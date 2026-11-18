# M7.5A — เริ่ม Model V2-A (Event-Balanced Sampling)

> **ยังไม่ได้ Train V2-A** ไฟล์นี้มีรหัสทดลองและขั้นตรวจสอบสำหรับรันบนเครื่องของคุณ ข้อมูล M7.4C ที่แนบเป็นตัวอ้างอิง DEV เท่านั้น

## 1. ติดตั้งไฟล์

แตก `M75A_Model_V2_Design.zip` แล้ว **คัดลอกไฟล์ใน ZIP ทุกไฟล์ที่อยู่โฟลเดอร์หลัก** (`train_v2a_eventbalanced.py`, `m75a_preflight.py`, `m75a_compare_v2a_dev.py`, `m74c_baseline_reference.csv` และไฟล์ .sh) ไปยัง `~/Projects/FloodAI-Research`

**ห้ามแทนที่** `train_sar_unet.py` เดิม — V2-A import ฟังก์ชันเดิมจาก local trainer ที่คุณแก้ IoU=NaN แล้ว และไม่แก้ freeze baseline.

## 2. เช็กโค้ดสุ่มและอ่าน Frozen Protocol (ไม่ Train)

```bash
cd ~/Projects/FloodAI-Research
source .venv/bin/activate
python train_v2a_eventbalanced.py --self-test
python m70d_freeze_protocol.py verify --project-root .
python m75a_preflight.py \
  --roots-dir data/sen1floods11/v2_development_roots
```

## 3. Preflight V2-A 1 Fold (ไม่ Train)

```bash
python train_v2a_eventbalanced.py \
  --data-root data/sen1floods11/v2_development_roots/dev_fold_01_usa \
  --seed 42 --check-only
```

## 4. Smoke Test Local — ไม่ใช่ผลวิจัย

```bash
python train_v2a_eventbalanced.py \
  --data-root data/sen1floods11/v2_development_roots/dev_fold_01_usa \
  --output-dir results/event_level_v2/v2a_smoke_usa_seed42 \
  --epochs 1 --batch-size 2 --max-train 8 --max-val 4 \
  --seed 42 --device mps
```

ควรได้ `best_sar_unet.pt`, `history.csv`, `sampled_events_by_epoch.csv`, `run_config_v2a.json` ในโฟลเดอร์ Smoke เท่านั้น

## 5. FULL 3 Folds × 3 Seeds (9 experiments) — หลังผ่าน Smoke

MacBook M2 RAM 8GB: รันทีละ fold/seed ไม่ parallel. โหมด Cloud Colab GPU ให้ตั้ง `DEVICE=cuda` (ต้องใช้ไฟล์และ data-root เดียวกัน, และตรวจ Frozen Protocol เหมือน Local)

```bash
bash m75a_run_v2a_full.sh
```

หรือหากต้องการรันทีละชุด:

```bash
python train_v2a_eventbalanced.py \
  --data-root data/sen1floods11/v2_development_roots/dev_fold_01_usa \
  --output-dir results/event_level_v2/v2a_eventbalanced_seed42/dev_fold_01_usa \
  --epochs 25 --batch-size 2 --crop-size 256 --base-channels 16 \
  --lr 0.0003 --patience 6 --seed 42 --device mps
```

ไฟล์ `m75a_run_v2a_full.sh` รัน 9 ชุดแบบเรียงต่อกันและหยุดเมื่อพบ error. โฟลเดอร์ output ต้องไม่เคยมีผลเดิมอยู่แล้ว — script ป้องกันการ overwrite โดยไม่ตั้งใจ

## 6. Compare DEV เท่านั้นหลังครบทั้ง 9 ชุด

```bash
python m75a_compare_v2a_dev.py
```

หากยังไม่ครบ 9 ชุด จะขึ้น NOT READY และ **ไม่** รายงานผลเปรียบเทียบที่ไม่สมบูรณ์

## ทำไมตอนนี้ยังไม่ใช้ Historical TEST / Thailand?

เพราะ India, Paraguay, Ghana เป็น historical TEST ที่ถูกตรวจสอบไปแล้ว และ Thailand ยังไม่มี independent aligned ground truth ที่เทียบ IoU ได้เหมือน Sen1Floods11. การเลือก V2 จาก TEST จะเป็น data leakage ในการวิจัย

หาก `m70d` verify ไม่ผ่าน ให้หยุดตรวจสอบก่อน train; อย่าแก้ frozen source/CSV/TIFF เพื่อให้ผ่านแบบฝืนๆ
