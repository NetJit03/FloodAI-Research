# บทพูดและคำเชื่อมรายหน้า

ฉบับ 26 หน้า จัดตามโครงใหม่ ข้อมูลหลักเป็น DEV และหน้าแผนเป็นข้อเสนอที่ยังไม่ได้ดำเนินการ

## 01 FloodAI-Research: ชื่อเรื่องและขอบเขตงาน

งานนี้ศึกษาความน่าเชื่อถือของแผนที่น้ำผิวดินจาก Sentinel-1 SAR โดยดูทั้งผลเมื่อแยกเหตุการณ์ออกจากข้อมูลฝึก และความไม่แน่นอนของผลทำนาย การนำเสนอรอบนี้เป็นผลเบื้องต้นและแผนยืนยันผลขั้นสุดท้าย

**เชื่อมไปหน้าถัดไป:** ผมจะเริ่มจากปัญหาและขอบเขต ก่อนอธิบายการทดลองและผลที่ได้

**ขอบเขต:** ผลเบื้องต้น ยังไม่มี independent final test ในชุดปัจจุบัน

**Sources:**
- presentation/plan_v2/SLIDE_STORYBOARD_TH.md
- train_sar_unet.py

## 02 ลำดับการนำเสนอ

การนำเสนอแบ่งเป็นห้าช่วง เริ่มจากงานนี้ทำอะไรและถามอะไร ตามด้วยข้อมูลและวิธีตรวจคำถาม จากนั้นเป็นผลที่ได้จริง สถานะงานปัจจุบัน และแผนที่เหลือจนส่งงาน รอบนี้ยังไม่ได้มีผล independent final test จึงแยกผลที่ทำแล้วออกจากแผนอนาคตอย่างชัดเจน

**เชื่อมไปหน้าถัดไป:** เริ่มจากปัญหาที่ทำให้การมีแผนที่น้ำเพียงอย่างเดียวยังไม่ตอบเรื่องความน่าเชื่อถือ

**ขอบเขต:** ผลเบื้องต้น ยังไม่มี independent final test ในชุดปัจจุบัน

**Sources:**
- presentation/plan_v2/SLIDE_STORYBOARD_TH.md

## 03 แผนที่น้ำอาจพลาดน้ำหรือระบุน้ำเกินจริง

ภาพนี้เป็นกรณีศึกษาที่เลือกจาก Spain บน DEV เริ่มอ่านจากแผนที่อ้างอิงสีน้ำเงินซึ่งระบุพื้นที่น้ำ แล้วดูผลของ Baseline ensemble พื้นที่สีส้มในภาพข้อผิดพลาดคือน้ำที่โมเดลพลาด ส่วนสีแดงคือพื้นดินที่ทำนายเป็นน้ำ ปัญหาที่เราสนใจจึงมีทั้งความถูกต้องของแผนที่และข้อมูลที่จะช่วยชี้บริเวณที่ควรตรวจเพิ่ม ภาพนี้เป็นตัวอย่าง ไม่ใช่หลักฐานแทนทุกเหตุการณ์

**เชื่อมไปหน้าถัดไป:** ก่อนตรวจความน่าเชื่อถือ ต้องกำหนดให้ชัดว่าโมเดลรับอะไรและทำนายอะไร

**ขอบเขต:** Selected DEV case: Spain_1167260   Baseline Ensemble

**Sources:**
- presentation/plan_v2/SLIDE_STORYBOARD_TH.md
- presentation/deck_v2/asset_manifest.json

## 04 อินพุตสองแบนด์ และความน่าจะเป็นของน้ำ

โมเดลรับ Sentinel-1 SAR สองแบนด์คือ VV และ VH ซึ่งเป็นข้อมูลสองช่องของภาพเดียวกัน ในการทดลองนี้ไม่มีข้อมูลฝน โมเดลให้ความน่าจะเป็นของน้ำต่อพิกเซล แล้วใช้ threshold 0.50 แปลงเป็นแผนที่น้ำและพื้นดิน Target คือ surface water ณ เวลาที่ถ่ายภาพ จึงอาจรวมน้ำถาวรด้วย ภาพตัวอย่างเป็น Sri-Lanka_713926 จาก DEV Ground Truth หมายถึงแผนที่อ้างอิงสำหรับฝึกและตรวจผล

**เชื่อมไปหน้าถัดไป:** เมื่อขอบเขตของระบบชัดแล้ว คำถามวิจัยของเรามีสามข้อ

**ขอบเขต:** Selected DEV example: Sri-Lanka_713926   Target: surface water ณ เวลาถ่ายภาพ

