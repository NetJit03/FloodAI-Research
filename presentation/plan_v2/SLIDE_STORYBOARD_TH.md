# โครงเนื้อหานำเสนอ FloodAI-Research ฉบับเรียงเรื่องใหม่

สถานะ: ผู้ใช้อนุมัติให้สร้างตามโครงนี้แล้ว จัดทำชุดนำเสนอ 26 หน้าใน output/ วันที่ 18 พฤศจิกายน 2569 ส่วนงานในแผนอนาคตยังไม่ได้ดำเนินการ

เอกสารนี้ไม่เปลี่ยนผลการทดลอง ไม่แทนที่ทะเบียนหลักฐาน และไม่ประกาศว่าทำงานในแผนอนาคตแล้ว มี 26 หน้าฉบับเต็ม จำนวนหน้าจริงปรับหลังทราบเวลานำเสนอ ไม่บังคับย่อกลับเป็น 12 หน้า

แกนเรื่อง: งานนี้จำแนกน้ำผิวดินจาก SAR และศึกษาความน่าเชื่อถือเมื่อแยกเหตุการณ์ออกจากการฝึก เปรียบเทียบ sampling สามแบบ ตรวจความไวต่อ seed และศึกษาการรวม Baseline หลาย seed กับ uncertainty ขณะนี้มี Development Results แล้ว งานที่ยังขาดคือ independent confirmation และ reference ประเทศไทยที่เหมาะสม

## ส่วนที่ 1: ทำอะไร ทำไมต้องทำ และถามอะไร

### 01 ชื่อและขอบเขตงาน
- ใช้ชื่อหัวข้อวิจัยเดิม: Towards Reliable SAR-Based Flood Mapping: Domain Generalization and Uncertainty Quantification Across Geographic Regions
- คำอธิบายภาษาไทย: ศึกษาความน่าเชื่อถือของการจำแนกน้ำผิวดินด้วย Sentinel-1 SAR เมื่อใช้กับเหตุการณ์ที่แยกจากข้อมูลฝึก
- แสดงชื่อผู้จัดทำ รายวิชา อาจารย์ และวันที่ตามข้อมูลที่ผู้ใช้ยืนยันเท่านั้น
- ภาพ: ตัวอย่าง SAR คู่แผนที่น้ำจากข้อมูลจริง ไม่แสดงพื้นที่สมมติเป็นผลการทดลอง
- จุดเชื่อม: ก่อนดูโมเดล ต้องเห็นว่าความน่าเชื่อถือของแผนที่มีประเด็นอะไร

### 02 เส้นทางของการนำเสนอ
- ห้าช่วง: ปัญหาและคำถาม / ข้อมูลและการทดลอง / ข้อค้นพบ / สถานะปัจจุบัน / แผนจนเสร็จ
- ชี้ว่ารอบนี้นำเสนอผลเบื้องต้นและแผนยืนยันผล
- ภาพ: หัวข้อเรียงลำดับเรียบง่าย ไม่อัดศัพท์เทคนิค
- จุดเชื่อม: เริ่มจากสิ่งที่แผนที่ต้องบอกได้

### 03 ปัญหาที่งานนี้สนใจ
- แผนที่ต้องบอกว่าน้ำอยู่ตรงไหน แต่การพลาดน้ำและการระบุพื้นดินเป็นน้ำเป็นข้อผิดพลาดคนละแบบ
- คำถามด้านความน่าเชื่อถือคือผลเปลี่ยนเพียงใดเมื่อใช้กับเหตุการณ์ที่ไม่ได้ใช้ฝึก และจะรู้ได้อย่างไรว่าบริเวณใดควรตรวจเพิ่ม
- ภาพ: GT/Prediction/Error ของ selected DEV case ที่ตรวจแล้ว ใส่คำอธิบาย water, missed water, false alarm
- ขอบเขต: ผลกระทบเชิงปฏิบัติเป็นแรงจูงใจ ยังไม่ได้วัดประโยชน์ภาคสนามหรือมูลค่าความเสียหาย
- จุดเชื่อม: ต้องนิยามก่อนว่าโมเดลของเราทำนายอะไร

