# ผลการตรวจหลักฐานสำหรับสไลด์ FloodAI-Research

ตรวจล่าสุด (Asia/Bangkok): 2026-11-18T00:37:09.066076+07:00

ผลตัวเลขหลักตรงกับผลเดิม: Baseline 0.6143, V2-A 0.5979, V2-B 0.5879 และ Baseline Ensemble 0.6483 จึงใช้เนื้อหาเชิงผลลัพธ์เหล่านี้ได้โดยคงขอบเขต DEV Validation

## ขอบเขตการตรวจที่ทำใหม่

| ส่วน | วิธีตรวจ | ผล |
| --- | --- | --- |
| Frozen files | คำนวณ SHA-256 ของ code, split CSVs และ 243 คู่ SAR/GT แล้วเทียบ local freeze | 500/500 ตรงกัน |
| สถานะ freeze | อ่าน frozen JSON/Markdown และบันทึก manual sign-offs | มี frozen_at และ sign-offs ครบ 4 รายการ ไม่ใช้ audit_report เก่าแทน frozen record |
| Split membership | อ่านทุก TRAIN/VALID/test stub/Bolivia stub ของ 3 DEV folds | 243 unique pairs, 7 prefixes, event-disjoint, reserved groups ไม่อยู่ใน TRAIN/VALID |
| Raster | อ่าน arrays และ metadata ของ 243 คู่ ตรวจ shape, labels, grid และ valid masks | 2×512×512 SAR, 512×512 GT, labels อยู่ใน −1/0/1, band names VV/VH ทุกคู่ |
| Checkpoints | weights_only=True, state_dict strict load, finite weights, parameters, metadata, confusion counts, history epoch และ config | 27/27 ผ่าน ไม่มีการฝึกใหม่ |
| Code consistency | เทียบ AST ของ dataset/model/loss/evaluate/seed functions ระหว่าง Baseline กับ V2-B และตรวจ recorded source hashes | ฟังก์ชันหลักตรงกัน; V2-A import baseline implementation |
| Sampling | ตรวจ V2-A source/exposure logs และ V2-B manifests/weights เทียบ raw TRAIN GT | V2-B เป็น 50/50 mixture ไม่ใช่ห้ากลุ่มเท่ากันทั้งหมด |
| DG summaries | คำนวณ IoU จาก checkpoint TP/FP/FN แล้ว mean events/seeds และ Sample SD | ตรงตาราง M8.1 และตัวเลขที่แสดง |
| Ensemble 141 records | เทียบ membership กับ VALID, raw GT counts/masks, confusion identities และรวม event counts/Brier/UQ ใหม่ | 69/42/30 ภาพ ครบ 141, macro IoU ตรง manifest |
| Stored UQ arrays | อ่าน NPZ เก้าภาพด้วย allow_pickle=False คำนวณ confusion/Brier/Entropy/MI และ top10% capture ใหม่ | ตรง outputs เดิมภายใน tolerance ที่ระบุ |
| CPU re-inference | โหลด Baseline checkpoints 3 seeds ต่อ fold ทำนายภาพ previews ทั้ง 9 ใหม่ | max abs probability difference 5.96e-07; binary disagreements ที่ threshold0.50 = 0 valid pixels |
| Figures | คัดลอก source PNG พร้อม SHA-256, สร้าง data charts และวาด UQ จาก stored NPZ พร้อม colorbars ที่อ่านได้ | 11 รูปพร้อม provenance |

มี automated checks ผ่าน 1366/1366 รายการ ตัวเลขจำนวน checks แสดงขอบเขตการตรวจ ไม่ใช่เปอร์เซ็นต์ความจริงของงานวิจัย

## รายละเอียดที่มีผลต่อการเขียนสไลด์

