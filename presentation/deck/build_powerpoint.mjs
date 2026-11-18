import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createRequire } from 'node:module';
const DIR=path.dirname(fileURLToPath(import.meta.url));
const P=path.dirname(DIR);
const require=createRequire(path.join(DIR,'tooling','package.json'));
const PptxGenJS=require('pptxgenjs');
const JSZip=require('jszip');
const content=JSON.parse(await fs.readFile(path.join(DIR,'deck_content.json'),'utf8'));
const pptx=new PptxGenJS();
pptx.layout='LAYOUT_WIDE';
pptx.author='FloodAI-Research';
pptx.subject='Preliminary event-disjoint development validation of SAR surface-water segmentation';
pptx.title='FloodAI-Research: Domain Generalization and Uncertainty Quantification';
pptx.company='FloodAI-Research';
pptx.lang='th-TH';
pptx.theme={headFontFace:'Tahoma',bodyFontFace:'Tahoma',lang:'th-TH'};
const W=13.333333,H=7.5;
const C={ink:'142638',blue:'24679B',orange:'D28B39',green:'2E8B74',muted:'506274',line:'D5DEE5',pale:'F2F5F7',white:'FFFFFF'};
const manifest={authoring:'PptxGenJS',version:pptx.version,user_override:'User explicitly approved PptxGenJS in place of the unavailable artifact-tool runtime.',slides:[],charts:[],tables:[]};
const errorSpecs=[];
const fmt=v=>Number(v).toFixed(4);
const methods=['baseline','v2a_eventbalanced','v2b_coverage'];
const methodNames=['Baseline','V2-A','V2-B'];
const evs=['USA','Sri-Lanka','Spain'];

function text(s,t,x,y,w,h,size=22,opts={}){
  s.addText(t,{x,y,w,h,fontFace:'Tahoma',fontSize:size,color:C.ink,margin:0,
    breakLine:false,paraSpaceAfterPt:0,valign:'mid',lineSpacingMultiple:1.08,...opts});
}
function paragraph(s,t,x,y,w,h,size=22,opts={}){text(s,t,x,y,w,h,size,{valign:'top',...opts});}
function footer(s,n,t='Development Validation. ผลการทดลองเบื้องต้น'){
  text(s,t,.60,7.09,11.5,.23,10.5,{color:C.muted});
  text(s,String(n),12.15,7.07,.58,.25,11,{align:'right',color:C.muted});
}
function newSlide(n,title,subtitle=''){
  const s=pptx.addSlide();s.background={color:C.white};
  text(s,title,.60,.42,12.1,.65,30,{bold:true});
  if(subtitle)text(s,subtitle,.62,1.10,12.05,.45,17.5,{color:C.muted});
  const source=content.slides[n-1];
  const notes=source.speaker_notes.replace(/\[([^\]]+)\]\(([^)]+)\)/g,(_,label,target)=>{
    if(target.startsWith('https://'))return label+': '+target;
    return label+': '+path.resolve(P,'slides',target);
  });
  s.addNotes(notes);
  manifest.slides.push({number:n,title,source:source.source,claim_ids:source.claim_ids});
  return s;
}
function table(s,n,rows,x,y,w,h,colW,size=21,options={}){
  const styled=rows.map((r,ri)=>r.map((v,ci)=>({text:String(v),options:{
    fill:ri===0?C.ink:(ri%2===0?C.pale:C.white),color:ri===0?C.white:C.ink,
    bold:ri===0,align:ci===0?'left':'center',valign:'middle',...options.cell?.(ri,ci)
  }})));
  s.addTable(styled,{x,y,w,h,colW,rowH:h/rows.length,fontFace:'Tahoma',fontSize:size,
    color:C.ink,margin:[5,9,5,9],border:{type:'solid',color:C.line,pt:.6},
    autoPage:false,verbose:false,paraSpaceAfterPt:0,...options});
  manifest.tables.push({slide:n,rows:rows.length,columns:rows[0].length,data:rows});
}
async function image(s,name,x,y,w,h){
  const p=path.join(P,'assets','figures',name);
  const bytes=await fs.readFile(p);
  const iw=bytes.readUInt32BE(16),ih=bytes.readUInt32BE(20);
  const ratio=Math.min(w/iw,h/ih),fw=iw*ratio,fh=ih*ratio;
  s.addImage({path:p,x:x+(w-fw)/2,y:y+(h-fh)/2,w:fw,h:fh,altText:name.replace(/_/g,' ')});
}
function chart(s,n,data,x,y,w,h,opts={},errors=null){
  s.addChart(pptx.ChartType.bar,data,{x,y,w,h,barDir:'col',barGrouping:'clustered',
    chartColors:[C.blue,C.orange,C.green],showLegend:true,legendPos:'b',legendFontFace:'Tahoma',
    legendFontSize:16,legendColor:C.ink,showValue:true,showTitle:false,
    dataLabelColor:C.ink,dataLabelFontFace:'Tahoma',dataLabelFontSize:18,dataLabelFormatCode:'0.0000',
    dataLabelPosition:'outEnd',showBorder:false,showCatName:false,showSerName:false,
    showCatName:false,catAxisLabelFontFace:'Tahoma',catAxisLabelFontSize:17,
    catAxisLabelColor:C.ink,catAxisLineColor:C.line,catAxisLineSize:1,
    valAxisLabelFontFace:'Tahoma',valAxisLabelFontSize:15,valAxisLabelColor:C.muted,
    valAxisMinVal:0,valAxisMaxVal:.9,valAxisMajorUnit:.1,valAxisNumFmt:'0.0',
    valAxisLineShow:false,catAxisLineShow:true,valGridLine:{color:C.line,width:.5},
    showValue:true,showMarker:false,gapSizePct:90,showShadow:false,
    chartArea:{fill:{color:C.white},border:{color:C.white,pt:0}},
    plotArea:{fill:{color:C.white},border:{color:C.white,pt:0}},...opts});
  const ordinal=manifest.charts.length+1;
  manifest.charts.push({slide:n,chart_part:`ppt/charts/chart${ordinal}.xml`,series:data,error_bars:errors});
  if(errors)errorSpecs.push({part:`ppt/charts/chart${ordinal}.xml`,values:errors});
}

