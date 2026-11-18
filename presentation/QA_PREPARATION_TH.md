# เตรียมตอบคำถามอาจารย์

## งานนี้ค้นพบอะไร?

ภายใต้ V2 event-disjoint Development Validation ที่ทดลอง Small U-Net เดียวกัน การถ่วง sampling ตาม event และ water coverage ยังไม่เพิ่ม Macro Water IoU เหนือ Baseline และพบความไวต่อ seed ชัดใน Sri Lanka เมื่อนำ Baseline สาม seeds ต่อ fold มาเฉลี่ย probability ได้คะแนน DEV สูงขึ้นเชิงพรรณนาและแผนที่ Entropy/MI แต่ยังต้องยืนยันบน Independent Test

## ทำไมเรียก FloodAI แต่ทำนาย surface water?

ชื่อโปรเจ็กต์มีบริบทเหตุการณ์น้ำท่วม แต่ target ของ labels คือ water/non-water ณ เวลาภาพ เราจึงตั้งขอบเขตให้ตรง target การแยกน้ำท่วมเกิดใหม่หรือพยากรณ์ล่วงหน้าต้องมี reference และการออกแบบเพิ่ม

## ใช้ข้อมูลฝนหรือโมเดล Transformer หรือไม่?

โมเดลที่นำเสนอใช้ VV/VH สองแบนด์และ Small U-Net ไม่มี rainfall encoder ในการทดลองนี้ โค้ด weather ที่มีอยู่ในโปรเจ็กต์เป็นอีกบริบทหนึ่ง และไม่ควรถือว่าถูกใช้เพียงเพราะพบชื่อไฟล์

## ทำไมใช้ U-Net?

งานต้องทำนายระดับพิกเซลและรักษาตำแหน่งเชิงพื้นที่ U-Net ให้โครงสร้าง encoder/decoder พร้อม skip connections ที่เหมาะเป็น baseline และ implementation ขนาด 1,963,953 parameters นี้ฝึกบนทรัพยากรที่มีได้ งานนี้ไม่ได้ทดลองเปรียบเทียบกับ architecture อื่น จึงไม่อ้างว่า U-Net ดีที่สุด

## 243 ภาพน้อยหรือไม่ และ train กี่ภาพกันแน่?

243 คือ development inventory จาก 7 event prefixes ในแต่ละ fold ฝึก 174, 201 หรือ 213 ภาพ ส่วน Validation 69, 42 หรือ 30 ภาพ ภาพเป็น chips ที่มี spatial correlation จำนวนพิกเซลมากจึงไม่ทดแทนจำนวนเหตุการณ์อิสระ งานยืนยันขั้นสุดท้ายยังต้องมี events เพิ่ม

## นี่เป็น cross-validation ครบทุก event หรือไม่?

เป็นสาม event-disjoint development folds ที่กัน USA, Sri Lanka และ Spain ออกเป็น VALID ตามลำดับ ไม่ได้หมุนครบทั้งเจ็ด events และ VALID ใช้เลือก checkpoint ด้วย จึงไม่อ้างเป็น untouched test

## ทำไมไม่ลบ seed 777 ที่คะแนนต่ำ?

Seed 777 เป็นส่วนหนึ่งของแผนการฝึกซ้ำ และผ่านการตรวจ checkpoint/history เหมือนตัวอื่น ผลต่ำเป็นหลักฐานความไม่เสถียร การตัดออกตามผลจะทำให้ประเมินสูงเกินจริง

## ทำไมใช้ seed เดียวกันแล้วยังเทียบวิธีแบบ paired ได้ไม่สมบูรณ์?

เทียบวิธีตาม fold และ seed เดียวกันได้ในเชิงการจัดการทดลอง แต่ sampler และ replacement เปลี่ยนลำดับและความถี่ของภาพ การใช้ RNG และ crops จึงไม่จำเป็นต้องเหมือนกันทั้งหมด ผลเป็นการเปรียบเทียบ sampling policy ภายใต้ protocol หลักเดียวกัน ไม่ใช่การแยกผลกลไกเดียวแบบสมบูรณ์

## Sampling ไม่ชนะ แปลว่างานล้มเหลวหรือไม่?