### 04 อินพุตและผลลัพธ์ของโมเดล
- อินพุตจริงมี VV และ VH สองแบนด์ ภาพต้นฉบับ 512×512
- เอาต์พุตคือ P(water) ต่อพิกเซล แล้วใช้ threshold 0.50 เป็น water/non-water
- อธิบาย Ground Truth ว่าเป็นแผนที่อ้างอิง และอธิบายว่าน้ำผิวดินอาจรวมน้ำถาวร
- ขอบเขต: จำแนกน้ำ ณ เวลาถ่ายภาพ ไม่มี rainfall encoder หรือการพยากรณ์น้ำท่วมในอนาคตในการทดลองนี้
- ภาพ: 11_input_vv_vh_gt.png พร้อม probability/prediction ที่เลือกจากเคสเดียวกันหากต้องการเพิ่ม ต้องตรวจ mask/grid และระบุสี
- จุดเชื่อม: เมื่อโจทย์ชัดแล้ว จึงตั้งคำถามวิจัย

### 05 คำถามที่การนำเสนอจะตอบ
- RQ1: การปรับวิธีเลือกภาพระหว่างฝึกช่วยเพิ่ม Water IoU บน DEV events ที่แยกจาก TRAIN หรือไม่
- RQ2: ผลต่างกันตามเหตุการณ์และ random seed เพียงใด และพบลักษณะข้อผิดพลาดใด
- RQ3: Baseline Deep Ensemble ให้ผลอย่างไร และ Entropy/MI ให้ข้อมูลเกี่ยวกับข้อผิดพลาดได้เพียงใด
- อธิบาย seed สั้น ๆ ว่าเป็นการฝึกซ้ำที่เปลี่ยนความสุ่มของการฝึก
- ขอบเขต: เป็นการจัดคำถามเพื่อเล่าผลปัจจุบัน ไม่อ้างว่าเป็น preregistered hypotheses ทั้งหมด
- จุดเชื่อม: แนวคิดที่ใช้มีที่มาจากอะไร

### 06 งานที่ใช้เป็นฐานและสิ่งที่โครงการนี้ตรวจเพิ่ม
- Sen1Floods11: ที่มาของข้อมูลและ labels
- U-Net: แนวคิด encoder/decoder และการรักษาข้อมูลตำแหน่งเพื่อ segmentation
- Deep Ensembles: การรวมโมเดลหลายตัวเพื่อศึกษาผลทำนายและ predictive uncertainty
- สิ่งที่เราต้องตอบด้วยข้อมูลตัวเอง: ผล sampling ภายใต้ Small U-Net และ protocol นี้ ความไวต่อ seed และข้อจำกัด UQ
- ภาพ: ตารางงานเดิม / แนวคิดที่นำมาใช้ / สิ่งที่เราตรวจเอง
- ขอบเขต: เอกสารสามชิ้นเป็นฐาน ไม่ใช่การทบทวน SAR domain generalization ครบทุกงาน ห้ามอ้างว่าไม่มีใครทำมาก่อนจนกว่าจะทบทวนเฉพาะทางเพิ่ม
- จุดเชื่อม: เริ่มจากชุดข้อมูลที่ใช้ทดลองจริง

## ส่วนที่ 2: ข้อมูลและวิธีตอบคำถาม

### 07 ข้อมูลทดลองจริง
- Development pool 243 คู่ SAR/LabelHand จาก 7 event prefixes
- Mekong 30, Nigeria 18, Pakistan 28, Somalia 26, Spain 30, Sri Lanka 42, USA 69
- labels 1=water, 0=land, −1=ignore
- ชี้ว่า 243 คือคลังพัฒนา ไม่ใช่จำนวน TRAIN ของทุก fold และ Mekong ในคลังนี้ไม่ใช่ Thailand pilot
- ภาพ: ชุดตัวอย่าง SAR/GT และจำนวนภาพราย event ไม่ต้องเริ่มจากตัวเลข dataset ทั้งหมด 4,831
- จุดเชื่อม: ข้อมูลที่ฝึกไม่ได้มีองค์ประกอบเท่ากันทุกกลุ่ม

