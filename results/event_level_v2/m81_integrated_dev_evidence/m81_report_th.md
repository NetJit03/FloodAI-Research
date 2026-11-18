# M8.1 — บูรณาการผล Domain Generalization และ Uncertainty Quantification (DEV ONLY)

**Source mode:** BUNDLED_REFERENCE_SNAPSHOTS. **No new training, inference, threshold tuning or TEST access.**

## 1. Research question และขอบเขต

การเรียนรู้จากเหตุการณ์น้ำท่วมหลายพื้นที่ช่วยให้โมเดลตรวจจับ surface water ได้ดีขึ้นบน DEV validation events ที่แยกจาก TRAIN และระดับ uncertainty ของ ensemble ช่วยระบุความผิดพลาดที่ควรตรวจสอบต่อได้เพียงใด?

ข้อมูล M7.6D ใช้ **3 seeds × 3 DEV events × 3 methods**. ส่วน M8.0A เป็น Deep Ensemble ของ **Baseline checkpoints 3 seeds ต่อ event**, ใช้ 141 DEV chips; M8.0B มีรายงานระดับภาพครบ 141 และ pixel-level selected-preview analysis เพียง **9 ภาพที่เลือกไว้**.

## 2. DG: เปรียบเทียบ single-model methods

| Method | Mean macro DEV IoU across seeds | SD of seed macro means | Paired mean Δ vs Baseline |
|---|---:|---:|---:|
| Baseline U-Net | 0.6143 | 0.0576 | +0.0000 |
| V2-A Event-balanced | 0.5979 | 0.0457 | -0.0164 |
| V2-B Water-coverage | 0.5879 | 0.0488 | -0.0264 |

ตัวเลขนี้คือ **mean of each seed's 3-event macro IoU**. ทั้งสาม seeds ไม่ใช่ independent geographical replications. Baseline มี mean DEV score สูงสุด แต่ผล Sri Lanka ข้าม seeds ยังไม่เสถียร จึงไม่อ้างว่า generalize ได้แน่นอน.

## 3. Ensemble Baseline vs methods แยกพื้นที่

| DEV event | Chips | Baseline mean | V2-A mean | V2-B mean | Baseline ensemble | Ensemble − Baseline mean |
|---|---:|---:|---:|---:|---:|---:|
| USA | 69 | 0.5383 | 0.5381 | 0.5384 | 0.5487 | +0.0104 |
| Sri Lanka | 42 | 0.5989 | 0.5486 | 0.5090 | 0.6858 | +0.0869 |
| Spain | 30 | 0.7058 | 0.7071 | 0.7164 | 0.7105 | +0.0047 |

Macro average over the three DEV event ensemble IoUs = **0.6483**; corresponding baseline mean of per-seed macro IoU = **0.6143**; difference **+0.0340**. นี่เป็นความแตกต่างเชิงพรรณนา ไม่ใช่การพิสูจน์นัยสำคัญหรือการประเมินบน independent TEST. Deep Ensemble มีต้นทุน inference สูงกว่าโมเดลเดี่ยว.

**Sri Lanka:** V2-B mean IoU 0.5090 เทียบ Baseline mean 0.5989; Baseline Deep Ensemble IoU 0.6858. ต้องแยกให้ชัดว่า ensemble ไม่ได้เป็น V2-B+UQ; ไม่มีผล UQ จาก V2-A/V2-B สำหรับการเปรียบเทียบโดยตรง.

## 4. UQ (full 141 DEV images, event-aggregated)

| Event | Ensemble recall | Brier | Mean predictive entropy (bits) | Mean ensemble MI (bits) | GT water P(water)<0.1 |
|---|---:|---:|---:|---:|---:|
| USA | 0.7049 | 0.0420 | 0.6349 | 0.0511 | 0.00% |
| Sri Lanka | 0.7311 | 0.0451 | 0.5180 | 0.0335 | 3.75% |
| Spain | 0.8128 | 0.0338 | 0.2988 | 0.0085 | 8.28% |

