#!/usr/bin/env python3
"""Validate delivery coverage, relative links, source hashes, and figure integrity."""
import csv
import hashlib
import json
from pathlib import Path
import re
import sys

P=Path(__file__).resolve().parents[1]
ROOT=P.parent
errors=[]
def need(condition,message):
    if not condition:errors.append(message)
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()
summary=json.loads((P/'evidence/verification_summary.json').read_text())
need(not summary['failed'],'Failed numerical evidence checks')
need(summary['runs']==27 and summary['unique_dev_chips']==243 and summary['ensemble_images']==141,'Evidence coverage mismatch')
need(summary['cpu_preview_inference']==9,'Nine CPU preview checks required for current finalization')
index=json.loads((P/'evidence/slide_index.json').read_text())
need(sum(s['kind']=='main' for s in index)==12,'Main slide count')
need(sum(s['kind']=='appendix' for s in index)==6,'Appendix slide count')
claims=list(csv.DictReader((P/'evidence/claims_and_sources.csv').open()))
ids={r['claim_id'] for r in claims}
need(len(ids)==25,'Claim registry must contain 25 unique claims')
for s in index:
    p=P/'slides'/s['file']
    need(p.is_file(),'Missing slide '+str(p))
    if not p.is_file():continue
    text=p.read_text()
    for title in ['## ข้อความบนสไลด์','## บทพูดภาษาไทย','## ภาพหรือตารางและการจัดวาง','## หลักฐานสำหรับผู้จัดทำ','## ขอบเขตการตีความ']:
        need(title in text,f'Missing section {title} in {p.name}')
    need(set(s['claims'])<=ids,'Unknown claims in '+p.name)
    for cid in s['claims']:
        r=next(r for r in claims if r['claim_id']==cid)
        need(s['file'] in r['slides'].split(';'),'Claim-slide mapping mismatch '+cid)
for p in P.rglob('*.md'):
    for target in re.findall(r'\]\(([^)]+)\)',p.read_text()):
        if target.startswith(('http://','https://','#','mailto:')):continue
        path=target.split('#')[0]
        need((p.parent/path).resolve().exists(),f'Broken local link: {p.relative_to(P)} -> {target}')
for r in csv.DictReader((P/'assets/figure_sources.csv').open()):
    p=P/r['figure']
    need(p.is_file() and sha(p)==r['output_sha256'],'Figure hash mismatch '+str(p))
    if r['kind']=='byte-identical source figure':
        need(sha(ROOT/r['source'])==r['source_sha256'],'Source figure changed '+r['source'])
    else:
        need(sha(P/r['source'])==r['source_sha256'],'Chart data changed '+r['source'])
for r in csv.DictReader((P/'evidence/source_manifest.csv').open()):
    p=ROOT/r['path']
    need(p.is_file() and sha(p)==r['sha256'],'Experiment source drift '+r['path'])
for r in claims:
    if not r['source'].startswith('https://'):need((ROOT/r['source']).is_file(),'Missing claim source '+r['source'])
need(len(list((P/'assets/figures').glob('*.png')))==11,'Figure count must be 11')
result={'status':'PASS' if not errors else 'FAIL','main_slides':12,'appendix_slides':6,
        'claims':len(claims),'figures':11,'errors':errors}
(P/'evidence/package_validation.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
print(json.dumps(result,indent=2,ensure_ascii=False))
sys.exit(bool(errors))