// 01. Minimal cover. No name or ID is invented.
{
 const s=newSlide(1,'');s.background={color:C.ink};
 text(s,'FLOODAI-RESEARCH',.78,.68,11.8,.42,18,{color:'8BC3DA',bold:true,charSpacing:2});
 paragraph(s,'ความน่าเชื่อถือของแผนที่น้ำ\nจาก Sentinel-1 SAR',.78,1.65,11.6,1.75,42,{bold:true,color:C.white});
 paragraph(s,'Domain Generalization and\nUncertainty Quantification',.80,3.70,11.3,1.05,27,{color:C.white});
 paragraph(s,'Small U-Net จาก VV/VH\nผลเบื้องต้นบน Event-disjoint Development Validation',.81,5.17,11.45,.95,22,{color:'C6D8E5'});
 text(s,'19 พฤศจิกายน 2569',.81,6.72,10,.35,17,{color:'C6D8E5'});
}
// 02. Task, target and questions with a real VV/VH/GT example.
{
 const s=newSlide(2,'โจทย์และคำถามวิจัย');
 paragraph(s,'ใช้ Sentinel-1 VV/VH เพื่อจำแนกน้ำผิวดินรายพิกเซล ณ เวลาถ่ายภาพ',.65,1.30,12,.52,23);
 paragraph(s,'Sampling ช่วยข้ามเหตุการณ์หรือไม่? ผลไวต่อ seed เพียงใด?\nEnsemble และ UQ ช่วยบอกบริเวณที่ควรตรวจเพิ่มได้อย่างไร?',.65,1.98,12,.93,22,{color:C.blue});
 await image(s,'11_input_vv_vh_gt.png',.64,3.02,12.05,3.82);
 footer(s,2,'Selected DEV example. Target เป็น surface water ซึ่งอาจรวมน้ำถาวร');
}
// 03. Event-level partitions, not an untouched final test.
{
 const s=newSlide(3,'ข้อมูลพัฒนาและการแบ่งตามเหตุการณ์','Sen1Floods11 hand-labelled SAR/LabelHand pairs');
 text(s,'243',.78,1.95,3.3,1.1,76,{bold:true,color:C.blue});
 text(s,'คู่ภาพ SAR / Ground Truth',.83,3.12,3.4,.5,21);
 text(s,'7 event prefixes',.83,3.70,3.3,.45,22,{color:C.muted});
 table(s,3,[['Validation event','TRAIN','VALID'],['USA',174,69],['Sri Lanka',201,42],['Spain',213,30]],4.55,1.85,8.05,2.65,[4.15,1.95,1.95],22);
 paragraph(s,'กัน Validation event ออกจาก TRAIN ทั้งเหตุการณ์\nใช้ VALID เลือก checkpoint และเปรียบเทียบวิธี',.83,5.03,11.7,1.02,24);
 text(s,'ผลที่รายงานจึงเป็น Development Results',.83,6.23,11.7,.45,23,{color:C.blue,bold:true});
 footer(s,3,'สาม held-out DEV events จากคลังพัฒนา 7 events. จำนวน 243 ภาพไม่ใช่ TRAIN ของทุก fold');
}
// 04. Actual implementation rather than a generic U-Net illustration.
{
 const s=newSlide(4,'Small U-Net ที่ใช้จริง','สถาปัตยกรรมเดียวกันทั้ง Baseline, V2-A และ V2-B');
 table(s,4,[['ส่วนของโมเดล','Channels'],['Input','2: VV, VH'],['Encoder','16, 32, 64, 128'],['Bottleneck','256'],['Decoder + skip connections','128, 64, 32, 16'],['Output','1 logit ต่อพิกเซล']],.67,1.82,8.1,3.85,[5.05,3.05],21);
 text(s,'1,963,953',9.1,2.05,3.58,.66,34,{bold:true,color:C.blue});
 text(s,'parameters',9.13,2.78,3.3,.45,21,{color:C.muted});
 paragraph(s,'Sigmoid\nP(water)\nThreshold 0.50',9.13,3.75,3.35,1.50,24);
 text(s,'TRAIN crop 256×256. VALID ใช้ภาพเต็ม 512×512',.72,6.25,11.9,.47,24);
 footer(s,4,'Implementation: Convolution, GroupNorm, ReLU, bilinear upsampling และ skip connections');
}
// 05. Treatment includes replacement and an explicit 50/50 mixture.
{
 const s=newSlide(5,'วิธีเลือกภาพระหว่างฝึก');
 table(s,5,[['วิธี','TRAIN image sampling'],['Baseline','Shuffle โดยไม่เลือกภาพซ้ำภายใน epoch'],['V2-A','ให้แต่ละ event มีโอกาสเท่ากันในความคาดหมาย'],['V2-B','ผสม uniform-image 50%\nกับ uniform-coverage-bin 50%']],.68,1.62,11.96,3.55,[2.18,9.78],22);
 paragraph(s,'V2-A และ V2-B สุ่มคืนตัวอย่าง จำนวน draws ต่อ epoch เท่ากับ N_train\nคง architecture, loss, folds และ threshold หลักเหมือนกัน',.73,5.55,11.8,1.0,22);
 footer(s,5,'V2-B ใช้สัดส่วนน้ำจาก full-chip GT ของ TRAIN. Bin coverage อาจต่างจาก crop coverage');
}
// 06. Metric hierarchy is explicit.
{
 const s=newSlide(6,'การทดลองและเกณฑ์เปรียบเทียบ');
 text(s,'27',.80,1.70,3.1,1.25,88,{bold:true,color:C.blue});
 text(s,'training runs',.85,3.05,3.2,.53,27);
 paragraph(s,'3 methods\n3 seeds\n3 DEV folds',.85,3.85,3.3,1.65,26,{color:C.muted});
 const steps=[['1  ภายในแต่ละ event','รวม TP, FP, FN ของ valid pixels\nแล้วคำนวณ Water IoU'],['2  ภายในแต่ละ seed','เฉลี่ย IoU ของสาม events\nให้น้ำหนักเหตุการณ์เท่ากัน'],['3  ข้ามสาม seeds','รายงาน Mean และ Sample SD\nของ seed macro scores']];
 steps.forEach((a,i)=>{text(s,a[0],4.65,1.67+i*1.52,7.9,.43,24,{bold:true});paragraph(s,a[1],4.65,2.20+i*1.52,7.9,.83,22,{color:C.muted});});
 footer(s,6,'Seeds 42, 123, 777. เลือก checkpoint จาก VALID IoU. Threshold 0.50. SD ไม่ใช่ confidence interval');
}
// 07. Fully editable bars and custom numerical error bars.
{
 const s=newSlide(7,'Sampling ทั้งสองแบบยังไม่เพิ่มคะแนนรวม','Macro DEV Water IoU เฉลี่ยข้ามสาม seed macro scores');
 const data=content.models.map((r,i)=>({name:methodNames[i],labels:['Macro DEV Water IoU'],values:[+r.macro_dev_iou]}));
 chart(s,7,data,.58,1.73,8.80,4.88,{valAxisMaxVal:.8,dataLabelFontSize:20,dataLabelPosition:'ctr',dataLabelColor:C.white,dataLabelFontBold:true},content.models.map(r=>[+r.seed_macro_sample_sd]));
 paragraph(s,'Baseline มี mean\nสูงสุดใน DEV นี้',9.62,2.11,3.03,1.16,26,{bold:true,color:C.blue});
 paragraph(s,'ผลต่างจาก Baseline\nV2-A  −0.0164\nV2-B  −0.0264',9.62,4.02,3.03,1.72,22);
 footer(s,7,'Error bars คือ Sample SD ข้าม 3 seed macro scores. ไม่มีการอ้างนัยสำคัญทางสถิติ');
}
// 08. Event heterogeneity and seed variability.
{
 const s=newSlide(8,'คะแนนและความผันผวนต่างกันตามเหตุการณ์','Mean Water IoU และ Sample SD ข้ามสาม seeds ภายในแต่ละ event');
 const data=methods.map((m,i)=>({name:methodNames[i],labels:['USA','Sri Lanka','Spain'],values:evs.map(e=>+content.events.find(r=>r.method===m&&r.event===e).mean_iou)}));
 const err=methods.map(m=>evs.map(e=>+content.events.find(r=>r.method===m&&r.event===e).sample_sd));
 chart(s,8,data,.56,1.76,9.15,4.98,{showValue:false},err);
 text(s,'Sri Lanka',9.96,2.02,2.66,.45,24,{bold:true,color:C.blue});
 text(s,'Baseline IoU',9.96,2.56,2.66,.4,20,{color:C.muted});
 [['42','0.7065'],['123','0.7011'],['777','0.3891']].forEach((r,i)=>{
  text(s,'Seed '+r[0],9.96,3.22+i*.70,1.38,.42,18);
  text(s,r[1],11.38,3.20+i*.70,1.22,.48,23,{bold:true,color:i===2?C.orange:C.ink});
 });
 footer(s,8,'คะแนนแต่ละ event มาจากโมเดลของ fold นั้น. ความต่างเป็นข้อสังเกต ไม่ใช่ causal country effect');
}
// 09. Preserve the full scientific source figure, including all legends.
{
 const s=newSlide(9,'Seed 777 พลาดน้ำในภาพ Sri Lanka','Selected DEV case: Sri-Lanka_534068. น้ำใน GT 98.14% ของ valid pixels');
 await image(s,'07_sri_lanka_seed_failure.png',.56,1.67,12.15,5.30);
 footer(s,9,'Selected case. สีส้มคือ False Negative. ภาพนี้ไม่พิสูจน์สาเหตุของความไม่เสถียรทั้งหมด');
}
// 10. Different estimands are named next to the comparison.
{
 const s=newSlide(10,'ผลของ Baseline Deep Ensemble');
 text(s,'0.6483',.77,1.33,3.65,.78,48,{bold:true,color:C.green});
 text(s,'Macro DEV Ensemble IoU',.81,2.13,4.1,.35,18,{color:C.muted});
 paragraph(s,'Mean single-model Macro IoU\n0.6143  (ผลต่าง +0.0340 IoU points)',5.05,1.35,7.52,1.1,23);
 const data=[{name:'Mean single-model IoU',labels:['USA','Sri Lanka','Spain'],values:evs.map(e=>+content.events.find(r=>r.method==='baseline'&&r.event===e).mean_iou)},
 {name:'IoU of probability ensemble',labels:['USA','Sri Lanka','Spain'],values:evs.map(e=>+content.ensemble.find(r=>r.validation_event===e).iou)}];
 chart(s,10,data,.62,2.70,12.0,4.12,{chartColors:[C.blue,C.green],valAxisMaxVal:.85,dataLabelFontSize:17,legendFontSize:15});
 footer(s,10,'Baseline 3 seeds ภายใน fold เดียวกัน. เป็นการเปรียบเทียบเชิงพรรณนาของ estimands ต่างกันบน DEV');
}
// 11. Real array-based map with compact definitions and scope labels.
{
 const s=newSlide(11,'แผนที่ความไม่แน่นอนของ Ensemble');
 await image(s,'08_sri_lanka_ensemble_uq.png',.43,1.36,8.58,5.49);
 text(s,'Predictive Entropy',9.25,1.73,3.48,.50,22,{bold:true,color:C.blue});
 paragraph(s,'ความไม่แน่นอนของ\nprobability เฉลี่ย',9.25,2.30,3.48,.93,21);
 text(s,'Mutual Information',9.25,3.52,3.48,.47,22,{bold:true,color:C.blue});
 paragraph(s,'ความเห็นต่างของ\nสมาชิก Ensemble',9.25,4.08,3.48,.88,21);
 paragraph(s,'ผลระดับภาพ 141 DEV chips\nPixel error audit: 9 selected',9.25,5.32,3.48,.86,18.5,{color:C.muted});
 text(s,'MI ต่ำยังทำนายผิดได้',9.25,6.37,3.48,.42,22,{bold:true,color:C.orange});
 footer(s,11,'Selected Sri Lanka DEV example. UQ เป็นสัญญาณสำหรับตรวจเพิ่ม ไม่รับรองความถูกต้องทุกพิกเซล');
}
// 12. Answer the research questions and define the next validation step.
{
 const s=newSlide(12,'ข้อค้นพบและสิ่งที่ต้องยืนยันต่อ');
 text(s,'Sampling',.80,1.62,2.9,.48,25,{bold:true,color:C.blue});
 paragraph(s,'Baseline ให้ Macro DEV IoU สูงสุด\n0.6143 ในสามวิธีที่ทดลอง',3.70,1.58,8.79,.96,26);
 text(s,'Seed stability',.80,3.08,2.9,.48,25,{bold:true,color:C.blue});
 paragraph(s,'Sri Lanka มีความไวต่อ seed และพลาดน้ำมากในบางภาพ',3.70,3.04,8.79,.96,26);
 text(s,'Ensemble / UQ',.80,4.54,2.9,.48,25,{bold:true,color:C.green});
 paragraph(s,'Baseline Ensemble ได้ Macro DEV IoU 0.6483\nและสร้างแผนที่ Entropy / MI ได้',3.70,4.50,8.79,1.10,26);
 paragraph(s,'ขั้นถัดไป: Independent labelled events\nและ Ground Truth ประเทศไทยที่สอดคล้องด้านเวลาและนิยาม',.81,6.06,11.8,.84,22,{bold:true});
 footer(s,12,'ผลหลักเป็น Development Validation จากสาม events. ยังไม่ใช่ Independent Final TEST');
}
// A. Implementation details stay in backup slides.
{
 const s=newSlide(13,'Appendix A: รายละเอียดการฝึกและ Sampling');
 table(s,13,[['รายการ','ค่าที่ใช้'],['Loss','0.5 masked BCE + 0.5 soft Dice'],['Optimizer','AdamW, lr 0.0003, weight decay 0.0001'],['Batch / Max epochs / Patience','2 / 25 / 6'],['TRAIN augmentation','Crop 256, H/V flips, rotations 0/90/180/270°'],['VALID','ภาพเต็ม 512, ไม่มี augmentation'],['Normalization preset','VV [−35, 5], VH [−40, 0], clip แล้ว scale [0, 1]'],['Valid pixels','Label ≠ −1 และ SAR ผ่าน finite/nodata mask']],.64,1.48,12.0,3.70,[4.05,7.95],18);
 text(s,'V2-A: P(i) = 1 / (K_events × N_event(i))',.76,5.40,11.8,.40,21);
 text(s,'V2-B: P(i) = 0.5 / N_train + 0.5 / (5 × N_bin(i))',.76,5.97,11.8,.40,21);
 text(s,'Bins: f=0; 0<f<0.01; 0.01≤f<0.10; 0.10≤f<0.50; 0.50≤f≤1',.76,6.54,11.8,.35,18);
 footer(s,13,'TRAIN-only full-chip coverage. SAR units ตาม dataset documentation; local TIFF units metadata ว่าง');
}
// B. Complete 27-run numerical record in editable cells.
{
 const s=newSlide(14,'Appendix B: คะแนนครบ 27 Runs','Water IoU ของ VALID event ใน checkpoint ของแต่ละ fold / seed');
 const r=[['Method','Seed','USA','Sri Lanka','Spain']];
 methods.forEach((m,i)=>[42,123,777].forEach(seed=>r.push([methodNames[i],seed,...evs.map(e=>fmt(content.runs.find(v=>v.method===m&&+v.seed===seed&&v.event===e).iou))])));
 table(s,14,r,.72,1.78,11.90,4.62,[2.2,1.3,2.7,3.0,2.7],19,{margin:[3,8,3,8]});
 footer(s,14,'ทุก seed อยู่ในการรายงาน รวม seed 777. ห้ามตีความ 27 runs เป็น 27 เหตุการณ์อิสระ');
}
// C. Population and selected sample remain visibly separate.
{
 const s=newSlide(15,'Appendix C: ผล UQ และขอบเขตตัวอย่าง');
 text(s,'ผลรวมราย event จาก 141 DEV ภาพ',.73,1.37,11.8,.43,23,{bold:true,color:C.blue});
 const r=[['DEV event','Recall','Brier','Entropy (bits)','MI (bits)'],...content.ensemble.map(v=>[v.validation_event.replace('-',' '),fmt(v.recall),fmt(v.brier),fmt(v.mean_predictive_entropy_bits),fmt(v.mean_mutual_information_bits)])];
 table(s,15,r,.72,1.99,11.90,1.78,[3.0,2.0,2.0,2.8,2.1],18);
 text(s,'Error capture เฉพาะ 9 selected images',.73,4.03,11.8,.43,23,{bold:true,color:C.orange});
 const t=[['พื้นที่ (3 ภาพต่อพื้นที่)','Entropy capture','MI capture'],...content.selected.map(v=>[v.event.replace('-',' '),(100*+v.entropy_capture).toFixed(1)+'%',(100*+v.mi_capture).toFixed(1)+'%'])];
 table(s,15,t,.72,4.65,11.90,1.78,[5.5,3.2,3.2],19);
 footer(s,15,'เลือก top-10% uncertainty ภายในแต่ละภาพ แล้วรวม captured errors / errors ทั้งหมด. ไม่ใช่ผล error detection ของ 141 ภาพ');
}
// D. Preserve counts and data roles without mixing protocols.
{
 const s=newSlide(16,'Appendix D: ที่มาข้อมูลและบทบาทชุดทดสอบ');
 table(s,16,[['DEV event prefix','Chips'],['Mekong',30],['Nigeria',18],['Pakistan',28],['Somalia',26],['Spain',30],['Sri Lanka',42],['USA',69]],.65,1.58,4.05,4.40,[2.9,1.15],18.5);
 table(s,16,[['กลุ่มข้อมูล','บทบาท'],['USA / Sri Lanka / Spain','VALID events ในสาม DEV folds'],['India / Paraguay / Ghana','Historical TEST ที่เคยตรวจแล้ว'],['Bolivia','Holdout เดิมที่เคยตรวจแล้ว'],['Thailand Phimai','Diagnostic pilot; ยังต้องมี aligned GT']],5.05,1.58,7.58,4.40,[3.0,4.58],18.5);
 paragraph(s,'Dataset docs ระบุ hand-labelled 446 และ weak-labelled 4,385 ในหมวด flood-event data\nการทดลอง V2 นี้ใช้ hand-labelled subset 243 คู่',.73,6.23,11.8,.70,18.5);
 footer(s,16,'Mekong เป็นชื่อ prefix ของชุดข้อมูล ไม่ใช่ Thailand quantitative test');
}
// E. Equations are editable text, with complete definitions in notes.
{
 const s=newSlide(17,'Appendix E: นิยามเมตริกและความไม่แน่นอน');
 const left=[['Water IoU','TP / (TP + FP + FN)'],['Recall','TP / (TP + FN)'],['Ensemble probability','P_mean = (P_42 + P_123 + P_777) / 3'],['Brier score','mean_valid_pixels (P_mean − y)²']];
 left.forEach((r,i)=>{text(s,r[0],.77,1.55+i*1.19,5.85,.4,22,{bold:true,color:C.blue});text(s,r[1],.77,2.02+i*1.19,5.85,.49,20.5);});
 text(s,'Predictive entropy',7.1,1.55,5.45,.4,22,{bold:true,color:C.blue});
 paragraph(s,'H(p) = −p log₂(p)\n            − (1−p) log₂(1−p)',7.1,2.02,5.45,1.0,23);
 text(s,'Mutual information',7.1,3.40,5.45,.4,22,{bold:true,color:C.blue});
 paragraph(s,'MI = H(P_mean)\n        − mean_member H(P_member)',7.1,3.88,5.45,1.0,22);
 text(s,'Error capture',7.1,5.20,5.45,.4,22,{bold:true,color:C.blue});
 paragraph(s,'Errors ใน top-10% uncertainty\nหารด้วย errors ทั้งหมดของภาพที่เลือก',7.1,5.67,5.45,.95,21);
 footer(s,17,'Entropy/MI ใช้ bits. IoU เมื่อ union=0 ให้ NaN. Error หมายถึง FP + FN');
}
// F. Bibliography, no invented sources or author identity.
{
 const s=newSlide(18,'Appendix F: เอกสารอ้างอิง');
 const refs=[['Sen1Floods11','Bonafilia et al. (2020). CVPR Workshops.\nDataset repository และ documentation ของผู้จัดทำ'],['U-Net','Ronneberger, Fischer & Brox (2015).\nU-Net: Convolutional Networks for Biomedical Image Segmentation'],['Deep Ensembles','Lakshminarayanan, Pritzel & Blundell (2017). NeurIPS 30.\nSimple and Scalable Predictive Uncertainty Estimation using Deep Ensembles'],['หลักฐานโปรเจ็กต์','27 histories / checkpoints; V2 split CSVs;\nM8.0A full DEV outputs และ 9 selected preview arrays']];
 refs.forEach((r,i)=>{text(s,r[0],.77,1.43+i*1.33,3.1,.40,23,{bold:true,color:C.blue});paragraph(s,r[1],4.0,1.42+i*1.33,8.57,.90,19.5);});
 footer(s,18,'รายละเอียด URL และ source-file provenance อยู่ใน speaker notes และ presentation/evidence/');
}