Brier เป็น pixel-aggregated error over evaluable DEV pixels; ค่าที่ต่ำไม่ได้รับประกันว่าจับน้ำได้ดีในทุกเหตุการณ์. Entropy แสดง predictive uncertainty, MI เป็นตัวแทน disagreement ระหว่างสมาชิก ensemble เท่านั้น ไม่สามารถแยกสาเหตุ uncertainty ได้อย่างเด็ดขาด. หลีกเลี่ยงการเปรียบเทียบค่า mean entropy ระหว่างพื้นที่โดยไม่คำนึงถึง water prevalence.

## 5. UQ error-detection audit (ONLY nine selected previews)

| Event | Selected images | Selected-only ECE | Entropy top-10% error capture | MI top-10% error capture |
|---|---:|---:|---:|---:|
| USA | 3 | 0.1510 | 82.4% | 2.4% |
| Sri Lanka | 3 | 0.3090 | 48.7% | 11.5% |
| Spain | 3 | 0.0195 | 46.4% | 34.5% |

ตัวเลข ECE และ top-10% error capture ในตารางนี้ **ไม่ใช่สถิติของ DEV ทั้ง 141 ภาพ**. ภาพเลือกเฉพาะ 9 ตัวอย่าง ไม่ได้สุ่มอย่างเป็นตัวแทน. การจับพิกเซลผิดด้วย MI ต่ำไม่ได้หมายความว่ามีข้อผิดพลาดน้อย: model disagreement สามารถต่ำเมื่อ ensemble ทำนายผิดเหมือนกันทั้งหมด.

## 6. ข้อจำกัดเชิงระเบียบวิธี

1. USA/Sri Lanka/Spain คือ **DEV validation** ซึ่งถูกใช้เลือก checkpoints และประเมินวิธี ไม่ใช่ untouched independent TEST; Indonesia/Paraguay/Ghana historical TEST, Bolivia และ Thailand ไม่ได้ถูกใช้ในขั้นตอนนี้.
2. Mean of three seed scores (โมเดลเดี่ยว) กับ IoU ของ ensemble aggregated masks เป็นสอง estimands ต่างกัน; รายงานทั้งคู่พร้อมคำอธิบาย.
3. UQ ที่มีอยู่เป็น **Baseline-only** ไม่ใช่การประเมิน UQ สำหรับ V2-A หรือ V2-B.
4. Spatial correlation ของ pixels/chips และจำนวน development events เพียง 3 ทำให้ไม่ควรคำนวณ confidence interval แบบถือ pixels อิสระ.
5. ผล M7.6D เดิมยังต้องตรวจ `m76d_local_checkpoint_audit.py` บน Mac ให้ผ่าน 27/27 ก่อนอ้างว่า checkpoint metadata verified; CSV histories อย่างเดียวไม่พอ.
6. การเปรียบเทียบวิธีที่ใช้ผล DEV เลือก winner แล้วนำผล DEV มาพิสูจน์ winner ซ้ำเป็น selection bias; อธิบายว่าเป็น **development finding**, ไม่ใช่ final performance.

## 7. Research decision (for Nov 19 preliminary presentation)

- รายงาน Baseline U-Net เป็น single-model reference ที่ให้ highest mean macro DEV IoU ในสาม methods ที่ศึกษานี้.
- รายงาน V2-A/V2-B เป็น ablations ของ TRAIN-only sampling ที่ยังไม่ปรับปรุง mean DEV performance โดยรวม.
- รายงาน Baseline Deep Ensemble แสดง higher descriptive DEV macro IoU and uncertainty maps; UQ ต้องรายงานพร้อม failure modes และข้อจำกัด selected-sample.
- ไม่จำเป็นต้องเพิ่ม XAI, MC Dropout, hyperparameter grid search หรือ full pixel-level ECE ก่อน preliminary presentation.
- ขั้นถัดไปที่เหมาะสมคือ M8.2 report/presentation โดยยังคงแผนสำหรับ truly unseen independent labeled event เป็น future final confirmation; Thailand ยังไม่มี comparable verified GT.

**Frozen baseline fingerprint (as recorded in M8.0A):** `dff29456bb921df80dc4d6afd91b266eb830f04092a28c14fd0870a9806a2529`
**Audit:** 141/141 image-level DEV records checked; 3 full events checked; 9 selected preview images flagged.