**Sources:**
- presentation/plan_v2/SLIDE_STORYBOARD_TH.md
- train_sar_unet.py
- https://github.com/cloudtostreet/Sen1Floods11

## 05 คำถามวิจัยสามข้อ

คำถามแรกคือการปรับโอกาสเลือกภาพระหว่างฝึกช่วยเพิ่ม Water IoU บน validation events ที่แยกจาก TRAIN หรือไม่ ข้อที่สองคือผลต่างกันตามเหตุการณ์และ seed มากเพียงใด Seed คือการกำหนดความสุ่มในการฝึกซ้ำ เช่นการเริ่มค่าน้ำหนักและการสุ่มข้อมูล ข้อที่สามคือการรวม Baseline หลาย seeds ให้ผลอย่างไร และ uncertainty มีข้อมูลเกี่ยวกับข้อผิดพลาดมากเพียงใด คำถามเหล่านี้ครอบคลุมการวิเคราะห์ปัจจุบัน โดยไม่ได้ลงทะเบียนสมมติฐานทั้งหมดล่วงหน้า

**เชื่อมไปหน้าถัดไป:** ต่อไปคือแนวคิดจากงานเดิมที่ใช้สร้างการทดลองของเรา

**ขอบเขต:** ผลเบื้องต้น ยังไม่มี independent final test ในชุดปัจจุบัน

**Sources:**
- presentation/plan_v2/SLIDE_STORYBOARD_TH.md
- presentation/evidence/claims_and_sources.csv

## 06 งานที่ใช้เป็นฐาน และสิ่งที่เราตรวจเอง

Sen1Floods11 เป็นที่มาของข้อมูลและ labels U-Net ให้แนวคิด encoder และ decoder สำหรับการจำแนกระดับพิกเซล ส่วน Deep Ensembles เป็นฐานแนวคิดของการรวมโมเดลเพื่อศึกษาความไม่แน่นอน งาน UrbanSARFloods ปี 2024 ยังชี้ว่าความไม่สมดุลของข้อมูลและความแตกต่างของบริบทพื้นที่เป็นความท้าทายในงาน SAR flood mapping แต่เราไม่ได้ใช้ dataset หรือจำลองผลของงานนั้น การทดลองของเราจึงตรวจผล sampling และ seed sensitivity ภายใต้ Small U-Net และข้อมูลที่กำหนด ไม่อ้างว่าเป็นการทบทวนวรรณกรรมครบทุกงานหรือเป็นวิธีที่ดีที่สุด

**เชื่อมไปหน้าถัดไป:** เริ่มดูข้อมูลที่ใช้จริงในรอบพัฒนานี้

**ขอบเขต:** ผลเบื้องต้น ยังไม่มี independent final test ในชุดปัจจุบัน

**Sources:**
- presentation/plan_v2/SLIDE_STORYBOARD_TH.md
- https://github.com/cloudtostreet/Sen1Floods11
- https://arxiv.org/abs/1505.04597
- https://papers.neurips.cc/paper/2017/hash/9ef2ed4b7fd2c810847ffa5fa85bce38-Abstract.html
- https://openaccess.thecvf.com/content/CVPR2024W/EarthVision/html/Zhao_UrbanSARFloods_Sentinel-1_SLC-Based_Benchmark_Dataset_for_Urban_and_Open-Area_Flood_CVPRW_2024_paper.html

## 07 ข้อมูลพัฒนา 243 คู่ จาก 7 กลุ่มเหตุการณ์

ข้อมูลที่ใช้จริงใน protocol ปัจจุบันเป็นคู่ SAR และ LabelHand243 คู่จากเจ็ด eventprefixes ไม่ใช่การนำทุกภาพใน dataset มาฝึก แต่ละภาพมีสองแบนด์ VV และ VH และมีแผนที่อ้างอิงคู่กัน Labels คือ 1 น้ำ 0 พื้นดินและลบ 1 บริเวณ ignore Mekong ในคลังนี้เป็นกลุ่มข้อมูลกัมพูชา ไม่ใช่ Thailandpilot จำนวน 243 คือ inventory สำหรับแบ่ง fold และไม่ใช่จำนวน TRAIN ของทุก fold

**เชื่อมไปหน้าถัดไป:** จำนวนภาพแต่ละกลุ่มไม่เท่ากัน และแต่ละภาพก็มีสัดส่วนน้ำต่างกัน

**ขอบเขต:** ผลเบื้องต้น ยังไม่มี independent final test ในชุดปัจจุบัน

**Sources:**
- presentation/plan_v2/SLIDE_STORYBOARD_TH.md
- presentation/evidence/verified_rasters.csv
- https://github.com/cloudtostreet/Sen1Floods11

