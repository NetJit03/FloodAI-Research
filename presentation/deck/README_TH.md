# แหล่งสร้าง PowerPoint

สร้างด้วย PptxGenJS 4.0.1 ตามวิธีที่ผู้ใช้อนุญาต แทน @oai/artifact-tool ที่ไม่มีใน session นี้

จากโฟลเดอร์รากโปรเจ็กต์:

```bash
node presentation/deck/build_powerpoint.mjs
python3 presentation/deck/validate_powerpoint.py
```

ข้อมูลที่ใช้คือ deck_content.json ซึ่งเตรียมจาก Markdown และ CSV ที่ตรวจแล้ว หากแก้ Markdown หรือหลักฐาน ให้เตรียม deck_content.json ใหม่ด้วย presentation/scripts/prepare_deck_content.py ก่อนสร้าง สคริปต์สร้างจะเขียนทับ PPTX ฉบับ Final จึงควรสำรองไฟล์ที่แก้ด้วยมือแล้ว

กราฟและตารางเก็บเป็นวัตถุ PowerPoint พร้อม embedded workbook สำหรับกราฟ ตัวสร้างเติม error bars แบบ custom จากค่า SD ที่ตรวจแล้ว และนำ orphan content-type declarations ของ PptxGenJS ออก โดยไม่เปลี่ยนความสัมพันธ์ของ slide/master ที่มีอยู่จริง

powerpoint_validation.json บันทึกการตรวจโครงสร้าง ตาราง กราฟ ค่า SD workbook และ Notes ส่วน render_validation.json บันทึกขอบเขตการตรวจภาพ ไม่ถือว่าการตรวจด้วย LibreOffice แทนการเปิดตรวจใน Microsoft PowerPoint ได้ครบทุกพฤติกรรม

PDF ฉบับส่งมอบสร้างโดย LibreOffice 26.8.3 แบบ headless จากสำเนาแอปใน /private/tmp พร้อม Fontconfig ที่ชี้ไปยัง Tahoma ของระบบ ส่วน render_pdf.m ใช้ PDFKit แปลง PDF เป็น PNG เพื่อการตรวจภาพ ไม่ต้องติดตั้ง LibreOffice เพื่อแก้ไข PowerPoint

โฟลเดอร์ .build/ และ renders_* เป็นงานระหว่างสร้าง ไฟล์ส่งมอบอยู่ ../output/ เท่านั้น