### 08 เหตุผลที่ทดลองปรับ Sampling
- แสดงว่าจำนวนภาพราย event ไม่เท่ากัน และภาพแต่ละภาพมีสัดส่วนน้ำต่างกัน
- ตั้งสมมติฐานสองด้าน: event ที่มีภาพมากอาจมี exposure มากกว่า และ distribution ของ water coverage อาจเกี่ยวข้องกับการเรียนรู้
- อธิบายว่าเหตุผลเหล่านี้จูงใจให้ทดลอง ไม่ได้พิสูจน์ว่าเป็นสาเหตุของ domain shift หรือ seed instability
- ภาพ: สถิติ TRAIN ของ fold ตัวอย่างหนึ่ง เช่น USA fold 174 ภาพ โดยใช้ bins จาก verified_coverage_bins.csv
- จุดเชื่อม: ก่อนเปลี่ยน sampler ต้องกำหนดระบบพื้นฐานให้เหมือนกัน

### 09 ระบบพื้นฐาน Small U-Net
- แสดงเส้นทาง VV/VH ผ่าน encoder, bottleneck, decoder, skip connections แล้วได้ probability map
- อธิบายหน้าที่ของแต่ละส่วนด้วยภาษาสั้น ๆ
- ใช้ architecture เดียวกันทั้งสามวิธี เพื่อศึกษาความแตกต่างของ sampling policy
- TRAIN crop 256×256 และ VALID ภาพเต็ม 512×512 เป็นรายละเอียดรอง
- ภาพ: แผนภาพที่ตรง implementation จริง หลีกเลี่ยงตาราง channels เป็นภาพหลัก เก็บ 1,963,953 parameters และ channels ใน Appendix
- จุดเชื่อม: จะตรวจว่าผลข้ามเหตุการณ์อย่างไร

### 10 การกันเหตุการณ์ออกเป็น Validation
- อธิบาย event-disjoint ว่าภาพของ validation event ไม่อยู่ใน TRAIN ของ fold เดียวกัน
- ตัวอย่าง Fold Sri Lanka: TRAIN 201 ภาพจากอีกหก event prefixes, VALID Sri Lanka 42 ภาพ
- อีกสอง folds: USA TRAIN174/VALID69; Spain TRAIN213/VALID30
- แต่ละ fold ฝึกโมเดลใหม่ VALID ใช้เลือก checkpoint ด้วย ผลทั้งหมดจึงเป็น Development Validation
- ภาพ: แถบ event membership สามแถว พร้อมตัวอย่างหนึ่ง fold ที่อ่านตามได้
- ขอบเขต: ไม่ใช่ cross-validation หมุนครบทั้งเจ็ด events และไม่ใช่ untouched final test
- จุดเชื่อม: เมื่อได้แผนที่แล้วจะให้คะแนนอย่างไร

### 11 เกณฑ์วัดผลที่ต้องเข้าใจก่อนดูตัวเลข
- อธิบาย TP, FP, FN ด้วยภาพน้ำที่ซ้อน GT กับ Prediction
- Water IoU = TP/(TP+FP+FN), สูงขึ้นหมายถึงพื้นที่ทับซ้อนดีขึ้นตามนิยามนี้
- สรุป IoU ราย event จาก confusion counts, เฉลี่ยสาม events เท่ากันต่อ seed แล้วสรุป Mean/Sample SD ข้ามสาม seeds
- Recall ใช้ช่วยอ่านการพลาดน้ำ รายละเอียด Brier/Entropy/MI ค่อยอธิบายในส่วน UQ
- ภาพ: ตัวอย่าง mask ซ้อนกันและลำดับการเฉลี่ย ไม่ให้สูตรกลบความหมาย
- ขอบเขต: IoU 0.6143 ไม่ใช่ classification accuracy 61.43%; SD ไม่ใช่ confidence interval
- จุดเชื่อม: ต่อไปคือสิ่งที่เปลี่ยนระหว่างวิธีทดลอง