## 08 ข้อมูลมีสัดส่วนน้ำไม่เท่ากัน

ตัวอย่างนี้ใช้ TRAIN ของ fold ที่กัน USA ออก รวม 174 ภาพ แบ่งภาพด้วยสัดส่วนน้ำใน Ground Truth เต็มภาพ ห้ากลุ่มมี 14,38,70,36 และ 16 ภาพตามลำดับ ภาพในกลุ่ม 1 ถึง 10 เปอร์เซ็นต์จึงพบมากกว่าภาพที่มีน้ำเกินครึ่งภาพ ขณะเดียวกันจำนวนภาพราย event ก็ต่างกัน นี่เป็นเหตุผลให้ทดลองปรับ sampling สองแนวทาง เป็นสมมติฐานเพื่อทดลอง ไม่ใช่ข้อพิสูจน์ว่าความไม่สมดุลเป็นสาเหตุของ seed instability

**เชื่อมไปหน้าถัดไป:** เราจะใช้โมเดลพื้นฐานเดียวกัน แล้วเปลี่ยนเฉพาะsamplingpolicyหลัก

**ขอบเขต:** ตัวอย่าง TRAIN ของ fold USA: 174 ภาพ   แบ่งกลุ่มจาก full-chip GT ของ TRAIN เท่านั้น

**Sources:**
- presentation/plan_v2/SLIDE_STORYBOARD_TH.md
- presentation/evidence/verified_coverage_bins.csv

## 09 Small U-Net สร้างแผนที่รายพิกเซลอย่างไร

Encoder ใช้ convolution เรียนรู้ features จากภาพและลดขนาดเชิงพื้นที่เพื่อเห็นบริบท Bottleneck ประมวลผลระดับลึก Decoder ขยาย features กลับมาสู่ระดับพิกเซล Skipconnections ส่งรายละเอียดจาก encoder มาช่วย decoder จากนั้น outputlogit ผ่าน sigmoid เป็น P(water) สถาปัตยกรรมจริงมี encoder16,32,64,128channels bottleneck256 และ decoder128,64,32,16 รวม 1,963,953parameters ทั้งสามวิธี sampling ใช้ Small U-Net นี้เหมือนกัน TRAIN สุ่ม crop256 ขณะที่ VALID ใช้ภาพเต็ม 512

**เชื่อมไปหน้าถัดไป:** เมื่อโมเดลเหมือนกัน เราจะกันข้อมูลตามเหตุการณ์เพื่อวัดผลอย่างไร

**ขอบเขต:** ผลเบื้องต้น ยังไม่มี independent final test ในชุดปัจจุบัน

**Sources:**
- presentation/plan_v2/SLIDE_STORYBOARD_TH.md
- train_sar_unet.py
- presentation/evidence/verified_runs.csv

## 10 กันหนึ่งเหตุการณ์ออกเป็น Validation

แต่ละแถวคือการฝึกโมเดลใหม่ของหนึ่ง fold สีฟ้าคือ TRAIN สีส้มคือ VALID ตัวอย่างแถว Sri Lanka ฝึกด้วยอีกหกกลุ่ม 201 ภาพและใช้ Sri Lanka42 ภาพเป็น VALID event นั้นจึงไม่อยู่ใน TRAIN ของโมเดลแถวนั้น อีกสอง fold กัน USA และ Spain ตามลำดับ VALID ใช้เลือก checkpoint ด้วยจึงเป็น development validation และนี่ไม่ใช่การหมุนครบทั้งเจ็ด events IndiaParaguayGhana กับ Bolivia ไม่อยู่ใน development pool นี้

**เชื่อมไปหน้าถัดไป:** ต่อไปต้องกำหนดว่าพื้นที่น้ำที่ทำนายตรงกับreferenceมากเพียงใด

**ขอบเขต:** ส้ม = VALID ใช้เลือก checkpoint   ฟ้า = TRAIN   ผลปัจจุบันเป็น Development Validation

**Sources:**
- presentation/plan_v2/SLIDE_STORYBOARD_TH.md
- presentation/evidence/verified_splits.csv

## 11 Water IoU วัดการทับซ้อนของพื้นที่น้ำ

IoU ดูพื้นที่น้ำที่ทำนายถูกเทียบกับพื้นที่ที่เป็นน้ำจริงหรือถูกทำนายเป็นน้ำ TP คือน้ำที่ถูกต้อง FP คือพื้นดินที่ทำนายเป็นน้ำ FN คือน้ำที่พลาด ตารางนี้เป็นภาพอธิบายตำแหน่งของสามประเภท ค่า IoU คำนวณ TP หารด้วย TP บวก FP บวก FN ในผลหลักเรารวม confusioncounts ภายใน event ก่อน เฉลี่ยสาม events เท่ากันต่อ seed แล้วสรุป Mean และ Sample SD ข้ามสาม seeds คะแนน 0.6143 จึงไม่ใช่ accuracy61.43 เปอร์เซ็นต์ กรณี union เป็นศูนย์ให้ NaN

