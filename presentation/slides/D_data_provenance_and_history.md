# Appendix D ที่มาข้อมูลและบทบาทชุดทดสอบ

ประเภท: สไลด์สำรอง · เวลาแนะนำ: 50 วินาที

## ประเด็นที่ต้องการให้ผู้ฟังเข้าใจ

รักษาประวัติการทดลองโดยไม่ปะปนคะแนนต่างโปรโตคอล

## ข้อความบนสไลด์

| กลุ่มข้อมูล | บทบาทในงานปัจจุบัน |
| --- | --- |
| Mekong 30 / Nigeria 18 / Pakistan 28 / Somalia 26 / Spain 30 / Sri Lanka 42 / USA 69 | Development Pool 243 ภาพ |
| USA / Sri Lanka / Spain | Validation events ของสาม folds |
| India / Paraguay / Ghana | Historical TEST ที่เคยตรวจและช่วยกำหนดคำถามวิจัย |
| Bolivia | Holdout เดิมที่เคยตรวจแล้ว |
| Thailand Phimai | Diagnostic pilot ต้องมี aligned surface-water GT เพิ่ม |

Sen1Floods11 ระบุ hand-labelled 446 ภาพ และ weak-labelled 4,385 ภาพในหมวด flood-event data

การทดลอง V2 นี้ใช้ hand-labelled subset 243 คู่

## บทพูดภาษาไทย

เอกสารทางการมีข้อมูลหลายหมวด รวมทั้ง permanent-water data จึงไม่ควรใช้ผลบวก 446 กับ 4,385 แทนจำนวนทุกไฟล์หรือทุกหมวดใน bucket งานนี้ใช้เฉพาะ subset 243 คู่ที่ตรวจแล้ว ตัว prefix Mekong เป็นชื่อไฟล์และไม่ควรถูกตีความว่าเป็น Thailand test เราแยกผลจากช่วงก่อนหน้าไว้เป็นบริบท เพราะฝึกด้วยข้อมูลและ checkpoints ต่างจากการเปรียบเทียบ V2 ปัจจุบัน

## ภาพหรือตารางและการจัดวาง

ใช้ตารางบทบาทข้อมูล ไม่มีความจำเป็นต้องนำคะแนน Historical TEST ขึ้นก่อนผล V2

## หลักฐานสำหรับผู้จัดทำ

Claim IDs: C02, C03, C05, C21, C22, C25

- [Sen1Floods11 docs](https://github.com/cloudtostreet/Sen1Floods11/blob/master/docs/README.md)
- [Protocol](../../results/event_level_v2/m70d_protocol_freeze/m70d_frozen_protocol.json)
- [แหล่งอ้างอิงและสถานะตรวจ](../evidence/references_TH.md)

## ขอบเขตการตีความ

การแบ่งตาม event prefix ช่วยกันเหตุการณ์ข้าม TRAIN/VALID แต่ไม่ได้พิสูจน์ว่า labels ปราศจากข้อผิดพลาดทุกพิกเซล