คำถามวิจัยคือวิธีเหล่านี้ช่วยหรือไม่ ผลภายใต้เงื่อนไขที่กำหนดยังไม่สนับสนุนว่าช่วยคะแนนรวม การรายงานผลนี้พร้อมความผันผวนและ failure case เป็นข้อค้นพบ ไม่ควรปรับวิธีต่อไปเรื่อย ๆ โดยใช้ชุดเดิมแล้วอ้างเป็นการยืนยันอิสระ

## 0.6143 หมายถึงแม่นยำ 61.43% หรือไม่?

เป็น Macro DEV Water IoU ที่เฉลี่ย event-level pixel-micro IoU แล้วเฉลี่ยข้าม seeds ไม่ใช่ classification Accuracy ผลต่าง Ensemble +0.0340 เป็น IoU points หรือ 3.40 จุดบนสเกล 0–100 ของ IoU ไม่ใช่ accuracy เพิ่ม 3.4% และไม่ใช่การเพิ่มสัมพัทธ์ 3.4%

## Ensemble คือรวมสาม methods หรือเก้า models หรือไม่?

ใช้เฉพาะ Baseline seeds 42/123/777 ภายใน fold เดียวกัน สมาชิกสามตัวไม่เคยฝึกด้วย Validation event นั้น มี Ensemble แยกสาม folds ห้ามรวมทุก fold เพราะสมาชิกจาก fold อื่นอาจเคยใช้ภาพ event ที่กำลังประเมินเป็น TRAIN

## Ensemble ดีกว่า single model แล้วใช่หรือไม่?

คะแนน probability Ensemble สูงกว่าค่าเฉลี่ย single-model scores บน DEV นี้ แต่เป็น estimands ต่างกันและยังไม่มี Independent Test รอบนี้ ไม่อ้างนัยสำคัญหรือการชนะทุก seed ทุกพื้นที่

## Entropy และ MI ต่างกันอย่างไร?

Entropy วัดความไม่แน่นอนของ probability เฉลี่ย ส่วน MI เท่ากับ entropy ของค่าเฉลี่ยลบค่าเฉลี่ย entropy ของสมาชิก และใช้เป็น proxy ของความเห็นต่าง ถ้าทุกตัวผิดอย่างมั่นใจเหมือนกัน MI อาจต่ำ จึงใช้เป็นเครื่องตรวจ error ที่สมบูรณ์ไม่ได้

## UQ ประเมิน 141 ภาพหรือ 9 ภาพ?

ผลรายภาพและผลรวม Ensemble/UQ มี 141 ภาพ ส่วน pixel-level top-10% error capture และ selected ECE มาจาก arrays เก้าภาพที่คัดเลือกไว้ ไม่ใช่ random representative sample ห้ามขยายผลเก้าภาพเป็นทั้ง 141 ภาพ

## ทำไมไม่นำ Historical TEST มาใช้ยืนยัน V2?

ผลเก่าเคยช่วยกำหนดคำถามและการพัฒนางานแล้ว จึงใช้เป็นบริบทและ historical diagnostics แต่ไม่ใช่ pristine confirmation ของวิธีที่พัฒนาต่อมา ต้องมีชุดเหตุการณ์ใหม่ที่ไม่เคยใช้ประกอบการเลือกวิธี

## ทำไมประเทศไทยไม่มีคะแนนในตารางหลัก?

UNOSAT detected-flood extent มีนิยามและเวลาที่อาจต่างจาก exhaustive surface-water mask การนำน้ำที่โมเดลทำนายไปเทียบตรง ๆ อาจนับพื้นที่นอก polygon เป็น FP อย่างไม่สมเหตุสมผล จึงเก็บพิมายเป็น pilot จนมี reference ที่จัดแนวและตรวจได้

## ตรวจความถูกต้องอะไรแล้วในชุดเตรียมสไลด์นี้?

อ่าน verification_report_TH.md: ตรวจ 243 คู่/500 frozen-file hashes, metadata และ history ของ 27 checkpoints, รวมผล 141 Ensemble records ใหม่ และตรวจ arrays เก้าภาพ พร้อมทำนายซ้ำเก้าภาพจาก Baseline checkpoints บน CPU ผล binary ตรงกับไฟล์ MPS เดิมทุก valid pixel ขอบเขตนี้ยังไม่ใช่การฝึกซ้ำทั้งหมดหรือรับรอง labels ทุกพิกเซล

แหล่งตัวเลขและ selector ทุก claim อยู่ [claims_and_sources.csv](evidence/claims_and_sources.csv) และ [verified_metrics.csv](evidence/verified_metrics.csv)
