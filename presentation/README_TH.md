# FloodAI-Research: ชุดเตรียมสไลด์ภาษาไทย

ชุดนำเสนอปัจจุบันปรับใหม่เป็น **26 หน้า** เรียงจากปัญหา ข้อมูล วิธีทดลอง ผล สถานะโครงการ และแผนจนจบงาน มี PowerPoint และ PDF ใน [output/](output/README_TH.md) พร้อม [บทพูดและคำเชื่อม 26 หน้า](plan_v2/SPEAKER_GUIDE_26_TH.md)

ชุดทางเลือก A เดิม 12 สไลด์หลัก + 6 สไลด์สำรอง และทะเบียนหลักฐานยังเก็บไว้ ชุดใหม่ใช้ [โครงเนื้อหาฉบับเรียงเรื่องใหม่](plan_v2/SLIDE_STORYBOARD_TH.md) เป็นแผนหลัก ส่วน slides/ และ SLIDE_CONTENT_ALL_TH.md เป็นเนื้อหาชุดก่อนหน้า

ออกแบบสำหรับ Preliminary Results วันที่ 19 พฤศจิกายน 2569 ชุด 26 หน้าต้องซ้อมและปรับตามเวลาที่ได้รับ ตัวเลข 13 นาทีในแผนเดิมเป็นเพียงข้อเสนอของชุด 12 หน้าหลัก เติมชื่อและรหัสผู้จัดทำบนปกก่อนนำเสนอ

## เริ่มอ่านตรงนี้

1. [แผนการเล่าเรื่องรายหน้า](slides/00_storyline_TH.md)
2. [เนื้อหาทุกหน้ารวมไฟล์เดียว](SLIDE_CONTENT_ALL_TH.md)
3. [ผลตรวจหลักฐานและจุดที่แก้ความเข้าใจเดิม](evidence/verification_report_TH.md)
4. [ภาพที่เลือกและวิธีใช้](assets/FIGURE_GUIDE_TH.md)
5. [เตรียมตอบคำถามอาจารย์](QA_PREPARATION_TH.md)

## วิธีนำไปทำสไลด์

เปิดไฟล์ใน slides/ ตามลำดับ แต่ละหน้ามีส่วน “ข้อความบนสไลด์” ที่พร้อมคัดลอก และ “บทพูดภาษาไทย” สำหรับ speaker notes ภาพอยู่ assets/figures/ ส่วนหลักฐานเก็บไว้ตรวจเองและตอบคำถาม

ใช้ตารางข้อมูลหรือภาพเป็นหลักต่อหน้า ลดข้อความที่ซ้ำกับภาพ เก็บคำว่า DEV Validation และ Selected 9 only ในหน้าที่เกี่ยวข้อง ไม่ต้องนำชื่อ milestone ภายในไปเล่าทุกขั้น หน้า 04 ใช้รายละเอียด Small U-Net จากโค้ดจริง

## ข้อมูลที่ตรวจย้อนกลับได้

- [ข้อกล่าวอ้างและแหล่งข้อมูล](evidence/claims_and_sources.csv)
- [ทะเบียนตัวเลขพร้อมหน่วย/selector/สูตร](evidence/verified_metrics.csv)
- [ผล 27 runs](evidence/verified_runs.csv), [ผลเฉลี่ยสามวิธี](evidence/verified_models.csv)
- [Split counts](evidence/verified_splits.csv), [ตรวจ raster 243 คู่](evidence/verified_rasters.csv)
- [Ensemble event summaries](evidence/verified_ensemble_events.csv), [selected UQ capture](evidence/verified_selected_uq_events.csv)
- [CPU recheck เก้าภาพ](evidence/cpu_preview_recheck.csv), [manifest แหล่งไฟล์](evidence/source_manifest.csv)
- [แหล่งอ้างอิงภายนอก](evidence/references_TH.md), [ข้อจำกัดที่ยังเหลือ](evidence/unresolved_questions_TH.md)

## การสร้างหลักฐานซ้ำ

รันจากโฟลเดอร์ FloodAI-Research โดยใช้ .venv ที่มี torch/rasterio/numpy/matplotlib อยู่แล้ว:

```bash
MPLCONFIGDIR=/private/tmp/floodai-mpl .venv/bin/python presentation/scripts/build_presentation_evidence.py --recheck-previews
python3 presentation/scripts/build_slide_markdown.py
python3 presentation/scripts/finalize_package.py
python3 presentation/scripts/validate_package.py
```

คำสั่งแรกอ่าน code, DEV splits, TIFF, checkpoints และผลเดิม แล้วเขียนผลตรวจ/กราฟเฉพาะ presentation/ มี inference ใหม่เก้าภาพบน CPU ไม่มี training หรือ Historical TEST/Thailand inference คำสั่งสร้าง Markdown จะเขียนทับไฟล์ที่สร้างใน presentation/ จึงควรเก็บสำเนาหากแก้ข้อความเองแล้ว

หากไม่ต้องการ inference ซ้ำ สามารถใช้คำสั่งแรกโดยไม่ใส่ --recheck-previews เพื่อตรวจ evidence บางส่วนได้ แต่การ finalize ชุดเต็มต้องรันพร้อม flag เพื่อไม่อ้างการตรวจจาก cache เก่า

## ขอบเขตที่ต้องคงไว้

คะแนนหลักเป็น Development Validation; ภาพตัวอย่างมี selection bias; ยังไม่ยืนยัน V2 บน Independent Final TEST และไม่รายงาน Thailand quantitative accuracy การตรวจชุดนี้เพิ่มความตรวจสอบย้อนกลับได้ โดยไม่ได้รับรอง labels หรือข้อสรุปวิจัยถูกต้อง 100%

การเปลี่ยนแปลงครั้งนี้อยู่ภายใน presentation/ ไม่แก้ code การทดลอง splits checkpoints หรือรายงานต้นทาง