**เชื่อมไปหน้าถัดไป:** ด้วยเกณฑ์นี้ เราจึงเปรียบเทียบวิธีเลือกภาพทั้งสามแบบ

**ขอบเขต:** ผลเบื้องต้น ยังไม่มี independent final test ในชุดปัจจุบัน

**Sources:**
- presentation/plan_v2/SLIDE_STORYBOARD_TH.md
- train_sar_unet.py
- presentation/evidence/verified_seed_macros.csv

## 12 เปลี่ยนโอกาสเลือกภาพระหว่างฝึก

Baseline สลับภาพ TRAIN ตามปกติหนึ่งครั้งต่อ epoch V2A ให้น้ำหนักภาพตามขนาด event เพื่อให้แต่ละ event มีโอกาสถูกเลือกเท่ากันในความคาดหมาย V2B ใช้ส่วนผสมห้าสิบเปอร์เซ็นต์สุ่มภาพแบบ uniform และอีกห้าสิบเปอร์เซ็นต์เลือก coverage bin แบบ uniform แล้วเลือกภาพใน bin ทั้ง V2A และ V2B สุ่มคืนตัวอย่าง จำนวน draws ต่อ epoch เท่ากับ Ntrain ห้ากลุ่มจึงไม่ได้ถูกสุ่มเท่ากันทั้งหมดใน V2B และ weights อ้าง full-chipTRAIN labels เท่านั้น

**เชื่อมไปหน้าถัดไป:** แต่ละวิธีถูกฝึกซ้ำหลายseedและหลายfoldเพื่อไม่อิงผลครั้งเดียว

**ขอบเขต:** ผลเบื้องต้น ยังไม่มี independent final test ในชุดปัจจุบัน

**Sources:**
- presentation/plan_v2/SLIDE_STORYBOARD_TH.md
- train_sar_unet.py
- train_v2a_eventbalanced.py
- m76b_water_sampler.py

## 13 เปรียบเทียบ 27 ครั้งภายใต้กติกาหลักเดียวกัน

สาม methods แต่ละวิธีฝึกด้วย seeds 42,123 และ 777 ครบสาม DEVfolds รวม 27runs ไม่ใช่ 27 สถาปัตยกรรม คงโมเดล lossnormalizationfoldsthreshold และ trainingprotocol หลักเดียวกัน สิ่งที่เปลี่ยนคือ sampling policy การสุ่ม crop และลำดับข้อมูลไม่จำเป็นต้องเหมือนกันทั้งหมดแม้ใช้ seed เลขเดียวกัน เรารายงานทุก seed รวม seed ที่ได้คะแนนต่ำ เพื่อไม่เลือกเฉพาะผลดี

**เชื่อมไปหน้าถัดไป:** เริ่มตอบRQ1ด้วยผลคะแนนรวมของสามวิธี

**ขอบเขต:** ผลเบื้องต้น ยังไม่มี independent final test ในชุดปัจจุบัน

**Sources:**
- presentation/plan_v2/SLIDE_STORYBOARD_TH.md
- presentation/evidence/verified_runs.csv

## 14 RQ1: Sampling ยังไม่เพิ่มคะแนนรวมบน DEV

กราฟนี้แสดง Macro DEV Water IoU เฉลี่ยข้ามสาม seedmacro scores Baseline ได้ 0.6143 V2A0.5979 และ V2B0.5879 เส้น errorbar คือ Sample SD ของสาม seedmacro scores ผลต่างจาก Baseline คือประมาณลบ 0.0164 และลบ 0.0264 ตามลำดับ ภายใต้กติกานี้ Baseline มีค่าเฉลี่ยสูงสุด และยังไม่พบหลักฐานจาก DEV ว่าวิธี sampling ที่ทดลองเพิ่มคะแนนรวม ผลนี้ไม่ใช่ข้อพิสูจน์ว่าสองวิธีใช้ไม่ได้กับข้อมูลทุกชุด และยังไม่อ้างนัยสำคัญทางสถิติ

**เชื่อมไปหน้าถัดไป:** คะแนนรวมอาจซ่อนความแตกต่างระหว่างเหตุการณ์ จึงต้องแยกดูต่อ

**ขอบเขต:** Development Validation   Error bars = Sample SD ข้ามสาม seed macro scores