1. **Freeze มีอยู่จริง:** m70d_audit_report.md เป็นสถานะก่อน freeze ส่วน m70d_frozen_protocol.json/.md เป็นสถานะถัดมา คำกล่าวก่อนตรวจที่สงสัยว่าไม่มี freeze ปิดได้ด้วยไฟล์นี้และ byte hashes ที่ตรงกัน
2. **Checkpoint metadata พร้อมแล้ว:** เอกสาร M8.1 เดิมยังระบุให้ตรวจบน local แต่รอบนี้ตรวจ checkpoint/history/config ใหม่ครบ 27 ตัว ไม่ต้องนำข้อกังวลว่า package ขาด V2-A configs มาเป็นข้อจำกัดปัจจุบัน
3. **V2-B เป็น mixture:** P(i)=0.5/N+0.5/(5*N_bin(i)); bins ใช้ full-chip GT ของ TRAIN และสุ่มคืนตัวอย่าง จำนวน draws ต่อ epoch เท่ากับ N_train
4. **Checkpoint update มี tolerance:** โค้ดรับ epoch ใหม่เมื่อ IoU ดีขึ้นเกิน 1e-5 ไม่ได้ใช้การเลือก maximum แบบไม่สน tolerance
5. **7–16 epochs ที่รันจริง:** 25 คือค่าสูงสุด ไม่ใช่จำนวน epochs ที่ทุก run ฝึกครบ ตรวจ early stopping against history แล้ว
6. **หน่วยและ band order:** official README ระบุ VV/VH และ dB; TIFF descriptions ระบุ VV/VH จริง แต่ TIFF units เป็น None ทั้งคู่ทุกภาพ การมี sign-off ไม่แทนการตรวจ radiometric provenance ทุกขั้นอย่างอิสระ
7. **Grid tolerance:** affine coefficients บางตัวไม่เท่ากันแบบ bitwise แต่ความต่างตำแหน่งมุมภาพสูงสุด 7.91e-11 pixels ต่ำกว่า tolerance 1e-6 pixels มาก ใช้ CRS/dimensions เดียวกัน ไม่ใช่ spatial misalignment ที่มีสาระสำคัญ
8. **Narrative typo และสถานะเก่า:** M8.1 ข้อจำกัดข้อหนึ่งเขียน Indonesia แต่ protocol/splits ระบุ India; README หลักบอก V2-A ยังไม่ฝึก; M8.0B มี next-step เก่าที่ให้ย้อนกลับไป implement V2-B ข้อความเหล่านี้ไม่ใช้กำหนดสถานะปัจจุบัน
9. **USA P<0.1:** ค่าเปอร์เซ็นต์ที่ปัดเป็น 0.00% ยังมี GT-water pixel จำนวน 1 พิกเซล ไม่ควรพูดว่าไม่มีเลย ชุดสไลด์หลักตัดตัวเลขนี้ออกเพราะไม่จำเป็นต่อคำตอบวิจัย

## สิ่งที่การตรวจนี้ยังไม่ครอบคลุม

- ไม่ได้ฝึกโมเดลใหม่ และไม่ได้ทำ inference ใหม่ทุก run × ทุก Validation image
- ผล Ensemble ทั้ง 141 ภาพตรวจจาก stored records เทียบ raw GT และการรวมใหม่; inference ใหม่ทำเฉพาะเก้า previews
- ไม่ได้ตรวจความจริงของ labels ทุกพิกเซลด้วยผู้เชี่ยวชาญ หรือดาวน์โหลดต้นฉบับ remote TIFF มาเทียบ local conversion ทุกขั้น
- ไม่ได้ทำ Historical TEST/Thailand inference และไม่อ้างว่าตรวจ local archive ทุกไฟล์หรือทุก zip อย่างละเอียด
- จำนวนเหตุการณ์ Validation สามเหตุการณ์และ seeds สามค่าไม่พอแทนการยืนยันผลข้ามภูมิภาคทั่วไป
- การมีเอกสาร freeze/hashes ไม่ได้พิสูจน์ประวัติการตัดสินใจของผู้วิจัยนอกบันทึก หรือรับรองข้อมูลปราศจาก label noise

## วิธีตรวจย้อนกลับ

- [claims_and_sources.csv](claims_and_sources.csv): 25 ข้อความหลัก, slide IDs, source และ selector
- [verified_metrics.csv](verified_metrics.csv): 74 ค่าพร้อมหน่วย ขอบเขต และวิธีคำนวณ
- [verified_runs.csv](verified_runs.csv): checkpoints/histories ของ 27 runs
- [source_manifest.csv](source_manifest.csv): source path, size และ SHA-256
- [checks.csv](checks.csv): ผลแต่ละเงื่อนไข ไม่ควรตีความว่า PASS = งานถูกต้อง 100%
- [unresolved_questions_TH.md](unresolved_questions_TH.md): ข้อจำกัดที่ต้องคงไว้ในการสรุป

ข้อมูลบนสไลด์มีสถานะว่า “ตรวจตามหลักฐานและขอบเขตที่ระบุ” ไม่ใช้ข้อความรับรองความถูกต้อง 100%
