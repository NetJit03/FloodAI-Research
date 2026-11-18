#!/usr/bin/env python3
"""Prepare an authoring-neutral specification from the audited slide manuscripts."""
from pathlib import Path
import csv
import json
import re

P=Path(__file__).resolve().parents[1]
D=P/'deck'
D.mkdir(exist_ok=True)
index=json.loads((P/'evidence/slide_index.json').read_text())
audit=json.loads((P/'evidence/package_validation.json').read_text())
if audit['status']!='PASS':raise SystemExit('Evidence package must pass before deck preparation')
def read(name):return list(csv.DictReader((P/'evidence'/name).open()))
spec=[]
for i,row in enumerate(index,1):
    text=(P/'slides'/row['file']).read_text()
    def section(name):
        m=re.search(r'^## '+re.escape(name)+r'\n\n(.*?)(?=\n## |\Z)',text,re.M|re.S)
        return m.group(1).strip() if m else ''
    speaker=section('บทพูดภาษาไทย')
    sources=section('หลักฐานสำหรับผู้จัดทำ')
    limits=section('ขอบเขตการตีความ')
    spec.append(dict(number=i,source=row['file'],kind=row['kind'],title=row['title'],
                     slide_text=section('ข้อความบนสไลด์'),
                     speaker_notes=speaker+'\n\nขอบเขตการตีความ\n'+limits+'\n\nSources / evidence\n'+sources,
                     claim_ids=row['claims'],seconds=row['seconds']))
data=dict(slides=spec,models=read('verified_models.csv'),events=read('verified_events.csv'),
          runs=read('verified_runs.csv'),ensemble=read('verified_ensemble_events.csv'),
          selected=read('verified_selected_uq_events.csv'),splits=read('verified_splits.csv'),
          figures=list(csv.DictReader((P/'assets/figure_sources.csv').open())),
          design=dict(aspect='16:9',background='FFFFFF',ink='142638',accent='24679B',
                      second='D28B39',third='2E8B74',body='Thai',chart_labels='English',
                      notes='Thai with evidence source links',main_count=12,appendix_count=6))
(D/'deck_content.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
(D/'LAYOUT_PLAN_TH.md').write_text('''# โครงจัดหน้าสำหรับไฟล์นำเสนอ

ขนาด 16:9 พื้นขาว ตัวอักษรสีน้ำเงินเข้ม ใช้สีน้ำเงิน/ส้ม/เขียวแยก Baseline/V2-A/V2-B เหมือนกันทุกหน้า ตัวอักษรและตารางควรแก้ไขได้ บทพูดและ sources อยู่ใน speaker notes

| หน้า | การจัดวาง |
| --- | --- |
| 01 | ชื่อเรื่องขนาดใหญ่และขอบเขต DEV Validation |
| 02 | โจทย์วิจัยสั้น ๆ และภาพ VV/VH/GT |
| 03 | จำนวนคลังพัฒนาและตาราง TRAIN/VALID |
| 04 | ตารางสถาปัตยกรรมจริงและจำนวนพารามิเตอร์ |
| 05 | ตารางเปรียบเทียบสาม sampling policies |
| 06 | จำนวน 27 runs และลำดับการเฉลี่ย IoU |
| 07 | กราฟผลรวมสามวิธี พร้อม error bars ที่ระบุว่าเป็น Sample SD |
| 08 | กราฟราย event พร้อมข้อความ seed sensitivity |
| 09 | ภาพ failure case ขนาดใหญ่ รักษา legend และคำว่า DEV |
| 10 | กราฟ Ensemble เทียบค่าเฉลี่ยโมเดลเดี่ยว และ macro scores |
| 11 | ภาพ UQ หกช่องและคำอธิบาย Entropy/MI กับขอบเขต 141/9 |
| 12 | ข้อค้นพบหลักและ Independent Test ที่ต้องทำต่อ |
| A | ตาราง hyperparameters และสูตร sampling |
| B | ตารางผลครบ 27 runs |
| C | ตาราง UQ ของ 141 ภาพ แยกจาก error capture ของ 9 ภาพ |
| D | จำนวนภาพราย event และบทบาทข้อมูลเก่า/Thailand |
| E | สูตร IoU, Ensemble, Entropy, MI, Brier และ Error capture |
| F | รายการอ้างอิง |

คงข้อสรุปจากต้นฉบับ ไม่คัดลอกตารางเต็มมาซ้ำกับกราฟบนสไลด์หลัก ลดคำอธิบายบนหน้าแล้วเก็บรายละเอียดใน notes ไม่มี placeholder ชื่อหรือรหัสที่ยังไม่ได้รับจากผู้ใช้
''')
print('Prepared content and layout specification for',len(spec),'slides')