### 12 สามวิธีเลือกภาพระหว่างฝึก
- Baseline: shuffle ภาพ TRAIN ตามปกติ
- Event-balanced (V2-A): ปรับโอกาสเลือกให้แต่ละ event มีโอกาสเท่ากันในความคาดหมาย สุ่มคืนตัวอย่าง
- Water-coverage (V2-B): ผสม uniform-image 50% กับ uniform ของห้ากลุ่ม coverage 50% สุ่มคืนตัวอย่าง
- bins ใช้ full-chip GT ของ TRAIN ไม่ใช้ validation labels เพื่อสร้าง sampling weights
- ภาพ: ตัวอย่างเลือกภาพจากข้อมูล TRAIN ชุดเดียวกัน อธิบายก่อนใส่สูตร Appendix
- ขอบเขต: V2-B ไม่ได้ให้ห้ากลุ่มมีจำนวนภาพถูกสุ่มเท่ากันทั้งหมด และ crop coverage อาจต่างจาก full-chip coverage
- จุดเชื่อม: วิธีทั้งสามถูกฝึกซ้ำอย่างไรเพื่อไม่อิงผลครั้งเดียว

### 13 แบบการทดลองที่ใช้เปรียบเทียบ
- 3 methods × 3 seeds (42/123/777) × 3 DEV folds = 27 training runs
- คง architecture, loss, normalization, folds และ threshold หลักเดียวกัน
- รายงานทุก seed รวม seed ที่คะแนนต่ำ ไม่เลือกเฉพาะครั้งที่ดีที่สุด
- ภาพ: ตาราง design แบบอ่านง่าย ไม่แสดง logs ทั้งหมด
- จุดเชื่อม: เริ่มตอบ RQ1 ด้วยผลรวม

## ส่วนที่ 3: ข้อค้นพบทีละคำถาม

### 14 RQ1: Sampling เพิ่มคะแนนรวมหรือไม่
- Mean macro DEV Water IoU: Baseline 0.6143 ±0.0576; V2-A 0.5979 ±0.0457; V2-B 0.5879 ±0.0488
- Baseline มี mean สูงสุดในสามวิธีที่ศึกษา วิธี sampling สองแบบยังไม่เพิ่มคะแนนรวมใน DEV นี้
- ภาพ: กราฟสามแท่งพร้อม Sample SD และป้าย DEV
- ขอบเขต: ไม่อ้างนัยสำคัญ และไม่สรุปว่าทั้งสองวิธีใช้ไม่ได้กับทุกข้อมูล
- จุดเชื่อม: ค่าเฉลี่ยรวมอาจซ่อนความต่างระหว่างเหตุการณ์

### 15 RQ2: ผลต่างกันตามเหตุการณ์และ seed อย่างไร
- แสดงคะแนนราย event โดยเริ่มจาก Baseline เพื่อให้ผู้ฟังอ่านง่าย
- USA และ Spain มีคะแนน Baseline ข้าม seeds ใกล้กันกว่า Sri Lanka ในผลที่มี
- Sri Lanka: seed42 0.7065, seed123 0.7011, seed777 0.3891
- ภาพ: จุดคะแนนสาม seed ต่อ event หรือกราฟที่แสดงแต่ละ run ชัด แทนการสื่อด้วย SD เพียงอย่างเดียว
- ขอบเขต: ต่างตาม validation event และโมเดลประจำ fold ไม่ใช่ข้อพิสูจน์ causal country effect
- จุดเชื่อม: ดูว่าความต่างนี้มีลักษณะอย่างไรในภาพจริง

### 16 กรณีศึกษาการพลาดน้ำใน Sri Lanka
- ใช้ Sri-Lanka_534068, GT มีน้ำ 98.14% ของ valid pixels
- IoU ของสาม seeds ในภาพนี้ประมาณ 0.9917 / 0.9859 / 0.2267
- เริ่มอ่าน GT ก่อน จากนั้นเทียบ predictions และเน้น missed water ของ seed777
- ภาพ: แยกภาพเดิมเป็นส่วนที่อ่านง่าย คงชื่อภาพ สี legend และสัดส่วน ไม่วางแปดช่องเล็ก ๆ โดยไม่อธิบาย
- ขอบเขต: selected case ไม่เป็นตัวแทนทุกภาพ และไม่พิสูจน์ว่าสัดส่วนน้ำเป็นสาเหตุเพียงอย่างเดียว
- จุดเชื่อม: เมื่อผลต่าง seed ต่างกัน การรวม probability จะเป็นอย่างไร

