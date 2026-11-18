# 03 ข้อมูลและการแบ่งตามเหตุการณ์

ประเภท: สไลด์หลัก · เวลาแนะนำ: 75 วินาที

## ประเด็นที่ต้องการให้ผู้ฟังเข้าใจ

243 ภาพคือคลังพัฒนา แต่ละโมเดลฝึกด้วยจำนวนภาพตาม fold

## ข้อความบนสไลด์

**Sen1Floods11: 243 คู่ SAR/LabelHand จาก 7 event prefixes**

| Validation event | TRAIN | VALID |
| --- | ---: | ---: |
| USA | 174 | 69 |
| Sri Lanka | 201 | 42 |
| Spain | 213 | 30 |

กัน Validation event ออกจาก TRAIN ทั้งเหตุการณ์

ใช้ VALID เลือก checkpoint และเปรียบเทียบวิธี จึงรายงานเป็น Development Results

## บทพูดภาษาไทย

ชุดพัฒนามี Mekong 30, Nigeria 18, Pakistan 28, Somalia 26, Spain 30, Sri Lanka 42 และ USA 69 ภาพ แต่เราไม่ได้ฝึกทุกโมเดลด้วย 243 ภาพ ตัวอย่าง fold ของ Sri Lanka ฝึกด้วยอีกหกเหตุการณ์ 201 ภาพ แล้วใช้ Sri Lanka ทั้ง 42 ภาพเป็น Validation วิธีนี้ตรวจเหตุการณ์ที่ไม่ได้อยู่ใน TRAIN ของโมเดลนั้น อย่างไรก็ตาม เราใช้ Validation เลือก epoch และพัฒนาวิธีด้วย จึงยังเรียกเป็น Independent Final Test ไม่ได้ India, Paraguay, Ghana และ Bolivia ไม่อยู่ในคลังพัฒนา V2 นี้

## ภาพหรือตารางและการจัดวาง

ใช้ตาราง TRAIN/VALID เป็นภาพหลัก ไม่จำเป็นต้องเพิ่มแผนที่ประเทศ ตารางสำรองจำนวนภาพราย event อยู่ Appendix D

## หลักฐานสำหรับผู้จัดทำ

Claim IDs: C03, C04, C05

- [Split ที่ตรวจแล้ว](../evidence/verified_splits.csv)
- [CSV ต้นทางของ fold USA](../../data/sen1floods11/v2_development_roots/dev_fold_01_usa/splits/flood_train_data.csv)
- [รายงานตรวจ raster ทุกคู่](../evidence/verified_rasters.csv)

## ขอบเขตการตีความ

เป็น 3 held-out validation events จาก 7 events ไม่ใช่ leave-one-event-out ครบ 7 folds และไม่ใช่ 243 independent events