**Sources:**
- presentation/plan_v2/SLIDE_STORYBOARD_TH.md
- presentation/evidence/verified_models.csv

## 15 RQ2: ความเสถียรต่างกันตามเหตุการณ์

หน้านี้แสดงผล Baseline สาม seeds แยกตาม event USA และ Spain มีคะแนนข้าม seeds ใกล้กันกว่า Sri Lanka ในผลที่มี Sri Lankaseed 42 และ 123 ได้ประมาณ 0.7065 และ 0.7011 แต่ seed 777 เหลือ 0.3891 ตัวเลขนี้แสดงความไวต่อการฝึกซ้ำในบาง event ไม่ได้เป็น causalcountryeffect เพราะแต่ละ event มาจากโมเดลประจำ fold ของตน เราเก็บ seed 777 ไว้ในผลรวมทั้งหมดเพื่อสะท้อนความไม่เสถียรจริง

**เชื่อมไปหน้าถัดไป:** ดูภาพจริงเพื่อเข้าใจว่าคะแนนSriLankaที่ลดลงมีลักษณะอย่างไร

**ขอบเขต:** Baseline เท่านั้น   ทุก seed อยู่ในการรายงาน   แต่ละ event ใช้โมเดลของ fold ตนเอง

**Sources:**
- presentation/plan_v2/SLIDE_STORYBOARD_TH.md
- presentation/evidence/verified_runs.csv
- presentation/evidence/verified_events.csv

## 16 Seed 777 พลาดน้ำมากในภาพตัวอย่างนี้

เริ่มจาก Ground Truth ซึ่งมีน้ำ 98.14 เปอร์เซ็นต์ของ validpixels ในภาพ Sri Lanka534068 จากนั้นเทียบ prediction ที่ threshold0.50 ของสาม seeds สอง seeds แรกครอบคลุมน้ำเกือบทั้งภาพ ส่วน seed 777 ตรวจพบเพียงบางส่วน IoU จึงเป็น 0.9917 0.9859 และ 0.2267 ตามลำดับ นี่เป็น selectedDEVcase ซึ่งอธิบายลักษณะความผิดพลาดได้ แต่ไม่แทนทุกภาพและไม่พิสูจน์ว่าสัดส่วนน้ำเป็นสาเหตุเพียงอย่างเดียว

**เชื่อมไปหน้าถัดไป:** เมื่อผลจากต่างseedsต่างกัน เราจึงศึกษาการรวมprobabilityด้วยBaselineEnsemble

**ขอบเขต:** Selected DEV case: Sri-Lanka_534068   สีน้ำเงิน = น้ำ   สีเทา = พื้นดิน

**Sources:**
- presentation/plan_v2/SLIDE_STORYBOARD_TH.md
- presentation/evidence/verified_high_water_cases.csv
- presentation/deck_v2/asset_manifest.json

## 17 Baseline Deep Ensemble รวมผลอย่างไร

สำหรับ validation event หนึ่ง เราใช้เฉพาะ Baselinecheckpoints ของสาม seeds ที่ฝึกใน fold นั้น แล้วเฉลี่ย P(water)ต่อพิกเซลก่อนใช้ threshold ตัวเลข 0.85 0.90 และ 0.10 ในหน้านี้เป็นตัวอย่างสมมติเพื่ออธิบายการคำนวณ เฉลี่ยได้ประมาณ 0.617 จึงจัดเป็นน้ำที่ threshold0.50 การรวมจริงไม่ได้เอา BaselineV2A และ V2B มารวม และไม่ได้ใช้สมาชิกข้าม fold เพื่อประเมิน DEVevent เพราะสมาชิกจาก fold อื่นอาจเคยฝึกด้วย event นั้น

**เชื่อมไปหน้าถัดไป:** ต่อไปเป็นคะแนนที่ได้จริงจากการรวมBaselineสามseeds

**ขอบเขต:** ตัวอย่างตัวเลขสมมติเพื่ออธิบายวิธี   การทดลองจริงใช้ Baseline 3 seeds ภายใน fold เดียวกัน

**Sources:**
- presentation/plan_v2/SLIDE_STORYBOARD_TH.md
- results/event_level_v2/m80a_dev_ensemble_uq/m80a_members.csv
- https://papers.neurips.cc/paper/2017/hash/9ef2ed4b7fd2c810847ffa5fa85bce38-Abstract.html

## 18 RQ3: Ensemble ให้ Macro DEV IoU สูงขึ้น