### 17 หลักการ Baseline Deep Ensemble
- ใช้ Baseline สาม seeds ภายใน fold เดียวกัน และเฉลี่ย probability ก่อน threshold
- ตัวอย่างหนึ่งพิกเซล 0.85, 0.90, 0.10 เฉลี่ยประมาณ 0.617 แล้ว threshold0.50
- เป็นการรวม Baseline ไม่ใช่รวม Baseline+V2-A+V2-B
- ภาพ: probability ของสามสมาชิกกับค่าเฉลี่ย แล้วค่อยแสดง final prediction
- ขอบเขต: ห้ามรวมทุก fold เพื่อประเมิน DEV event เพราะสมาชิกจาก fold อื่นอาจฝึกด้วย event นั้น
- จุดเชื่อม: ดูผลที่ได้จริงจากการรวม

### 18 RQ3 ส่วนแรก: ผลของ Ensemble
- Mean single-model macro DEV IoU 0.6143 เทียบ macro DEV Ensemble IoU 0.6483, ผลต่าง0.0340 IoU points
- USA 0.5383→0.5487; Sri Lanka 0.5989→0.6858; Spain 0.7058→0.7105
- ภาพ: paired bars ราย event และข้อความผลหลักหนึ่งประโยค
- ขอบเขต: ค่าเฉลี่ยคะแนนโมเดลเดี่ยวกับคะแนนหลังรวม probability เป็นการคำนวณคนละแบบ เปรียบเทียบเชิงพรรณนา ไม่อ้างชนะทุก seed หรือ independent test
- จุดเชื่อม: Ensemble ยังให้ข้อมูลความไม่แน่นอนจากสมาชิกได้

### 19 ความหมายของ Entropy และ MI
- Predictive Entropy: ความไม่แน่นอนของ probability เฉลี่ย สูงเมื่อค่าเฉลี่ยอยู่ใกล้0.5
- MI: ตัวแทนความเห็นต่างของสมาชิก ตามสูตร entropy ของค่าเฉลี่ยลบค่าเฉลี่ย entropy สมาชิก
- ยกตัวอย่างทุกสมาชิกให้0.5ใกล้กัน กับสมาชิกที่มั่นใจคนละทาง เพื่อให้เห็นว่าทั้งสองค่าไม่ใช่สิ่งเดียวกัน
- ภาพ: ตัวอย่าง probability อย่างง่ายก่อนแผนที่จริง สูตรเต็มเก็บ Appendix
- ขอบเขต: หากสมาชิกผิดเหมือนกันอย่างมั่นใจ MI อาจต่ำ
- จุดเชื่อม: นำความหมายนี้ไปอ่านแผนที่จริงและตรวจขอบเขตหลักฐาน

### 20 RQ3 ส่วนที่สอง: UQ บอกข้อผิดพลาดได้แค่ไหน
- เรียง GT, Prediction/Error, Entropy, MI ของเคสเดียวกัน พร้อมบอกวิธีอ่านสี
- แยกชัด: ผลรวมรายภาพ Ensemble/UQ มี141 DEV images แต่ detailed pixel error capture มี9selected images
- อธิบาย top-10% error capture ว่าเลือกพิกเซล uncertainty สูง10%แล้วดูว่ารวมข้อผิดพลาดได้เท่าไร
- ผลปัจจุบันแสดงข้อจำกัดของการใช้ disagreement เป็นตัวเตือน MI ต่ำไม่ได้ยืนยันว่าทำนายถูก
- ภาพ: selected map อ่านได้และป้าย141/9ที่มองเห็น ตาราง capture ราย event เก็บสำรองถ้าหน้าแน่น
- จุดเชื่อม: รวมคำตอบทั้งสามข้อก่อนรายงานความคืบหน้า

