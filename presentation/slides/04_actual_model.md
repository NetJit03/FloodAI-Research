# 04 Small U-Net ที่ใช้จริง

ประเภท: สไลด์หลัก · เวลาแนะนำ: 60 วินาที

## ประเด็นที่ต้องการให้ผู้ฟังเข้าใจ

แสดงสถาปัตยกรรมจากโค้ดที่ฝึกจริง และสิ่งที่คงที่ระหว่างวิธี

## ข้อความบนสไลด์

| ส่วนของโมเดล | Channels |
| --- | --- |
| Input | 2: VV, VH |
| Encoder | 16, 32, 64, 128 |
| Bottleneck | 256 |
| Decoder พร้อม Skip connections | 128, 64, 32, 16 |
| Output | 1 logit ต่อพิกเซล |

**1,963,953 parameters** · Sigmoid เป็น P(water) · Threshold 0.50

TRAIN crop 256×256 · VALID ใช้ภาพเต็ม 512×512

## บทพูดภาษาไทย

ทั้งสามวิธีใช้ Small U-Net เดียวกัน Encoder ลดขนาดภาพเพื่อเรียนรู้บริบท ส่วน Decoder เพิ่มความละเอียดและรวม skip features เพื่อคืนตำแหน่งเชิงพื้นที่ โค้ดนี้ใช้ Convolution, GroupNorm และ ReLU โดยเพิ่มขนาดด้วย bilinear interpolation แล้วต่อกับ features ของ Encoder ทั้ง 27 runs ใช้โครงสร้างและจำนวนพารามิเตอร์เดียวกัน Output เป็น logit แล้วใช้ sigmoid และ threshold คงที่ 0.50

## ภาพหรือตารางและการจัดวาง

ใช้ตาราง channels เป็นหลัก หากวาดแผนภาพภายหลัง ให้ยึดรายละเอียดจากตารางนี้และโค้ด SmallUNet ไม่ใช้แผนภาพ U-Net ต้นฉบับแทนโมเดลจริง

## หลักฐานสำหรับผู้จัดทำ

Claim IDs: C06, C07

- [SmallUNet, conv_block และ decode](../../train_sar_unet.py)
- [พารามิเตอร์และ checkpoint ที่ตรวจแล้ว](../evidence/verified_runs.csv)
- [แนวคิด U-Net ต้นฉบับ](https://arxiv.org/abs/1505.04597)

## ขอบเขตการตีความ

Small U-Net เป็น implementation ของโปรเจ็กต์นี้ รายละเอียด channels, normalization และ upsampling ต่างจาก U-Net ต้นฉบับ