await fs.mkdir(path.join(DIR,'.build'),{recursive:true});
await fs.mkdir(path.join(P,'output'),{recursive:true});
const draft=path.join(DIR,'.build','FloodAI_Research_TH_draft.pptx');
await pptx.writeFile({fileName:draft,compression:true});

// PptxGenJS does not expose custom error bars. Add standard OOXML error bars
// using the exact verified SD values. Charts and their workbooks stay native.
const zip=await JSZip.loadAsync(await fs.readFile(draft));
// Version 4.0.1 emits content-type overrides for non-existent unused masters.
// Remove only orphan declarations; do not alter any live slide/master relationship.
let contentTypes=await zip.file('[Content_Types].xml').async('string');
contentTypes=contentTypes.replace(/<Override\b[^>]*\bPartName="([^"]+)"[^>]*\/>/g,(entry,name)=>zip.file(name.replace(/^\//,''))?entry:'');
zip.file('[Content_Types].xml',contentTypes);
for(const spec of errorSpecs){
  let xml=await zip.file(spec.part).async('string');
  let si=0;
  xml=xml.replace(/<c:ser>([\s\S]*?)<\/c:ser>/g,(whole,body)=>{
    const vals=spec.values[si++];
    if(!vals)throw new Error('Missing error bar series');
    const lit='<c:numLit><c:formatCode>0.0000</c:formatCode><c:ptCount val="'+vals.length+'"/>'+vals.map((v,i)=>'<c:pt idx="'+i+'"><c:v>'+v+'</c:v></c:pt>').join('')+'</c:numLit>';
    const err='<c:errBars><c:errDir val="y"/><c:errBarType val="both"/><c:errValType val="cust"/><c:noEndCap val="0"/><c:plus>'+lit+'</c:plus><c:minus>'+lit+'</c:minus><c:spPr><a:ln w="12700"><a:solidFill><a:srgbClr val="142638"/></a:solidFill><a:prstDash val="solid"/></a:ln></c:spPr></c:errBars>';
    if(!body.includes('<c:cat>'))throw new Error('Cannot locate category insertion point');
    return '<c:ser>'+body.replace('<c:cat>',err+'<c:cat>')+'</c:ser>';
  });
  if(si!==spec.values.length)throw new Error('Error bar series count mismatch');
  zip.file(spec.part,xml);
}
const finalPath=path.join(P,'output',process.argv[2]||'FloodAI_Research_Presentation_TH_Final.pptx');
await fs.writeFile(finalPath,await zip.generateAsync({type:'nodebuffer',compression:'DEFLATE'}));
await fs.writeFile(path.join(DIR,'deck_manifest.json'),JSON.stringify(manifest,null,2));
console.log(JSON.stringify({file:finalPath,slides:pptx._slides.length,charts:manifest.charts.length,tables:manifest.tables.length,errorbarCharts:errorSpecs.length},null,2));