Baseline Ensemble ให้ macroDEVIoU0.6483 เทียบกับ mean ของ single-modelmacro IoU0.6143 ผลต่าง 0.0340IoUpoints ราย eventUSA เพิ่มจาก 0.5383 เป็น 0.5487 Sri Lanka จาก 0.5989 เป็น 0.6858 และ Spain จาก 0.7058 เป็น 0.7105 ตัวเลขสองชุดคำนวณต่างกัน ชุดแรกเฉลี่ยคะแนนโมเดลเดี่ยว อีกชุดเฉลี่ย probability ก่อนคำนวณคะแนน เราจึงรายงานเป็นความแตกต่างเชิงพรรณนา ไม่อ้างว่าชนะทุก seed ทุกพื้นที่หรือมีนัยสำคัญ และยังเป็น DEV ที่ใช้เลือก checkpoint แล้ว Ensemble ยังมีต้นทุน inference มากกว่าโมเดลเดี่ยว

**เชื่อมไปหน้าถัดไป:** นอกจากแผนที่เฉลี่ย เราใช้ผลสมาชิกศึกษาความไม่แน่นอนได้ด้วย

**ขอบเขต:** Development Validation   Mean(single-model IoU) และ IoU(mean probabilities) คำนวณต่างกัน

**Sources:**
- presentation/plan_v2/SLIDE_STORYBOARD_TH.md
- presentation/evidence/verified_ensemble_events.csv
- presentation/evidence/verified_models.csv

## 19 Entropy กับ MI วัดคนละลักษณะของความไม่แน่นอน

PredictiveEntropy วัดความไม่แน่นอนของ probability เฉลี่ย โดยสูงเมื่อค่าเฉลี่ยใกล้ 0.5 MI คำนวณ entropy ของค่าเฉลี่ยลบค่าเฉลี่ย entropy ของสมาชิกและใช้เป็นตัวแทน disagreement ในตัวอย่างสมมติแรกทุกสมาชิกให้ 0.5 จึงมี Entropy หนึ่ง bit แต่ MI ศูนย์ ตัวอย่างที่สองให้ 0.95 0.95 และ 0.05 ค่าเฉลี่ย 0.65 มี Entropy ประมาณ 0.9341 และ MI0.6477bits สมาชิกจึงเห็นต่างกัน ทั้งนี้ถ้าสมาชิกมั่นใจผิดเหมือนกัน MI อาจต่ำ จึงไม่ใช่ probability ของการทำนายผิด

**เชื่อมไปหน้าถัดไป:** นำความหมายนี้ไปอ่านแผนที่จริงและดูขอบเขตการตรวจerror

**ขอบเขต:** ตัวอย่างสมมติ   Entropy และ MI ใช้หน่วย bits   MI เป็นตัวแทน disagreement

**Sources:**
- presentation/plan_v2/SLIDE_STORYBOARD_TH.md
- m80a_dev_ensemble_uq.py
- https://papers.neurips.cc/paper/2017/hash/9ef2ed4b7fd2c810847ffa5fa85bce38-Abstract.html

## 20 RQ3: UQ ให้ข้อมูลเพิ่ม แต่ยังพลาดข้อผิดพลาดได้

ภาพนี้เป็น selectedDEVcaseSri Lanka845821 น้ำใน GT มี 97.42 เปอร์เซ็นต์ เริ่มดู GT และข้อผิดพลาดสีส้มคือน้ำที่ Ensemble พลาด แล้วเทียบ Entropy และ MI บนสเกลศูนย์ถึงหนึ่ง bits MI สามารถต่ำได้แม้มี missed water ผล Ensemble และสรุป UQ ระดับภาพมีครบ 141 ภาพ แต่การตรวจ pixel error detection แบบละเอียดมี arrays ที่เลือกไว้เพียง 9 ภาพ ในภาพตัวอย่างนี้ Entropy จับ error ได้ 46.8 เปอร์เซ็นต์ส่วน MI ได้ 2.6 เปอร์เซ็นต์เมื่อเลือก top10 เปอร์เซ็นต์ วิธี top10 เปอร์เซ็นต์ errorcapture คือเลือกพิกเซล uncertainty สูงสุดสิบเปอร์เซ็นต์ภายในแต่ละภาพ แล้วหารจำนวน error ที่จับได้ด้วย error ทั้งหมดในภาพที่เลือก ไม่ขยายผลจาก 9 ภาพไปแทนทั้ง 141 ภาพ

**เชื่อมไปหน้าถัดไป:** เราสามารถกลับมาตอบคำถามสามข้อพร้อมข้อจำกัดได้แล้ว

**ขอบเขต:** Selected DEV case: Sri-Lanka_845821   แผนที่ Entropy/MI ใช้สเกล 0–1 bits

