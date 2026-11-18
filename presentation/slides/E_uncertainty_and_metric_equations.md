# Appendix E นิยามเมตริกและความไม่แน่นอน

ประเภท: สไลด์สำรอง · เวลาแนะนำ: 45 วินาที

## ประเด็นที่ต้องการให้ผู้ฟังเข้าใจ

ใช้ตอบคำถามเกี่ยวกับสูตรโดยไม่เพิ่มภาระบนสไลด์หลัก

## ข้อความบนสไลด์

Water IoU = TP / (TP + FP + FN)

Recall = TP / (TP + FN)

P̄ = (P₄₂ + P₁₂₃ + P₇₇₇) / 3

H(P̄) = −P̄ log₂(P̄) − (1−P̄) log₂(1−P̄)

MI = H(P̄) − mean_member H(P_member)

Brier = mean_valid_pixels (P̄ − y)²

IoU เมื่อ union=0 ให้ NaN

Error capture = จำนวน error ใน top-10% uncertainty / จำนวน error ทั้งหมดของภาพที่เลือก

## บทพูดภาษาไทย

Entropy ใช้ฐานสองและมีค่าสูงสุดหนึ่ง bit สำหรับปัญหา binary โค้ด clip ค่า probability เล็กน้อยเพื่อหลีกเลี่ยง log(0) และ clamp MI ที่ติดลบจากความคลาดเคลื่อนเชิงตัวเลขให้เป็นศูนย์ MI วัดความต่างของสมาชิกที่เรามี ไม่ได้พิสูจน์ว่ารู้ uncertainty ทุกแหล่ง เมื่อสมาชิกมั่นใจและผิดตรงกัน ทั้ง Entropy และ MI อาจต่ำได้

## ภาพหรือตารางและการจัดวาง

จัดสูตรเป็นข้อความหรือสมการ editable ภายหลัง ไม่ต้องแปลงเป็นภาพสังเคราะห์

## หลักฐานสำหรับผู้จัดทำ

Claim IDs: C12, C18, C19, C20

- [สูตร evaluate](../../train_sar_unet.py)
- [entropy และ uncertainty](../../m80a_dev_ensemble_uq.py)
- [top-10% capture](../../m80b_dev_uncertainty_audit.py)

## ขอบเขตการตีความ

NaN สำหรับ empty IoU union ไม่ได้หมายความว่าเมตริกทุกตัวในโค้ดใช้ NaN เหมือนกัน เช่น F1 มี policy ของตนเอง
