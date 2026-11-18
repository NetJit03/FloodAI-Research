# 06 การทดลองและเกณฑ์เปรียบเทียบ

ประเภท: สไลด์หลัก · เวลาแนะนำ: 60 วินาที

## ประเด็นที่ต้องการให้ผู้ฟังเข้าใจ

บอกจำนวนการฝึก หน่วยวัด และลำดับการเฉลี่ยให้ชัด

## ข้อความบนสไลด์

**3 วิธี × 3 seeds × 3 folds = 27 runs**

Seeds: 42, 123, 777

1. ภายในแต่ละ event: รวม TP, FP, FN ของ valid pixels แล้วคำนวณ Water IoU
2. ภายในแต่ละ seed: เฉลี่ย IoU ของสาม Validation events แบบให้น้ำหนักเท่ากัน
3. รายงานค่าเฉลี่ยและ Sample SD ข้ามสาม seed macro scores

เลือก checkpoint จาก VALID IoU · Threshold คงที่ 0.50

## บทพูดภาษาไทย

คะแนนหลักมีสองระดับการรวม ภายในเหตุการณ์เราใช้ confusion counts รวมทุกภาพ ไม่ได้เฉลี่ย IoU รายภาพ จากนั้นเฉลี่ยสามเหตุการณ์โดยให้น้ำหนักเหตุการณ์เท่ากัน แล้วเฉลี่ยอีกครั้งข้าม seeds Error bars ที่จะแสดงคือ Sample SD ของ seed macro scores สามค่า ไม่ใช่ confidence interval จากเหตุการณ์จำนวนมาก ในโค้ด checkpoint จะอัปเดตเมื่อ VALID IoU ดีขึ้นเกิน 0.00001 และหยุดเมื่อไม่ดีขึ้นหก epochs หรือครบ 25 epochs

## ภาพหรือตารางและการจัดวาง

ใช้สมการ IoU = TP/(TP+FP+FN) หนึ่งบรรทัดคู่กับขั้นตอนการเฉลี่ย ไม่ต้องใส่ loss curves บนหน้านี้

## หลักฐานสำหรับผู้จัดทำ

Claim IDs: C07, C11, C12

- [คะแนนและ epoch ของ 27 runs](../evidence/verified_runs.csv)
- [Seed macro scores](../evidence/verified_seed_macros.csv)
- [evaluate และ checkpoint update](../../train_sar_unet.py)

## ขอบเขตการตีความ

IoU 0.6143 ไม่ใช่ Accuracy 61.43% จำนวน seeds เป็นการฝึกซ้ำ ไม่ใช่จำนวนพื้นที่อิสระ