**Sources:**
- presentation/plan_v2/SLIDE_STORYBOARD_TH.md
- presentation/evidence/verified_selected_uq_images.csv
- presentation/evidence/verified_selected_uq_events.csv
- presentation/deck_v2/asset_manifest.json

## 21 คำตอบปัจจุบันและขอบเขตข้อสรุป

RQ1sampling สองแบบยังไม่เพิ่มคะแนนรวมบน DEV RQ2 พบความไวต่อ event และ seed โดยเฉพาะ Sri Lanka RQ3Baseline Ensemble ให้คะแนน DEV สูงขึ้นเชิงพรรณนาและสร้างแผนที่ความไม่แน่นอนได้ แต่ pixel error diagnostics ยังมีข้อจำกัดจากการเลือกภาพ ข้อจำกัดที่ส่งผลต่อการอ้างผลคือมี validation events เพียงสาม events ใช้ VALID เลือก checkpoint และยังไม่มี independent final test การพลาดน้ำในบาง seed เป็นข้อสังเกตที่ยังไม่ได้แยกสาเหตุเชิงทดลอง

**เชื่อมไปหน้าถัดไป:** จากข้อค้นพบเหล่านี้ ผมจะสรุปว่างานถึงขั้นไหนแล้วและยังเหลืออะไร

**ขอบเขต:** ผลเบื้องต้น ยังไม่มี independent final test ในชุดปัจจุบัน

**Sources:**
- presentation/plan_v2/SLIDE_STORYBOARD_TH.md
- presentation/evidence/unresolved_questions_TH.md
- presentation/evidence/verified_models.csv

## 22 ตอนนี้โครงการถึงขั้นไหนแล้ว

ขณะนี้เสร็จขั้นพัฒนาและวิเคราะห์ผลเบื้องต้นแล้ว PipelineSAR-onlySmall U-Net และ protocol พร้อม เปรียบเทียบสาม methods ครบ 27runs มี event / seed / failure analysis รวมถึง Baseline Ensemble141DEVimages และ pixel UQ selected diagnostics9 ภาพ มีการตรวจหลักฐาน checkpoint และผลการทดลองครบตามขอบเขตที่บันทึกไว้ Manuscript และ presentation มีร่างและกำลังปรับการเรียบเรียง ส่วน independent final test และ ThailandquantitativeGT ยังไม่พร้อม เราจึงไม่รายงานเปอร์เซ็นต์ความสำเร็จที่ไม่มีเกณฑ์

**เชื่อมไปหน้าถัดไป:** งานสำคัญถัดไปคือการยืนยันผลบนข้อมูลอิสระภายใต้กติกาที่ล็อกไว้

**ขอบเขต:** สถานะตามหลักฐานในโปรเจ็กต์ ณ 18 พฤศจิกายน 2569

**Sources:**
- presentation/plan_v2/SLIDE_STORYBOARD_TH.md
- presentation/evidence/verification_report_TH.md
- presentation/evidence/unresolved_questions_TH.md

## 23 ขั้นถัดไป: ยืนยันด้วย Independent Final TEST

หน้านี้เป็นแผนเสนอ ยังไม่ได้ทำ final experiment ขั้นแรกคือจัดหา labelled events ใหม่และตรวจ overlap กับข้อมูลเดิมทั้ง event เวลาและ footprint จากนั้นล็อก methodsseedsstopping rulethresholdmetrics และ aggregation ก่อนดูคะแนน TEST ข้อเสนอหากคงการเปรียบเทียบสาม methods คือใช้ development pool243 ภาพฝึก final models สาม methods คูณสาม seeds รวม 9final runs กำหนดจำนวน epochs จาก DEV ล่วงหน้าโดยไม่ earlystop บน TEST และสร้าง Baseline ensemble จากสาม seeds ที่ฝึกชุดเดียวกัน จึงประเมินทุกวิธีบน TEST ชุดเดียวตาม protocol ประวัติ IndiaParaguayGhana และ Bolivia ที่เคยตรวจแล้วไม่ใช่ pristineconfirmation ใหม่ จำนวน events ต้องสอดคล้องกับขอบเขตการอ้างผล

**เชื่อมไปหน้าถัดไป:** สำหรับประเทศไทย การยืนยันเชิงปริมาณต้องเริ่มจากreferenceที่สอดคล้องกับงาน

**ขอบเขต:** แผนเสนอ   ยังไม่ได้ดำเนินการ   9 final runs เป็นงานใหม่ แยกจาก 27 runs ที่เสร็จแล้ว

**Sources:**
- presentation/plan_v2/SLIDE_STORYBOARD_TH.md
- presentation/evidence/unresolved_questions_TH.md