### 21 คำตอบปัจจุบันและข้อจำกัด
- RQ1: sampling ที่ทดลองยังไม่เพิ่มคะแนนรวมบน DEV
- RQ2: พบ event/seed sensitivity โดยมี Sri Lanka เป็นกรณีเด่น
- RQ3: Baseline Ensemble ให้คะแนน DEV สูงขึ้นเชิงพรรณนาและสร้าง UQ maps ได้ การตรวจ error ยังมีข้อจำกัด
- ข้อจำกัดหลัก: สาม validation events, ไม่มี independent final test, selected UQ diagnostics, reference ไทยยังไม่พร้อม
- ภาพ: ตารางคำถาม / คำตอบ / หลักฐาน / ขอบเขต
- จุดเชื่อม: จากข้อค้นพบเหล่านี้ ตอนนี้โครงการอยู่ตรงไหน

## ส่วนที่ 4: ความคืบหน้าและแผนจนเสร็จ

### 22 สถานะโครงการ ณ วันที่นำเสนอ
- เสร็จแล้ว: pipeline SAR-only Small U-Net, development splits/protocol, trainingสามวิธี27runs, event/seed/failure analysis, Baseline Ensemble141DEV, selected pixel UQ9ภาพ และการตรวจหลักฐานรอบล่าสุด
- อยู่ระหว่างปรับ: การเรียบเรียง manuscript/presentation ให้สอดคล้องกับคำถามและผล
- ยังไม่เสร็จ: independent final test, aligned/verified Thailand quantitative GT และรายงานผลขั้นสุดท้าย
- ประโยคหลัก: ขณะนี้เสร็จช่วงพัฒนาและวิเคราะห์ผลเบื้องต้น กำลังจัดการนำเสนอ และเตรียมขั้นยืนยันผลอิสระ
- ภาพ: development / confirmation / final report พร้อมตำแหน่งปัจจุบัน ไม่รายงานเปอร์เซ็นต์สำเร็จที่ไม่มีเกณฑ์
- จุดเชื่อม: ขั้นยืนยันผลต้องทำอะไรต่างจากการประเมินที่ผ่านมา

### 23 แผน Independent Final TEST
- สถานะของหน้านี้คือแผนที่เสนอ ยังไม่มีผลขั้นนี้
- จัดหา labelled events ใหม่ ตรวจการซ้ำกับข้อมูลที่เคยใช้ทั้งด้าน event, เวลา และพื้นที่ ไม่ใช้แค่ชื่อประเทศหรือชื่อไฟล์ตัดสินความอิสระ
- ล็อกวิธีฝึก โมเดลที่เปรียบเทียบ threshold เมตริก และวิธีรวมผลก่อนเปิดดูคะแนน test
- ข้อเสนอสำหรับการเปรียบเทียบสามวิธีขั้นสุดท้าย: ฝึกใหม่บน development pool243ภาพด้วยสามmethods×สามseeds=9final training runs กำหนดจำนวนepochsจากข้อมูลDEVล่วงหน้า แล้วสร้าง Baseline ensembleจากสามseedที่ฝึกชุดเดียวกัน
- ไม่ใช้ TEST เลือก epoch/checkpoint หรือปรับวิธี หากใช้ all243เป็นTRAINต้องกำหนด stopping ruleจากDEVก่อน ไม่มีearly stoppingบนTEST
- ประเมิน frozen final models บนชุดเดียวกันและรายงานทุกวิธี รวมผลที่ไม่สนับสนุนสมมติฐาน
- ขอบเขต: 9finalrunsเป็นข้อเสนอใหม่ ไม่ใช่ส่วนหนึ่งของ27runsที่ทำเสร็จ และรูปแบบนี้ต้องตกลงก่อนเริ่ม confirmation
- จุดเชื่อม: ประเทศไทยต้องเตรียม reference เพิ่มอย่างไร

