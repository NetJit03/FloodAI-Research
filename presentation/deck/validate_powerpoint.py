#!/usr/bin/env python3
"""Verify all editable chart values, custom SD bars, notes, tables and OOXML."""
from pathlib import Path
from zipfile import ZipFile
import json
import math
import re
import subprocess
import sys
import xml.etree.ElementTree as E

D=Path(__file__).resolve().parent
P=D.parent
source=json.loads((D/'deck_content.json').read_text())
manifest=json.loads((D/'deck_manifest.json').read_text())
target=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else P/'output/FloodAI_Research_Presentation_TH_Final.pptx'
NS={'a':'http://schemas.openxmlformats.org/drawingml/2006/main',
    'p':'http://schemas.openxmlformats.org/presentationml/2006/main',
    'c':'http://schemas.openxmlformats.org/drawingml/2006/chart',
    's':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
checks=[]
def check(name,ok,detail=''):
    checks.append(dict(check=name,status='PASS' if ok else 'FAIL',detail=str(detail)))
def near(a,b):return math.isclose(float(a),float(b),rel_tol=0,abs_tol=1e-12)
with ZipFile(target) as z:
    slide_names=[f'ppt/slides/slide{i}.xml' for i in range(1,19)]
    check('18_slide_parts',all(n in z.namelist() for n in slide_names) and len([n for n in z.namelist() if re.fullmatch(r'ppt/slides/slide\d+\.xml',n)])==18)
    check('18_notes_parts',len([n for n in z.namelist() if re.fullmatch(r'ppt/notesSlides/notesSlide\d+\.xml',n)])==18)
    alltext=''
    for i,n in enumerate(slide_names,1):
        root=E.fromstring(z.read(n))
        texts='\n'.join(t.text or '' for t in root.findall('.//a:t',NS))
        alltext+=texts
        for el in root.findall('.//a:tcPr',NS):
            check(f'table_anchor_slide{i}',el.get('anchor') in [None,'t','ctr','b','just','dist'],el.get('anchor'))
        notes=E.fromstring(z.read(f'ppt/notesSlides/notesSlide{i}.xml'))
        note_text='\n'.join(t.text or '' for t in notes.findall('.//a:t',NS))
        check(f'notes_have_sources_{i}','Sources / evidence' in note_text and 'Claim IDs' in note_text)
        for cid in source['slides'][i-1]['claim_ids']:
            check(f'note_claim_{i}_{cid}',cid in note_text)
    check('no_name_id_placeholders',not any(t in alltext for t in ['[ชื่อ','[รหัส','[STUDENT','Click to edit']))
    check('dev_scope_visible','Development Validation' in alltext and 'Independent Final TEST' in alltext)
    check('mi_limit_visible','MI ต่ำยังทำนายผิดได้' in alltext)
    table_count=sum(len(E.fromstring(z.read(n)).findall('.//a:tbl',NS)) for n in slide_names)
    check('native_tables',table_count==9,table_count)
    for m in manifest['charts']:
        root=E.fromstring(z.read(m['chart_part']))
        series=root.findall('.//c:barChart/c:ser',NS)
        check('chart_series_count_'+m['chart_part'],len(series)==len(m['series']))
        for si,(ser,expected) in enumerate(zip(series,m['series'])):
            actual=[v.text for v in ser.findall('./c:val/c:numRef/c:numCache/c:pt/c:v',NS)]
            check(f'chart_values_{m["slide"]}_{si}',len(actual)==len(expected['values']) and all(near(a,b) for a,b in zip(actual,expected['values'])),actual)
            labels=[v.text for v in ser.findall('./c:cat/c:strRef/c:strCache/c:pt/c:v',NS)]
            if not labels:
                labels=[v.text for v in ser.findall('./c:cat/c:multiLvlStrRef/c:multiLvlStrCache/c:lvl/c:pt/c:v',NS)]
            expected_labels=expected['labels'][0] if expected['labels'] and isinstance(expected['labels'][0],list) else expected['labels']
            check(f'chart_categories_{m["slide"]}_{si}',labels==expected_labels,labels)
            if m['error_bars']:
                for direction in ['plus','minus']:
                    values=[v.text for v in ser.findall(f'./c:errBars/c:{direction}/c:numLit/c:pt/c:v',NS)]
                    sd=m['error_bars'][si]
                    check(f'error_bars_{m["slide"]}_{si}_{direction}',len(values)==len(sd) and all(near(a,b) for a,b in zip(values,sd)),values)
        # Validate the editable embedded workbook against each chart's literal series.
        xlsx=f'ppt/embeddings/Microsoft_Excel_Worksheet{manifest["charts"].index(m)+1}.xlsx'
        candidates=[n for n in z.namelist() if n.startswith('ppt/embeddings/') and n.endswith('.xlsx')]
        if xlsx not in candidates:
            xlsx=candidates[manifest['charts'].index(m)]
        import io
        with ZipFile(io.BytesIO(z.read(xlsx))) as book:
            sheet=E.fromstring(book.read('xl/worksheets/sheet1.xml'))
            byref={c.attrib['r']:c.find('s:v',NS).text for c in sheet.findall('.//s:sheetData/s:row/s:c',NS) if c.find('s:v',NS) is not None}
            for si,expected in enumerate(m['series']):
                column=chr(ord('B')+si)
                vals=[byref.get(f'{column}{j+2}') for j in range(len(expected['values']))]
                check(f'workbook_values_{m["slide"]}_{si}',all(v is not None and near(v,e) for v,e in zip(vals,expected['values'])),vals)

SKILL=Path('/Users/netinho/.codex/plugins/cache/openai-primary-runtime/presentations/26.1105.12137/skills/presentations/container_tools')
reports={}
for name,script,args in [
    ('integrity','inspect_presentation_package_integrity.py',['--fail-on-findings']),
    ('layout','inspect_presentation_layout_geometry.py',['--expected-aspect','16:9','--expected-slide-count','18','--approved-font-family','Tahoma','--validate-heading-fit','--validate-bullet-geometry'])]:
    result=subprocess.run([sys.executable,str(SKILL/script),str(target),*args],capture_output=True,text=True)
    try:report=json.loads(result.stdout)
    except Exception:report={'error':result.stdout+result.stderr}
    reports[name]=report
    (D/f'{name}_validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    check(name+'_gate',result.returncode==0 and report.get('finding_count',1)==0 and report.get('warning_count',0)==0)
summary=dict(file=str(target),status='PASS' if all(c['status']=='PASS' for c in checks) else 'FAIL',
             checks=len(checks),failures=[c for c in checks if c['status']=='FAIL'],
             editable_charts=3,editable_tables=9,notes=18,
             authoring_override=manifest['user_override'],
             rendering='See render_validation.json for the separate visual verification status')
(D/'powerpoint_validation.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(summary,ensure_ascii=False,indent=2))
sys.exit(bool(summary['failures']))
