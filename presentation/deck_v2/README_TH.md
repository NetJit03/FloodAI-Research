# แหล่งสร้างชุดนำเสนอฉบับเรียงเรื่องใหม่

แผนเนื้อหา: ../plan_v2/SLIDE_STORYBOARD_TH.md

สร้าง 26 หน้าด้วย PptxGenJS 4.0.1 ตามการอนุญาตของผู้ใช้ ใช้ tooling จาก ../deck/tooling/ ไม่แก้โค้ดทดลอง ไม่ฝึกโมเดลหรือรัน inference ใหม่

```bash
MPLCONFIGDIR=/private/tmp/floodai-mpl .venv/bin/python presentation/deck_v2/prepare_assets.py
node presentation/deck_v2/build_revised.mjs
python3 presentation/deck_v2/validate_revised.py
```

prepare_assets.py เรนเดอร์ scientific panels จาก arrays ที่เก็บไว้ มี source/output hashes ใน asset_manifest.json และอ่านค่าตรวจ error capture จาก verified_selected_uq_images.csv

build_revised.mjs สร้างข้อความ ตาราง กราฟพร้อม embedded workbooks แผนภาพ native และ speaker notes แล้วเพิ่ม custom SD error bars จากค่าในทะเบียนหลักฐาน พร้อมลบ orphan master content-type declarations ของ PptxGenJS

validate_revised.py เปรียบเทียบค่าใน charts/workbooks/tables กับ manifest และ CSV ที่ตรวจแล้ว ตรวจ Notes และป้าย DEV/selected/future plan รวมถึง package integrity และ layout geometry ผลอยู่ validation.json การตรวจนี้ไม่รับรองว่า labels ทุกพิกเซลเป็นจริงหรือผลทั่วไปทุกพื้นที่

PDF สร้างด้วย LibreOffice 26.8.3 แบบ headless และ explicit Fontconfig ของ Tahoma จากระบบ PNG สำหรับตรวจภาพสร้างด้วย PDFKit โดยใช้ ../deck/render_pdf.m รายละเอียดและขอบเขตการตรวจอยู่ render_validation.json ซึ่งแยกจากการเปิดตรวจใน PowerPoint จริง

หากเปลี่ยนตารางหลักฐาน ต้องอัปเดต ../deck/deck_content.json ให้ตรงก่อนสร้าง ตัวสร้างเขียนทับ PPTX ฉบับใหม่และ SPEAKER_GUIDE_26_TH.md จึงควรสำรองไฟล์ที่แก้ด้วยมือแล้ว

ไฟล์ส่งมอบอยู่ ../output/ ส่วน .build/ และ renders_* เป็นไฟล์ระหว่างการทำงาน