### 24 แผน Ground Truth และกรณีประเทศไทย
- พิมายปัจจุบันยังเป็น diagnostic pilot ไม่รายงาน accuracy จากการเทียบ UNOSAT ตรง ๆ
- หากคงเป้าหมาย quantitative Thailand validation ให้เลือกเหตุการณ์/เวลา/พื้นที่ใหม่ที่เหมาะกับ confirmation และจัดทำ reference ตามนิยาม surface water ของงาน
- ตรวจเวลา acquisition, CRS, resolution, grid, valid/ignore mask และความครอบคลุม reference แยกน้ำถาวร/น้ำเกิดใหม่เฉพาะเมื่อมีหลักฐานพอ
- จัดผู้ตรวจ label และกติกาจัดการบริเวณกำกวม โดยผู้ทำ reference ไม่เห็น prediction ที่กำลังประเมิน
- เมื่อreferenceไม่ครอบคลุมทั้งภาพ ต้องไม่ถือพื้นที่ที่ไม่มีannotationเป็นlandโดยอัตโนมัติ
- ผลส่งมอบ: SAR/GT pairs, annotation guide, quality-review log, provenance และ independent-test membership ที่ตรวจได้
- ขอบเขต: ถ้าจัดหา reference ไม่ได้ตามคุณภาพ ต้องปรับขอบเขตการอ้างผลไทยร่วมกับอาจารย์ ไม่แทนด้วยคะแนนที่นิยามไม่ตรง
- จุดเชื่อม: รวมทุกงานที่เหลือเป็นขั้นตอนและเกณฑ์จบ

### 25 แผนดำเนินงานจนส่งฉบับสุดท้าย
- A ปิดการเรียบเรียงผลเบื้องต้นและการทบทวนงานที่เกี่ยวข้อง รับ feedback แล้วล็อกคำถาม/ขอบเขต
- B ขยาย pixel-level UQ audit จาก9ภาพเป็น141DEVตามกติกาคงที่ เพื่อใช้กำหนดแผน confirmation โดยยังรายงานว่าเป็นDEV
- C เตรียม independent labelled events และ referenceไทย ตรวจคุณภาพและความเป็นอิสระ
- D Freeze final training/evaluation plan ก่อนคะแนนTEST ทำfinalrunsตามแผน ตรวจartifactsและrunmanifest
- E รันfinalevaluationตามแผน รายงานรายeventและmacro พร้อมข้อผิดพลาดและต้นทุนinference ประเมินUQบนขอบเขตที่ประกาศไว้ทั้งหมด
- F เขียนรายงานfinalตรวจตัวเลข/รูป/ข้อสรุป ทำreproducibilitypackageและสไลด์สุดท้าย
- ภาพ: ตารางขั้นตอน / สิ่งที่ทำ / สิ่งส่งมอบ / เงื่อนไขผ่าน ดูรายละเอียดด้านล่าง
- ไม่ใส่วันที่หรือจำนวนสัปดาห์เป็นคำรับปากจนทราบวันส่งงาน ผู้ตรวจlabel และข้อมูลที่จะใช้
- จุดเชื่อม: สรุปสิ่งที่มีแล้วและสิ่งที่จะทำให้ข้อสรุปสมบูรณ์

### 26 ข้อสรุปและสิ่งที่จะส่งเมื่อจบงาน
- มีหลักฐานเชิงพัฒนาเรื่องsampling, seed sensitivity และ Baseline Ensemble/UQ แล้ว
- ขั้นยืนยันผลคือทดสอบบน independent labelled events โดยล็อกprotocolและมีreferenceที่สอดคล้องกับtarget
- สิ่งส่งมอบสุดท้าย: คำตอบวิจัยที่ระบุขอบเขต, ผลfinalevaluation, บทวิเคราะห์ข้อผิดพลาด, code/config/splits/runmanifest, manuscriptและpresentation
- ประโยคปิด: งานส่วนที่เหลือมุ่งยืนยันความน่าเชื่อถือของข้อค้นพบด้วยข้อมูลอิสระและจัดทำรายงานให้ตรวจย้อนกลับได้
- ไม่ใช้เงื่อนไขว่าคะแนนต้องดีขึ้นจึงถือว่างานเสร็จ

## เกณฑ์จบของแผนงาน