## 24 ประเทศไทยต้องมี Ground Truth ที่ประเมินได้

พิมายปัจจุบันยังเป็น diagnosticpilot เรายังไม่ใช้คะแนนที่เปรียบกับ UNOSAT ตรงๆเป็น accuracy ของงาน surfacewater เพราะนิยามความครอบคลุมและเวลาอาจต่างกัน แผนคือเลือกเหตุการณ์เวลาและพื้นที่ที่เหมาะกับ confirmation จัดทำ reference ตามนิยาม surfacewater ตรวจ CRSresolutiongrid และ validignoremask พร้อมตรวจเวลา acquisition ผู้ทำ reference ควรไม่เห็น prediction ที่กำลังประเมิน ต้องมี annotation guide ผู้ตรวจคุณภาพและกติกาบริเวณกำกวม พื้นที่ที่ไม่มี annotation ไม่ควรถูกถือเป็น land โดยอัตโนมัติ ถ้าจัดหา reference คุณภาพพอไม่ได้ ต้องปรับขอบเขตการอ้างผลไทยร่วมกับอาจารย์

**เชื่อมไปหน้าถัดไป:** นำงานที่เหลือทั้งหมดมาเรียงเป็นขั้นตอนและสิ่งส่งมอบที่ตรวจได้

**ขอบเขต:** แผนเสนอ   พิมายปัจจุบันเป็น Diagnostic Pilot   ยังไม่รายงาน Thailand quantitative accuracy

**Sources:**
- presentation/plan_v2/SLIDE_STORYBOARD_TH.md
- presentation/evidence/unresolved_questions_TH.md

## 25 แผนดำเนินงานจนส่งฉบับสุดท้าย

เริ่มจากรับ feedback และล็อกขอบเขตพร้อมเติม related work จากนั้นขยาย pixel UQ audit ให้ครบ 141DEV ด้วยกติกาคงที่ ยังคงป้าย DEV เตรียม independent reference และ ThailandGT แล้ว freezefinal training / evaluation plan ก่อนคะแนน TEST ทำ final runs และตรวจ artifacts รัน evaluation ครบตาม protocol รายงานราย eventmacro และ UQ พร้อมข้อผิดพลาดและต้นทุน inference สุดท้ายอัปเดต manuscriptfigures และ reproducibility package ก่อนซ้อมนำเสนอ ยังไม่รับปากระยะเวลาเพราะขึ้นกับวันส่งข้อมูลและผู้ตรวจ labels หากจะให้ confidenceinterval ต้องคำนึงถึงการพึ่งพากันภายใน event ไม่ถือพิกเซลหรือ seeds เป็นภูมิภาคอิสระจำนวนมาก

**เชื่อมไปหน้าถัดไป:** ปิดด้วยสิ่งที่มีแล้วและสิ่งที่จะส่งเมื่อโครงการเสร็จ

**ขอบเขต:** แผนเสนอ   ลำดับและเกณฑ์จบ   กำหนดเวลาเมื่อทราบวันส่งและความพร้อมของ reference

**Sources:**
- presentation/plan_v2/SLIDE_STORYBOARD_TH.md
- presentation/plan_v2/SLIDE_STORYBOARD_TH.md

## 26 ข้อสรุปและสิ่งที่จะส่งเมื่อจบโครงการ

ขณะนี้มีหลักฐานเชิงพัฒนาเรื่อง sampling ความไวต่อ seed และ Baseline EnsembleUQ แล้ว ขั้นที่เหลือมุ่งยืนยันข้อค้นพบด้วย independent labelled events และ reference ที่สอดคล้องกับ target สิ่งส่งมอบสุดท้ายคือคำตอบ RQ ที่มีขอบเขตชัด ผล finalevaluation และ erroranalysis manuscriptpresentation และ codeconfigsplitrun manifest ที่ตรวจย้อนกลับได้ เกณฑ์จบงานคือคำถามวิจัยได้รับคำตอบตามหลักฐานและขอบเขตที่ตกลงไว้ ไม่กำหนดว่าคะแนนต้องดีขึ้นจึงถือว่าเสร็จ

**เชื่อมไปหน้าถัดไป:** ขอบคุณครับ พร้อมรับคำแนะนำเกี่ยวกับขอบเขต confirmation และแผน reference ประเทศไทย

**ขอบเขต:** ผลเบื้องต้น ยังไม่มี independent final test ในชุดปัจจุบัน

**Sources:**
- presentation/plan_v2/SLIDE_STORYBOARD_TH.md
- presentation/plan_v2/SLIDE_STORYBOARD_TH.md
