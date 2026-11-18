"""Validate the revised slide evidence, editable OOXML and scope labels."""
from pathlib import Path
from zipfile import ZipFile
import csv,io,json,math,re,subprocess,sys,xml.etree.ElementTree as E
D=Path(__file__).resolve().parent;P=D.parent;ROOT=P.parent
target=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else P/'output/FloodAI_Research_Revised26_TH_Final.pptx'
manifest=json.loads((D/'manifest.json').read_text())
NS={'a':'http://schemas.openxmlformats.org/drawingml/2006/main','c':'http://schemas.openxmlformats.org/drawingml/2006/chart','s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
checks=[]
def check(name,ok,detail=''):checks.append({'name':name,'pass':bool(ok),'detail':str(detail)})
def csvread(name):return list(csv.DictReader((P/'evidence'/name).open()))
def near(a,b):return math.isclose(float(a),float(b),abs_tol=1e-12,rel_tol=0)
def flat(labels):return labels[0] if labels and isinstance(labels[0],list) else labels
def clean(v):return re.sub(r'\s+','',str(v))
runs=csvread('verified_runs.csv');models=csvread('verified_models.csv');events=csvread('verified_events.csv');ensemble=csvread('verified_ensemble_events.csv')
with ZipFile(target) as z:
    slides=[n for n in z.namelist() if re.fullmatch(r'ppt/slides/slide\d+\.xml',n)]
    notes=[n for n in z.namelist() if re.fullmatch(r'ppt/notesSlides/notesSlide\d+\.xml',n)]
    check('26 slides and notes',len(slides)==len(notes)==26)
    roots={i:E.fromstring(z.read(f'ppt/slides/slide{i}.xml')) for i in range(1,27)}
    text={i:'\n'.join(v.text or '' for v in r.findall('.//a:t',NS)) for i,r in roots.items()}
    for i,r in roots.items():
        check(f'valid table anchors {i}',all(v.get('anchor') in [None,'t','ctr','b','just','dist'] for v in r.findall('.//a:tcPr',NS)))
        n=E.fromstring(z.read(f'ppt/notesSlides/notesSlide{i}.xml'))
        nt='\n'.join(v.text or '' for v in n.findall('.//a:t',NS))
        check(f'notes content {i}',len(nt)>300 and 'Sources / evidence' in nt and 'ประโยคเชื่อมไปหน้าถัดไป' in nt)
        for source in manifest['slides'][i-1]['sources']:
            check(f'source exists {i}: {source}',source.startswith('https://') or (ROOT/source).exists())
    check('scope distinguishes future',all('แผนเสนอ' in text[i] for i in [23,24,25]))
    check('final runs are future',all(v in text[23] for v in ['9 runs','ยังไม่ได้ดำเนินการ','27 runs']))
    check('141 versus 9 visible',all(v in text[20] for v in ['141 ภาพ','9 ภาพที่เลือกไว้']))
    check('independent final test absent visible','ยังไม่มี Independent Final TEST' in text[21])
    cap=next(r for r in csvread('verified_selected_uq_images.csv') if r['image']=='Sri-Lanka_845821_S1Hand.tif')
    check('selected capture on exact image',all(f'{float(cap[k])*100:.1f}%' in text[20] for k in ['entropy_capture','mi_capture']) and 'ในภาพนี้' in text[20])
    check('all seed results retained visible','0.3891' in text[15])
    check('ensemble score visible',f'{sum(float(r["iou"]) for r in ensemble)/3:.4f}' in text[18])
    check('no placeholders',not any(v in '\n'.join(text.values()) for v in ['[ชื่อ','[รหัส','Click to edit','TODO']))
    check('table count',sum(len(r.findall('.//a:tbl',NS)) for r in roots.values())==6)
    for m in manifest['tables']:
        table=roots[m['slide']].find('.//a:tbl',NS)
        actual=[[clean(''.join(v.text or '' for v in cell.findall('.//a:t',NS))) for cell in row.findall('a:tc',NS)] for row in table.findall('a:tr',NS)]
        check(f'table cells {m["slide"]}',actual==[[clean(v) for v in row] for row in m['data']])
    for j,m in enumerate(manifest['charts'],1):
        root=E.fromstring(z.read(m['part']));series=root.findall('.//c:barChart/c:ser',NS)
        check(f'chart series {m["slide"]}',len(series)==len(m['series']))
        for si,(ser,expected) in enumerate(zip(series,m['series'])):
            vals=[v.text for v in ser.findall('./c:val/c:numRef/c:numCache/c:pt/c:v',NS)]
            labels=[v.text for v in ser.findall('./c:cat/c:multiLvlStrRef/c:multiLvlStrCache/c:lvl/c:pt/c:v',NS)] or [v.text for v in ser.findall('./c:cat/c:strRef/c:strCache/c:pt/c:v',NS)]
            check(f'chart values {m["slide"]}/{si}',len(vals)==len(expected['values']) and all(near(a,b) for a,b in zip(vals,expected['values'])))
            check(f'chart categories {m["slide"]}/{si}',labels==flat(expected['labels']))
            if m['sd']:
                for direction in ['plus','minus']:
                    vals=[v.text for v in ser.findall(f'./c:errBars/c:{direction}/c:numLit/c:pt/c:v',NS)]
                    check(f'SD {m["slide"]}/{si}/{direction}',len(vals)==len(m['sd'][si]) and all(near(a,b) for a,b in zip(vals,m['sd'][si])))
        candidates=sorted(n for n in z.namelist() if n.startswith('ppt/embeddings/') and n.endswith('.xlsx'))
        name=f'ppt/embeddings/Microsoft_Excel_Worksheet{j}.xlsx'
        if name not in candidates:name=candidates[j-1]
        with ZipFile(io.BytesIO(z.read(name))) as book:
            sheet=E.fromstring(book.read('xl/worksheets/sheet1.xml'))
            byref={v.get('r'):v.find('s:v',NS).text for v in sheet.findall('.//s:c',NS) if v.find('s:v',NS) is not None}
            for si,ex in enumerate(m['series']):
                vals=[byref.get(f'{chr(66+si)}{i+2}') for i in range(len(ex['values']))]
                check(f'workbook {m["slide"]}/{si}',all(v is not None and near(v,b) for v,b in zip(vals,ex['values'])))
    byslide={m['slide']:m for m in manifest['charts']}
    check('243 inventory values',byslide[7]['series'][0]['values']==[30,18,28,26,30,42,69] and sum(byslide[7]['series'][0]['values'])==243)
    bins=csvread('verified_coverage_bins.csv');order=['zero_water','water_0_to_1pct','water_1_to_10pct','water_10_to_50pct','water_ge_50pct']
    expected=[int(next(r for r in bins if r['fold']=='dev_fold_01_usa' and r['water_bin']==k)['n_chips']) for k in order]
    check('coverage bins measured',byslide[8]['series'][0]['values']==expected and sum(expected)==174)
    check('model means from verified CSV',all(near(s['values'][0],r['macro_dev_iou']) and near(sd[0],r['seed_macro_sample_sd']) for s,sd,r in zip(byslide[14]['series'],byslide[14]['sd'],models)))
    for s,seed in zip(byslide[15]['series'],[42,123,777]):
        check(f'baseline seed {seed} from CSV',all(near(v,next(r for r in runs if r['method']=='baseline' and int(r['seed'])==seed and r['event']==e)['iou']) for v,e in zip(s['values'],['USA','Sri-Lanka','Spain'])))
    check('ensemble chart from CSV',all(near(a,r['iou']) for a,r in zip(byslide[18]['series'][1]['values'],ensemble)))

SKILL=Path('/Users/netinho/.codex/plugins/cache/openai-primary-runtime/presentations/26.1105.12137/skills/presentations/container_tools')
for name,script,args in [('integrity','inspect_presentation_package_integrity.py',['--fail-on-findings']),('layout','inspect_presentation_layout_geometry.py',['--expected-aspect','16:9','--expected-slide-count','26','--approved-font-family','Tahoma','--validate-heading-fit','--validate-bullet-geometry'])]:
    result=subprocess.run([sys.executable,str(SKILL/script),str(target),*args],capture_output=True,text=True)
    report=json.loads(result.stdout);(D/f'{name}_validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    check(name+' gate',result.returncode==0 and report.get('finding_count',1)==0 and report.get('warning_count',0)==0,report)
report={'file':str(target),'status':'PASS' if all(c['pass'] for c in checks) else 'FAIL','checks':len(checks),'failures':[c for c in checks if not c['pass']],'slides':26,'native_charts':5,'native_tables':6,'native_diagrams':3,'notes':26,'native_powerpoint_final_inspected':False}
(D/'validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(report,ensure_ascii=False,indent=2));sys.exit(bool(report['failures']))
