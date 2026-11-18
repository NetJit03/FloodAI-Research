# Appendix A รายละเอียดการฝึกและ Sampling

ประเภท: สไลด์สำรอง · เวลาแนะนำ: 60 วินาที

## ประเด็นที่ต้องการให้ผู้ฟังเข้าใจ

เตรียมตอบคำถามด้าน implementation โดยไม่ทำให้สไลด์หลักแน่น

## ข้อความบนสไลด์

| รายการ | ค่าที่ใช้ |
| --- | --- |
| Loss | 0.5 masked BCE + 0.5 soft Dice |
| Optimizer | AdamW, lr 0.0003, weight decay 0.0001 |
| Batch / Max epochs / Patience | 2 / 25 / 6 |
| TRAIN augmentation | Crop 256, H/V flips, rotations 0/90/180/270° |
| VALID | ภาพเต็ม 512, ไม่มี augmentation |
| Normalization preset | VV [−35,5], VH [−40,0], clip แล้ว scale [0,1] |
| Valid pixels | Label ≠ −1 และ SAR ผ่าน finite/nodata mask |

V2-A: P(image i) = 1/(K_events × N_event(i))

V2-B: P(image i) = 0.5/N_train + 0.5/(5 × N_bin(i))

ห้ากลุ่ม V2-B: f=0, 0<f<0.01, 0.01≤f<0.10, 0.10≤f<0.50, 0.50≤f≤1

## บทพูดภาษาไทย

โค้ดใช้ LabelHand −1 เป็น ignore, 0 เป็น land และ 1 เป็น water โดยไม่ใช้ label nodata=0 มาตัด land ทิ้ง แต่ยังใช้ nodata metadata ของ SAR ตรวจ invalid pixels ส่วนช่วง normalization เป็น preset ตามข้อมูลที่เอกสารชุดข้อมูลระบุว่าเป็น dB ตรวจพบชื่อแบนด์ VV/VH ใน TIFF ทุกคู่ที่ใช้ และมี sign-off การตรวจ provenance ที่บันทึกไว้ แต่ metadata หน่วยของ TIFF เองว่าง จึงไม่ควรกล่าวว่าได้ตรวจเทียบกระบวนการ radiometric processing ต้นทางทั้งหมดอย่างอิสระแล้ว

## ภาพหรือตารางและการจัดวาง

ตารางใช้เป็นหน้าสำรอง สามารถแยกสองหน้าถ้าต้องอธิบาย sampler ละเอียด

## หลักฐานสำหรับผู้จัดทำ

Claim IDs: C06, C07, C08, C09, C10, C23

- [โค้ดฝึก](../../train_sar_unet.py)
- [สูตร sampling](../../m76b_water_sampler.py)
- [configs และ checkpoint ทุก run](../evidence/verified_runs.csv)
- [TIFF metadata](../evidence/verified_rasters.csv)

## ขอบเขตการตีความ

การแบ่ง bin ใช้สัดส่วนน้ำใน full chip ของ TRAIN เท่านั้น จำนวนภาพที่เลือกได้จริงอาจไม่ตรงสัดส่วนคาดหมายทุก epoch
