# ประเด็นที่ยังไม่ยืนยันและผลต่อการนำเสนอ

ประเด็นเหล่านี้ไม่ทำให้ต้องหยุดนำเสนอ Preliminary Results แต่จำกัดขอบเขตที่อ้างได้

| ประเด็น | สิ่งที่ตรวจได้แล้ว | สิ่งที่ยังขาด | ผลต่อสไลด์ |
| --- | --- | --- | --- |
| Independent Final TEST | Split V2 กัน India/Paraguay/Ghana/Bolivia ออก และใช้ USA/Sri Lanka/Spain เป็น VALID | หลักฐาน final evaluation บน labelled events ที่ไม่เคยใช้ประกอบการพัฒนา | ทุกผลหลักระบุ DEV Validation |
| Thailand quantitative validation | บริบทเดิมระบุพิมายเป็น pilot และมีข้อจำกัด UNOSAT เทียบ surface water | Reference ที่สอดคล้องด้านพื้นที่ เวลา นิยาม และตรวจอย่างอิสระหลายเหตุการณ์ | ไม่แสดง Thailand accuracy/Water IoU และไม่อ้างผลครอบคลุมประเทศไทย |
| Full UQ error detection | ตารางระดับภาพ 141 ภาพ และ arrays ที่ตรวจซ้ำ 9 ภาพ | Pixel-level benchmark ที่เป็นตัวแทนของ 141 ภาพ หรือ independent events | Error capture ระบุ selected 9 only |
| สาเหตุ Sri Lanka instability | คะแนนและภาพแสดง seed sensitivity และ missed water | การทดลองที่แยกสาเหตุ เช่น exposure/crop distribution/optimization/scene properties | บอกว่าเป็นข้อสังเกตและสมมติฐาน |
| Statistical significance | มีสาม seed macro scores และ Sample SD | จำนวนเหตุการณ์อิสระและแผนอนุมานที่เพียงพอ | ไม่เรียก SD ว่า confidence interval และไม่อ้าง significant improvement |
| ความตรงของต้นทาง SAR/GT | 243 คู่มี band names VV/VH, shape/grid/labels ผ่านตรวจ และ hash ตรง local freeze | การตรวจ label โดยผู้เชี่ยวชาญและ local conversion/download provenance เทียบต้นฉบับทั้งหมดอย่างอิสระ | ใช้หน่วย dB ตามเอกสารและ preset ของโค้ด พร้อมคงข้อจำกัด provenance |
| การทำนายซ้ำทั้งประชากร | Checkpoints ทั้ง 27 ตรวจ metadata/state shapes/finite weights และผลรายภาพ Ensemble รวมได้ตรง 141 ภาพ | รอบนี้ทำนายใหม่เพียง 9 previews ไม่ใช่ทุก run × ทุก validation image | แยก recomputed summaries ออกจาก full inference replication |
| ความน่าเชื่อถือการตัดสินใจ | มี Entropy/MI/Brier และตัวอย่างข้อผิดพลาด | Prospective calibration/rejection audit และต้นทุน false negatives ในการใช้จริง | อธิบาย UQ เป็นสัญญาณตรวจเพิ่ม ไม่รับรองความปลอดภัย |
| ผลประโยชน์เชิงเศรษฐกิจ | มีแนวคิดช่วยจัดลำดับการตรวจพื้นที่ | ผลวัดต้นทุน ประโยชน์ และการใช้งานภาคสนาม | ใช้คำว่าศักยภาพ ไม่กล่าวว่าพิสูจน์ว่าลดความเสียหายแล้ว |

ข้อมูลส่วนบุคคลก่อนจัดหน้าจริง: เติมชื่อผู้จัดทำ รหัส และตรวจชื่อมหาวิทยาลัย/รายวิชาให้ตรงเอกสารของผู้ใช้ ระยะเวลา 13 นาทีเป็นข้อเสนอจัดเรื่อง ไม่ใช่ข้อกำหนดรายวิชาที่ตรวจยืนยันแล้ว

หลักฐาน local configs และ hashes สอดคล้องกับการใช้ DEV-only ตามที่บันทึก แต่การตรวจไฟล์ไม่สามารถพิสูจน์ประวัติการตัดสินใจทุกอย่างของผู้วิจัยหรือรับรองว่าไม่มีการใช้ข้อมูลนอกบันทึกได้
