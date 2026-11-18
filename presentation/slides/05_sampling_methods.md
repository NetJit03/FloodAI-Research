# 05 วิธีเลือกภาพระหว่างฝึก

ประเภท: สไลด์หลัก · เวลาแนะนำ: 75 วินาที

## ประเด็นที่ต้องการให้ผู้ฟังเข้าใจ

ความต่างที่ตั้งใจทดลองอยู่ที่ TRAIN image sampling

## ข้อความบนสไลด์

| วิธี | การเลือกภาพ TRAIN |
| --- | --- |
| Baseline | Shuffle โดยไม่เลือกภาพซ้ำภายใน epoch |
| V2-A | ถ่วงโอกาสให้แต่ละ event เท่ากันในความคาดหมาย |
| V2-B | ผสม uniform-image 50% กับ uniform-coverage-bin 50% |

V2-A และ V2-B สุ่มแบบคืนตัวอย่าง จำนวนครั้งต่อ epoch เท่ากับ N_train

ทั้งสามวิธีใช้ architecture, loss, folds และ threshold หลักเหมือนกัน

## บทพูดภาษาไทย

Baseline ให้ภาพแต่ละภาพผ่านการเลือกหนึ่งครั้งต่อ epoch แต่แต่ละภาพยังได้รับ crop และ augmentation ใหม่ V2-A ให้แต่ละ event มีมวลความน่าจะเป็นเท่ากัน โดยไม่ได้บังคับจำนวนภาพที่สุ่มได้จริงให้เท่ากันทุก epoch ส่วน V2-B ใช้สัดส่วนน้ำจาก full-chip Ground Truth ของ TRAIN จัดห้ากลุ่ม และผสมการสุ่มสองแบบครึ่งต่อครึ่ง จึงไม่ได้ทำให้ห้ากลุ่มมีมวลเท่ากันทั้งหมด ทั้งสองแบบเลือกภาพซ้ำได้ ต่างจาก Baseline เราจึงตีความผลเป็นผลของ sampling policy ทั้งชุด รวมถึง replacement ด้วย

## ภาพหรือตารางและการจัดวาง

ใช้ตารางเปรียบเทียบสามแถว สูตรและขอบเขตห้ากลุ่มอยู่ Appendix A

## หลักฐานสำหรับผู้จัดทำ

Claim IDs: C08, C09, C10

- [Baseline DataLoader](../../train_sar_unet.py)
- [calculate_weights และ TrackedBalancedSampler](../../train_v2a_eventbalanced.py)
- [water_bin และ probability_for_bin](../../m76b_water_sampler.py)
- [ตรวจ sampling weights จาก TRAIN จริง](../evidence/verified_coverage_bins.csv)

## ขอบเขตการตีความ

กลุ่มของ V2-B เป็น full-chip coverage ไม่ใช่ coverage ของ crop และการใช้ seed เดียวกันไม่ทำให้ augmentation/exposure เหมือนกันทุกวิธี
