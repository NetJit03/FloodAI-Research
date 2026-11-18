# แหล่งอ้างอิงภายนอก

ตรวจเข้าถึง 18 พฤศจิกายน 2569 ผ่านหน้าแหล่งต้นฉบับ ไม่ใช้บทสนทนาเดิมเป็นหลักฐานแทนแหล่งเหล่านี้

| ID | แหล่งต้นฉบับ | ใช้สนับสนุน | สถานะ |
| --- | --- | --- | --- |
| R01 | [Sen1Floods11 repository](https://github.com/cloudtostreet/Sen1Floods11) | ชื่อ dataset, label codes, 512×512, S1 สองแบนด์ VV/VH และหน่วย dB ตามเอกสาร | อ่าน README ของผู้จัดทำแล้ว |
| R02 | [Sen1Floods11 documentation](https://github.com/cloudtostreet/Sen1Floods11/blob/master/docs/README.md) | Hand-labelled 446 และ weak-labelled 4,385 ในหมวด flood-event data และมี permanent-water หมวดแยก | อ่าน docs ของผู้จัดทำแล้ว |
| R03 | [Ronneberger, Fischer, Brox (2015), U-Net](https://arxiv.org/abs/1505.04597) | ที่มาของแนวคิด contracting/expanding paths สำหรับ segmentation | ตรวจชื่อ ผู้เขียน ปี และ abstract แล้ว |
| R04 | [Lakshminarayanan, Pritzel, Blundell (2017), Deep Ensembles](https://papers.neurips.cc/paper/2017/hash/9ef2ed4b7fd2c810847ffa5fa85bce38-Abstract.html) | ที่มาของแนวทาง Deep Ensemble สำหรับ predictive uncertainty | ตรวจชื่อ ผู้เขียน ปี และ abstract แล้ว |
| R05 | [Bonafilia et al. (2020), Sen1Floods11 paper](https://openaccess.thecvf.com/content_CVPRW_2020/html/w11/Bonafilia_Sen1Floods11_A_Georeferenced_Dataset_to_Train_and_Test_Deep_Learning_CVPRW_2020_paper.html) | รายการอ้างอิงบทความชุดข้อมูลตาม repository ผู้จัดทำ | หน้า HTML และ PDF ตอบ HTTP 403 ในรอบนี้ ไม่ได้อ่าน full paper |

ข้อความอ้างอิงย่อสำหรับใส่หน้า References:

- Bonafilia, D., Tellman, B., Anderson, T., & Issenberg, E. (2020). *Sen1Floods11: A Georeferenced Dataset to Train and Test Deep Learning Flood Algorithms for Sentinel-1*. CVPR Workshops. รายละเอียดข้อมูลตรวจจาก repository/docs ของผู้จัดทำ
- Ronneberger, O., Fischer, P., & Brox, T. (2015). *U-Net: Convolutional Networks for Biomedical Image Segmentation*. arXiv:1505.04597
- Lakshminarayanan, B., Pritzel, A., & Blundell, C. (2017). *Simple and Scalable Predictive Uncertainty Estimation using Deep Ensembles*. Advances in Neural Information Processing Systems 30

สถาปัตยกรรม SmallUNet, สูตร sampling และค่าเมตริกบนสไลด์ต้องอ้าง **โค้ดและผลโปรเจ็กต์** ด้วย บทความ U-Net ไม่ได้ยืนยันจำนวนพารามิเตอร์ของ implementation นี้ และผลในบทความ Deep Ensembles ไม่ใช่หลักฐานว่า FloodAI ได้ calibrated probabilities หรือพร้อมใช้จริง

การตรงกับ hash ของ local frozen files ยืนยันความคงเดิมของไฟล์ที่บันทึกในโปรเจ็กต์ การตรวจครั้งนี้ไม่ได้ดาวน์โหลด TIFF ต้นฉบับทางการมาเทียบทุก byte หรือรับรองว่า labels ทุกพิกเซลถูกต้อง
