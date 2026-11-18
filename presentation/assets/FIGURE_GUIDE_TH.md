# ภาพที่เตรียมสำหรับนำเสนอ

คัดภาพหลักให้แต่ละหน้ามีประเด็นเดียว กราฟ 01–05 สร้างใหม่จากตารางที่คำนวณซ้ำ ภาพ 06, 07, 11 คัดลอก PNG ต้นฉบับแบบไม่แก้พิกเซลและตรวจ SHA-256 ภาพ UQ 08–10 วาดจาก NPZ ผลเดิมพร้อม normalized VV ต้นทาง เพื่อให้ชื่อ panel และ colorbars อ่านได้ ค่าผลทำนาย/uncertainty ไม่ได้เปลี่ยน และไม่ใช้ภาพสังเคราะห์

| ไฟล์ | ใช้หน้า | เนื้อหาและวิธีใช้ |
| --- | --- | --- |
| [01_sampling_macro_iou.png](figures/01_sampling_macro_iou.png) | 07 | เปรียบเทียบ macro พร้อม Sample SD ของ seed macros |
| [02_event_iou.png](figures/02_event_iou.png) | 08 | Mean และ Sample SD ข้าม seeds ภายในแต่ละ event |
| [03_sri_lanka_seeds.png](figures/03_sri_lanka_seeds.png) | Appendix B | คะแนนทุก method ตาม seed ของ Sri Lanka |
| [04_ensemble_comparison.png](figures/04_ensemble_comparison.png) | 10 | Mean single-model IoU เทียบ IoU ของ Ensemble |
| [05_selected_error_capture.png](figures/05_selected_error_capture.png) | Appendix C | Capture เฉพาะเก้าภาพที่เลือก ต้องคง selected-only caption |
| [06_sri_lanka_learning_curves.png](figures/06_sri_lanka_learning_curves.png) | สำรอง | VALID IoU/Recall/Precision/Loss ตาม epoch ของ Baseline สาม seeds ใช้ตอบเรื่อง early stopping/variance |
| [07_sri_lanka_seed_failure.png](figures/07_sri_lanka_seed_failure.png) | 09 | SAR/GT/probability/confusion ของ Sri-Lanka_534068 ต้องคง legend |
| [08_sri_lanka_ensemble_uq.png](figures/08_sri_lanka_ensemble_uq.png) | 11 | ตัวอย่างหกช่อง VV/GT/P/prediction/Entropy/MI |
| [09_usa_ensemble_uq.png](figures/09_usa_ensemble_uq.png) | สำรอง | ตัวอย่าง USA เพิ่มเติม ไม่ต้องใส่ใน main ทั้งหมด |
| [10_spain_ensemble_uq.png](figures/10_spain_ensemble_uq.png) | สำรอง | ตัวอย่าง Spain เพิ่มเติม |
| [11_input_vv_vh_gt.png](figures/11_input_vv_vh_gt.png) | 02 | อินพุตสองแบนด์และ GT ของ Sri-Lanka_713926 |

ที่มาภาพและ hash: [figure_sources.csv](figure_sources.csv)

กราฟแกน Y เริ่มที่ 0 และระบุ DEV-only หรือ selected-only ชัดเจน ห้ามตัด caption ที่เปลี่ยนขอบเขตข้อสรุปเมื่อจัด PowerPoint ภาพหลายช่องควรใช้เต็มความกว้างสไลด์เพื่อให้อ่าน legend ได้ หากต้องการ native editable chart ให้ใช้ verified CSV ที่ระบุใน provenance โดยไม่อ่านค่ากลับจากรูป

ไม่มีภาพสังเคราะห์แทนผลวิจัย และไม่มีแผนภาพ U-Net ทั่วไปที่อ้างว่าเป็น architecture จริง หน้า 04 ใช้ตารางจากโค้ด actual implementation