| ขั้น | วิธีทำ | สิ่งส่งมอบและเงื่อนไขผ่าน |
| --- | --- | --- |
| A คำถามและเนื้อหา | ผูกRQกับผล ตรวจงานที่เกี่ยวข้องเฉพาะSAR/DGเพิ่มเติม และแยกDEVจากTEST | outline/manuscriptที่ระบุข้อกล่าวอ้างและขอบเขตตรงกัน อาจารย์รับทราบขอบเขตfinal |
| B Full DEV UQ | สร้างหรือคำนวณprobability/error/UQครบ141ภาพด้วยกติกาเดียวกัน ไม่มีเลือกตามผล | ครบ141 recordsและvalid masks สรุปรายeventและcase selectionที่ประกาศไว้ ยังคงป้ายDEV |
| C Independent reference | ตรวจoverlapทั้งevent/time/footprint จัดannotationguidelineและreviewlabel | SAR/GT/masksตรงกัน มีprovenanceและQC ชุดconfirmationไม่เคยใช้เลือกวิธี |
| D Frozen final experiment | กำหนดmethods/seeds/epochs/threshold/metrics/aggregationก่อนtest ฝึกและตรวจfinalartifacts | protocol+hashes+runmanifest ผลแต่ละrunครบและโหลดได้ ไม่มีtest-basedselection |
| E Final evaluation | รันตามprotocol รายงานIoU/RecallและUQตามแผน รวมทุกeventไม่เลือกทิ้งจากคะแนน | ตารางคะแนนครบพร้อมsample sizes การรวมระดับeventถูกต้อง ข้อสรุปไม่เกินจำนวนevents |
| F ส่งงาน | อัปเดตMethods/Results/Discussion/Limitations เชื่อมตัวเลขกับแหล่งและซ้อมนำเสนอ | manuscript, presentation, figures, scripts/configs/splits/manifests และคำตอบRQตรงกัน |

จำนวน independent events ต้องกำหนดตามขอบเขตการอ้างผลและข้อมูลที่หาได้ก่อนประเมิน หนึ่งเหตุการณ์ใหม่ให้เพียง confirmationเฉพาะกรณี ไม่พอรองรับข้ออ้างทั่วไปว่าทำงานได้ข้ามภูมิภาคทั้งหมด หากต้องการช่วงความเชื่อมั่นต้องออกแบบโดยคำนึงถึงการพึ่งพากันภายในเหตุการณ์ ไม่ถือพิกเซลหรือสามseedsเป็นภูมิภาคอิสระจำนวนมาก

## Appendix ที่เตรียมไว้ตอบคำถาม

1. ตารางครบ27runsและผลรายevent/seed
2. Small U-Net implementation, channels, parameters และtrainingconfig
3. สูตรsamplingและขอบเขตwater-coveragebins
4. สูตรIoU/Recall/Brier/Entropy/MI และaggregation
5. Learningcurvesและselectedfailurecasesเพิ่มเติม
6. Full141 versus selected9 UQ tablesและวิธีtop10%capture
7. HistoricalTEST India/Paraguay/Ghana, Bolivia และเหตุผลที่ไม่ใช้เป็นpristineV2confirmation
8. Phimai pilotและข้อจำกัดreference
9. Frozenprotocol, provenance และผลตรวจหลักฐาน
10. References

## หลักฐานที่ใช้กำหนดสถานะและตัวเลข

- ../evidence/verification_report_TH.md และ unresolved_questions_TH.md ใช้สถานะล่าสุด แก้ข้อความเก่าในM8.1เรื่องcheckpointauditและชื่อIndiaตามหลักฐานนี้
- ../evidence/verified_models.csv, verified_events.csv, verified_runs.csv, verified_high_water_cases.csv, verified_ensemble_events.csv, verified_selected_uq_events.csv
- ../../results/event_level_v2/m81_integrated_dev_evidence/m81_report_th.md
- ภาพและprovenanceใน ../assets/figures/ และ ../assets/FIGURE_GUIDE_TH.md

แหล่งแนวคิดที่เปิดตรวจซ้ำ18พฤศจิกายน2569:
- Sen1Floods11 repository: https://github.com/cloudtostreet/Sen1Floods11
- U-Net: https://arxiv.org/abs/1505.04597
- Deep Ensembles: https://papers.neurips.cc/paper/2017/hash/9ef2ed4b7fd2c810847ffa5fa85bce38-Abstract.html

ก่อนจัดหน้าต้องตรวจแหล่งเฉพาะสำหรับคำอธิบายคุณสมบัติSARและเพิ่มการทบทวนSAR/DGตามที่ใช้จริง ไม่สรุปความใหม่ของงานจากเอกสารฐานสามชิ้นเพียงอย่างเดียว
