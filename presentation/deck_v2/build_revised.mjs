import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {createRequire} from 'node:module';
const D=path.dirname(fileURLToPath(import.meta.url)),P=path.dirname(D),ROOT=path.dirname(P);
const require=createRequire(path.join(P,'deck/tooling/package.json'));
const PptxGenJS=require('pptxgenjs'),JSZip=require('jszip');
const data=JSON.parse(await fs.readFile(path.join(P,'deck/deck_content.json'),'utf8'));
const assets=JSON.parse(await fs.readFile(path.join(D,'asset_manifest.json'),'utf8'));
const pptx=new PptxGenJS();pptx.layout='LAYOUT_WIDE';pptx.lang='th-TH';
pptx.author='FloodAI-Research';pptx.title='FloodAI-Research: Preliminary Findings and Completion Plan';
pptx.subject='26-slide revised Thai research presentation';
pptx.theme={headFontFace:'Tahoma',bodyFontFace:'Tahoma',lang:'th-TH'};
const C={navy:'183B61',ink:'183047',blue:'2677AF',orange:'D98C35',green:'2E8B74',red:'CB5360',gray:'53697E',pale:'EFF4F8',line:'D5E0E9',white:'FFFFFF'};
const manifest={authoring:'PptxGenJS 4.0.1',user_override:'User approved PptxGenJS as the local authoring fallback.',total:26,slides:[],charts:[],tables:[],diagrams:[]};
const refs={dataset:'https://github.com/cloudtostreet/Sen1Floods11',unet:'https://arxiv.org/abs/1505.04597',ensemble:'https://papers.neurips.cc/paper/2017/hash/9ef2ed4b7fd2c810847ffa5fa85bce38-Abstract.html',urban:'https://openaccess.thecvf.com/content/CVPR2024W/EarthVision/html/Zhao_UrbanSARFloods_Sentinel-1_SLC-Based_Benchmark_Dataset_for_Urban_and_Open-Area_Flood_CVPRW_2024_paper.html'};
const claimSources=Object.fromEntries(data.slides.flatMap(v=>v.claim_ids.map(id=>[id,v.source])));
const errors=[];let number=0;
const f=v=>(+v).toFixed(4),evs=['USA','Sri-Lanka','Spain'];
function text(s,t,x,y,w,h,size=22,o={}){s.addText(t,{x,y,w,h,fontFace:'Tahoma',fontSize:size,color:C.ink,margin:0,valign:'mid',paraSpaceAfterPt:0,breakLine:false,lineSpacingMultiple:1.05,...o});}
function para(s,t,x,y,w,h,size=22,o={}){text(s,t,x,y,w,h,size,{valign:'top',...o});}
function line(s,x1,y1,x2,y2,color=C.line,width=1,arrow=false){s.addShape(pptx.ShapeType.line,{x:Math.min(x1,x2),y:Math.min(y1,y2),w:Math.abs(x2-x1),h:Math.abs(y2-y1),flipH:x2<x1,flipV:y2<y1,line:{color,width,...(arrow?{endArrowType:'triangle'}:{})}});}
function rect(s,x,y,w,h,fill=C.pale,stroke=fill){s.addShape(pptx.ShapeType.rect,{x,y,w,h,fill:{color:fill},line:{color:stroke,width:.8}});}
function node(s,label,x,y,w,h,fill=C.pale,color=C.ink,size=21){rect(s,x,y,w,h,fill);text(s,label,x+.09,y+.06,w-.18,h-.12,size,{align:'center',color});}
function slide(title,section,narration,transition,claims=[],sources=[],scope=''){
 const terms={'MacroDEVWaterIoU':'Macro DEV Water IoU','BaselineEnsemble':'Baseline Ensemble','Baselineensemble':'Baseline ensemble','GroundTruth':'Ground Truth','SampleSD':'Sample SD','SmallUNet':'Small U-Net','Pwater':'P(water)','VALIDเลือกcheckpoint':'VALID เลือก checkpoint','checkpointmetadata':'checkpoint metadata','independentfinaltest':'independent final test','independentlabelledevents':'independent labelled events','independentreference':'independent reference','labelledevents':'labelled events','pixelerrordetection':'pixel error detection','pixelerrordiagnostics':'pixel error diagnostics','pixelUQselecteddiagnostics':'pixel UQ selected diagnostics','pixelUQaudit':'pixel UQ audit','eventseedfailureanalysis':'event / seed / failure analysis','eventนั้น':'event นั้น','developmentvalidation':'development validation','developmentpool':'development pool','validationevent':'validation event','validationevents':'validation events','finalexperiment':'final experiment','finalmodels':'final models','finaltrainingevaluationplan':'final training / evaluation plan','finalruns':'final runs','stoppingrule':'stopping rule','TRAINlabels':'TRAIN labels','fullchip':'full-chip','coveragebin':'coverage bin','samplingpolicy':'sampling policy','seedinstability':'seed instability','seed777':'seed 777','seed42':'seed 42','seed123':'seed 123','seeds42':'seeds 42','SriLanka':'Sri Lanka','SARonly':'SAR-only','UQระดับภาพ':'UQ ระดับภาพ','relatedwork':'related work','annotationguide':'annotation guide','runmanifest':'run manifest','reproducibilitypackage':'reproducibility package','errordiagnostics':'error diagnostics','missedwater':'missed water','singlemodel':'single-model','macroIoU':'macro IoU'};
 for(const [from,to] of Object.entries(terms))narration=narration.replaceAll(from,to);
 narration=narration.replace(/([ก-๙])([A-Za-z0-9])/g,'$1 $2').replace(/([A-Za-z0-9])([ก-๙])/g,'$1 $2');
 scope=scope.replaceAll(' • ','   ');
 const s=pptx.addSlide();const n=++number;s.background={color:C.white};
 text(s,section,.62,.23,11.9,.24,12,{color:C.blue,bold:true});
 text(s,title,.62,.64,12.08,.67,32,{bold:true,color:C.navy});
 line(s,.62,1.43,12.68,1.43,C.line,.8);
 text(s,scope||'FloodAI-Research   ผลการวิจัยเบื้องต้น',.65,7.08,11.45,.23,10.5,{color:C.gray});
 text(s,String(n).padStart(2,'0'),12.13,7.06,.54,.25,11,{align:'right',color:C.gray});
 const local=['presentation/plan_v2/SLIDE_STORYBOARD_TH.md',...sources];
 const notes=narration+'\n\nประโยคเชื่อมไปหน้าถัดไป\n'+transition+'\n\nSources / evidence\n'+local.map(p=>p.startsWith('https://')?p:path.join(ROOT,p)).join('\n')+'\n\nClaim IDs: '+(claims.join(', ')||'NARRATIVE_OR_PROPOSED_PLAN')+'\n\nขอบเขต\n'+(scope||'ผลเบื้องต้น ไม่มี independent final test ในชุดปัจจุบัน');
 s.addNotes(notes);manifest.slides.push({number:n,title:title||'FloodAI-Research: ชื่อเรื่องและขอบเขตงาน',section,narration,transition,claim_ids:claims,sources:local,scope:scope||'ผลเบื้องต้น ยังไม่มี independent final test ในชุดปัจจุบัน'});return s;
}
function takeaway(s,t,y=6.35,color=C.blue){text(s,t,.77,y,11.85,.46,23,{bold:true,color});}
function rows(s,items,x,y,w,gap=1.08,size=23){items.forEach((r,i)=>{text(s,r[0],x,y+i*gap,.95,.43,24,{bold:true,color:C.blue});para(s,r[1],x+1.10,y+i*gap,w-1.10,.88,size);});}
function table(s,rows,x,y,w,h,colW,size=20,opts={}){
 const cells=rows.map((r,ri)=>r.map((v,ci)=>({text:String(v),options:{fill:ri===0?C.navy:(ri%2===0?C.pale:C.white),color:ri===0?C.white:C.ink,bold:ri===0,align:ci===0?'left':'center',valign:'middle'}})));
 s.addTable(cells,{x,y,w,h,colW,rowH:h/rows.length,fontFace:'Tahoma',fontSize:size,margin:[5,9,5,9],border:{type:'solid',color:C.line,pt:.5},autoPage:false,paraSpaceAfterPt:0,...opts});
 manifest.tables.push({slide:number,data:rows});
}
async function img(s,name,x,y,w,h){const p=path.join(D,'assets',name+'.png'),b=await fs.readFile(p),iw=b.readUInt32BE(16),ih=b.readUInt32BE(20),ratio=Math.min(w/iw,h/ih);s.addImage({path:p,x:x+(w-iw*ratio)/2,y:y+(h-ih*ratio)/2,w:iw*ratio,h:ih*ratio,altText:name});}
function chart(s,series,x,y,w,h,opts={},sd=null){
 s.addChart(pptx.ChartType.bar,series,{x,y,w,h,barDir:'col',barGrouping:'clustered',chartColors:[C.blue,C.orange,C.green],showLegend:true,legendPos:'b',legendFontFace:'Tahoma',legendFontSize:15,legendColor:C.ink,showValue:true,showTitle:false,dataLabelColor:C.ink,dataLabelFontFace:'Tahoma',dataLabelFontSize:18,dataLabelFormatCode:'0.0000',dataLabelPosition:'outEnd',showBorder:false,showCatName:false,showSerName:false,catAxisLabelFontFace:'Tahoma',catAxisLabelFontSize:17,catAxisLabelColor:C.ink,catAxisLineColor:C.line,valAxisLabelFontFace:'Tahoma',valAxisLabelFontSize:14,valAxisLabelColor:C.gray,valAxisMinVal:0,valAxisMaxVal:1,valAxisMajorUnit:.2,valAxisNumFmt:'0.0',valAxisLineShow:false,catAxisLineShow:true,valGridLine:{color:C.line,width:.5},barGapWidthPct:85,barOverlapPct:-10,showShadow:false,chartArea:{fill:{color:C.white},border:{color:C.white,pt:0}},plotArea:{fill:{color:C.white},border:{color:C.white,pt:0}},...opts});
 const part=`ppt/charts/chart${manifest.charts.length+1}.xml`;manifest.charts.push({slide:number,part,series,sd});if(sd)errors.push({part,sd});
}

// 01. Scope and the original research title, without inventing personal details.
{
 const s=slide('','01 ปัญหาและคำถามวิจัย','งานนี้ศึกษาความน่าเชื่อถือของแผนที่น้ำผิวดินจาก Sentinel-1 SAR โดยดูทั้งผลเมื่อแยกเหตุการณ์ออกจากข้อมูลฝึก และความไม่แน่นอนของผลทำนาย การนำเสนอรอบนี้เป็นผลเบื้องต้นและแผนยืนยันผลขั้นสุดท้าย','ผมจะเริ่มจากปัญหาและขอบเขต ก่อนอธิบายการทดลองและผลที่ได้',['C01','C21'],['train_sar_unet.py']);
 rect(s,0,0,13.333,7.5,C.navy);
 text(s,'FLOODAI-RESEARCH',.82,.70,11.8,.4,18,{bold:true,color:'BBD6EA',charSpacing:1.5});
 para(s,'ความน่าเชื่อถือของแผนที่น้ำ\nจาก Sentinel-1 SAR',.82,1.55,11.6,1.60,42,{bold:true,color:C.white});
 para(s,'Towards Reliable SAR-Based Flood Mapping:\nDomain Generalization and Uncertainty Quantification\nAcross Geographic Regions',.85,3.65,11.65,1.55,23,{color:C.white});
 text(s,'ผลเบื้องต้นและแผนดำเนินงานจนเสร็จ',.85,5.65,11.6,.5,25,{color:'BBD6EA'});
 text(s,'19 พฤศจิกายน 2569',.85,6.75,11.6,.32,17,{color:'BBD6EA'});
}
// 02. An explicit route through the research story.
{
 const s=slide('ลำดับการนำเสนอ','01 ปัญหาและคำถามวิจัย','การนำเสนอแบ่งเป็นห้าช่วง เริ่มจากงานนี้ทำอะไรและถามอะไร ตามด้วยข้อมูลและวิธีตรวจคำถาม จากนั้นเป็นผลที่ได้จริง สถานะงานปัจจุบัน และแผนที่เหลือจนส่งงาน รอบนี้ยังไม่ได้มีผล independent final test จึงแยกผลที่ทำแล้วออกจากแผนอนาคตอย่างชัดเจน','เริ่มจากปัญหาที่ทำให้การมีแผนที่น้ำเพียงอย่างเดียวยังไม่ตอบเรื่องความน่าเชื่อถือ',[],[]);
 rows(s,[['01','ปัญหาและคำถามวิจัย'],['02','ข้อมูลและวิธีทดลอง'],['03','ผลและข้อค้นพบ'],['04','สถานะโครงการปัจจุบัน'],['05','แผนดำเนินงานจนเสร็จ']],1.0,1.85,10.9,.91,27);
}
// 03. Introduce the error before its technical vocabulary.
{
 const s=slide('แผนที่น้ำอาจพลาดน้ำหรือระบุน้ำเกินจริง','01 ปัญหาและคำถามวิจัย','ภาพนี้เป็นกรณีศึกษาที่เลือกจาก Spain บน DEV เริ่มอ่านจากแผนที่อ้างอิงสีน้ำเงินซึ่งระบุพื้นที่น้ำ แล้วดูผลของ Baseline ensemble พื้นที่สีส้มในภาพข้อผิดพลาดคือน้ำที่โมเดลพลาด ส่วนสีแดงคือพื้นดินที่ทำนายเป็นน้ำ ปัญหาที่เราสนใจจึงมีทั้งความถูกต้องของแผนที่และข้อมูลที่จะช่วยชี้บริเวณที่ควรตรวจเพิ่ม ภาพนี้เป็นตัวอย่าง ไม่ใช่หลักฐานแทนทุกเหตุการณ์','ก่อนตรวจความน่าเชื่อถือ ต้องกำหนดให้ชัดว่าโมเดลรับอะไรและทำนายอะไร',['C01','C18'],['presentation/deck_v2/asset_manifest.json'],'Selected DEV case: Spain_1167260 • Baseline Ensemble');
 for(const [i,k,l] of [[0,'gt','แผนที่อ้างอิง'],[1,'pred','ผลทำนาย'],[2,'error','ข้อผิดพลาด']]){text(s,l,.78+i*4.16,1.78,3.65,.4,23,{bold:true});await img(s,'Spain_1167260_'+k,.76+i*4.16,2.40,3.65,3.65);}
 text(s,'น้ำเงิน = น้ำ',.79,6.25,3.55,.35,18,{color:C.blue});text(s,'Error: เขียว = ตรวจน้ำถูก',4.95,6.25,3.75,.35,18,{color:C.green});para(s,'ส้ม = พลาดน้ำ (FN)\nแดง = ระบุน้ำเกิน (FP)',9.1,6.12,3.70,.73,18,{color:C.ink});
}
// 04. A concrete input/output example.
{
 const s=slide('อินพุตสองแบนด์ และความน่าจะเป็นของน้ำ','01 ปัญหาและคำถามวิจัย','โมเดลรับ Sentinel-1 SAR สองแบนด์คือ VV และ VH ซึ่งเป็นข้อมูลสองช่องของภาพเดียวกัน ในการทดลองนี้ไม่มีข้อมูลฝน โมเดลให้ความน่าจะเป็นของน้ำต่อพิกเซล แล้วใช้ threshold 0.50 แปลงเป็นแผนที่น้ำและพื้นดิน Target คือ surface water ณ เวลาที่ถ่ายภาพ จึงอาจรวมน้ำถาวรด้วย ภาพตัวอย่างเป็น Sri-Lanka_713926 จาก DEV Ground Truth หมายถึงแผนที่อ้างอิงสำหรับฝึกและตรวจผล','เมื่อขอบเขตของระบบชัดแล้ว คำถามวิจัยของเรามีสามข้อ',['C01','C02'],['train_sar_unet.py',refs.dataset],'Selected DEV example: Sri-Lanka_713926 • Target: surface water ณ เวลาถ่ายภาพ');
 const xs=[.78,4.98,9.16];for(const [i,k,l]of[[0,'vv','VV'],[1,'vh','VH'],[2,'prob','P(water)']]){text(s,l,xs[i],1.76,3.4,.4,21,{bold:true});await img(s,'Sri-Lanka_713926_'+k,xs[i],2.35,3.40,3.45);}
 para(s,'ภาพ SAR 512 × 512 × 2',.80,6.0,6.7,.5,24,{bold:true});para(s,'Threshold 0.50 ใช้แบ่งน้ำ / พื้นดิน',7.8,6.0,4.9,.65,22,{color:C.blue});
}
// 05. Stable RQ labels are reused in results and discussion.
{
 const s=slide('คำถามวิจัยสามข้อ','01 ปัญหาและคำถามวิจัย','คำถามแรกคือการปรับโอกาสเลือกภาพระหว่างฝึกช่วยเพิ่ม Water IoU บน validation events ที่แยกจาก TRAIN หรือไม่ ข้อที่สองคือผลต่างกันตามเหตุการณ์และ seed มากเพียงใด Seed คือการกำหนดความสุ่มในการฝึกซ้ำ เช่นการเริ่มค่าน้ำหนักและการสุ่มข้อมูล ข้อที่สามคือการรวม Baseline หลาย seeds ให้ผลอย่างไร และ uncertainty มีข้อมูลเกี่ยวกับข้อผิดพลาดมากเพียงใด คำถามเหล่านี้ครอบคลุมการวิเคราะห์ปัจจุบัน โดยไม่ได้ลงทะเบียนสมมติฐานทั้งหมดล่วงหน้า','ต่อไปคือแนวคิดจากงานเดิมที่ใช้สร้างการทดลองของเรา',['C11','C13','C14','C16','C20'],['presentation/evidence/claims_and_sources.csv']);
 rows(s,[['RQ1','ปรับวิธีเลือกภาพระหว่างฝึก\nแล้วคะแนนบนเหตุการณ์ที่กันออกดีขึ้นหรือไม่'],['RQ2','ผลต่างกันตามเหตุการณ์และ seed เพียงใด\nและโมเดลพลาดน้ำลักษณะใด'],['RQ3','Baseline Ensemble ให้ผลอย่างไร\nและ uncertainty ช่วยบอกข้อผิดพลาดได้เพียงใด']],.82,1.90,11.75,1.45,25);
}
// 06. Trace ideas to prior work without claiming an exhaustive literature gap.
{
 const s=slide('งานที่ใช้เป็นฐาน และสิ่งที่เราตรวจเอง','01 ปัญหาและคำถามวิจัย','Sen1Floods11 เป็นที่มาของข้อมูลและlabels U-Net ให้แนวคิด encoder และ decoder สำหรับการจำแนกระดับพิกเซล ส่วน Deep Ensembles เป็นฐานแนวคิดของการรวมโมเดลเพื่อศึกษาความไม่แน่นอน งาน UrbanSARFloods ปี2024ยังชี้ว่าความไม่สมดุลของข้อมูลและความแตกต่างของบริบทพื้นที่เป็นความท้าทายในงาน SAR flood mapping แต่เราไม่ได้ใช้ dataset หรือจำลองผลของงานนั้น การทดลองของเราจึงตรวจผล sampling และ seed sensitivity ภายใต้ Small U-Net และข้อมูลที่กำหนด ไม่อ้างว่าเป็นการทบทวนวรรณกรรมครบทุกงานหรือเป็นวิธีที่ดีที่สุด','เริ่มดูข้อมูลที่ใช้จริงในรอบพัฒนานี้',['C02','C06','C16'],[refs.dataset,refs.unet,refs.ensemble,refs.urban]);
 table(s,[['ฐานงานเดิม','นำมาใช้ใน FloodAI'],['Sen1Floods11 (2020)','ข้อมูล SAR และแผนที่อ้างอิง'],['U-Net (2015)','โครงสร้างสำหรับจำแนกรายพิกเซล'],['Deep Ensembles (2017)','รวมโมเดลและวิเคราะห์ความไม่แน่นอน']],.77,1.83,11.85,2.85,[4.2,7.65],22);
 para(s,'สิ่งที่เราตรวจเอง\nSampling สามแบบ ความไวต่อ seed และข้อจำกัดของ UQ',.83,5.12,11.65,1.13,25,{bold:true,color:C.blue});
}
// 07. Explain the actual development subset, not the full catalogue first.
{
 const s=slide('ข้อมูลพัฒนา 243 คู่ จาก 7 กลุ่มเหตุการณ์','02 ข้อมูลและวิธีทดลอง','ข้อมูลที่ใช้จริงในprotocolปัจจุบันเป็นคู่SARและLabelHand243คู่จากเจ็ดeventprefixes ไม่ใช่การนำทุกภาพในdatasetมาฝึก แต่ละภาพมีสองแบนด์VVและVHและมีแผนที่อ้างอิงคู่กัน Labelsคือ1น้ำ 0พื้นดินและลบ1บริเวณignore Mekongในคลังนี้เป็นกลุ่มข้อมูลกัมพูชา ไม่ใช่Thailandpilot จำนวน243คือinventoryสำหรับแบ่งfold และไม่ใช่จำนวนTRAINของทุกfold','จำนวนภาพแต่ละกลุ่มไม่เท่ากัน และแต่ละภาพก็มีสัดส่วนน้ำต่างกัน',['C02','C03'],['presentation/evidence/verified_rasters.csv',refs.dataset]);
 chart(s,[{name:'Image pairs',labels:['Mekong','Nigeria','Pakistan','Somalia','Spain','Sri Lanka','USA'],values:[30,18,28,26,30,42,69]}],.65,1.80,8.8,4.85,{barDir:'bar',showLegend:false,chartColors:[C.blue],valAxisMaxVal:80,valAxisMajorUnit:20,valAxisNumFmt:'0',dataLabelFormatCode:'0',dataLabelFontSize:19,catAxisLabelFontSize:18});
 text(s,'243',9.72,2.07,2.83,.88,62,{bold:true,color:C.blue});text(s,'คู่ SAR / Ground Truth',9.75,3.02,2.85,.65,19);para(s,'512 × 512 พิกเซล\nVV และ VH\nน้ำ / พื้นดิน / Ignore',9.75,4.15,2.85,1.55,21);
}
// 08. A measured distribution motivates the sampling hypotheses.
{
 const s=slide('ข้อมูลมีสัดส่วนน้ำไม่เท่ากัน','02 ข้อมูลและวิธีทดลอง','ตัวอย่างนี้ใช้TRAINของfoldที่กันUSAออก รวม174ภาพ แบ่งภาพด้วยสัดส่วนน้ำในGroundTruthเต็มภาพ ห้ากลุ่มมี14,38,70,36และ16ภาพตามลำดับ ภาพในกลุ่ม1ถึง10เปอร์เซ็นต์จึงพบมากกว่าภาพที่มีน้ำเกินครึ่งภาพ ขณะเดียวกันจำนวนภาพรายeventก็ต่างกัน นี่เป็นเหตุผลให้ทดลองปรับsamplingสองแนวทาง เป็นสมมติฐานเพื่อทดลอง ไม่ใช่ข้อพิสูจน์ว่าความไม่สมดุลเป็นสาเหตุของseedinstability','เราจะใช้โมเดลพื้นฐานเดียวกัน แล้วเปลี่ยนเฉพาะsamplingpolicyหลัก',['C03','C10'],['presentation/evidence/verified_coverage_bins.csv'],'ตัวอย่าง TRAIN ของ fold USA: 174 ภาพ • แบ่งกลุ่มจาก full-chip GT ของ TRAIN เท่านั้น');
 chart(s,[{name:'TRAIN chips',labels:['ไม่มีน้ำ','>0–<1%','1–<10%','10–<50%','≥50%'],values:[14,38,70,36,16]}],.66,1.88,8.9,4.65,{showLegend:false,valAxisMaxVal:80,valAxisMajorUnit:20,valAxisNumFmt:'0',dataLabelFormatCode:'0',catAxisLabelFontSize:16,chartColors:[C.blue]});
 para(s,'สองสมมติฐาน\n\nจำนวนภาพต่อ event\nอาจทำให้ถูกใช้ฝึก\nบ่อยต่างกัน\n\nสัดส่วนน้ำใน TRAIN\nอาจเกี่ยวกับการเรียนรู้',9.82,2.0,2.76,3.9,20);
 takeaway(s,'จึงทดลองสมดุลตาม “เหตุการณ์” และตาม “สัดส่วนน้ำ”',6.43);
}
// 09. An editable diagram of the actual implementation.
{
 const s=slide('Small U-Net สร้างแผนที่รายพิกเซลอย่างไร','02 ข้อมูลและวิธีทดลอง','Encoderใช้convolutionเรียนรู้featuresจากภาพและลดขนาดเชิงพื้นที่เพื่อเห็นบริบท Bottleneckประมวลผลระดับลึก Decoderขยายfeaturesกลับมาสู่ระดับพิกเซล Skipconnectionsส่งรายละเอียดจากencoderมาช่วยdecoder จากนั้นoutputlogitผ่านsigmoidเป็นPwater สถาปัตยกรรมจริงมีencoder16,32,64,128channels bottleneck256และdecoder128,64,32,16 รวม1,963,953parameters ทั้งสามวิธีsamplingใช้SmallUNetนี้เหมือนกัน TRAINสุ่มcrop256ขณะที่VALIDใช้ภาพเต็ม512','เมื่อโมเดลเหมือนกัน เราจะกันข้อมูลตามเหตุการณ์เพื่อวัดผลอย่างไร',['C06','C07'],['train_sar_unet.py','presentation/evidence/verified_runs.csv']);
 const stages=[['VV + VH',.75,2.6,1.6,1.15],['Encoder',2.98,2.6,2.1,1.15],['Bottleneck',5.62,3.5,2.05,1.15],['Decoder',8.23,2.6,2.1,1.15],['P(water)',10.94,2.6,1.65,1.15]];
 stages.forEach((r,i)=>node(s,r[0],r[1],r[2],r[3],r[4],i===4?C.blue:C.pale,i===4?C.white:C.ink,22));
 line(s,2.35,3.18,2.98,3.18,C.blue,1.5,true);line(s,5.08,3.18,5.36,3.18,C.blue,1.5);line(s,5.36,3.18,5.36,4.08,C.blue,1.5);line(s,5.36,4.08,5.62,4.08,C.blue,1.5,true);
 line(s,7.67,4.08,7.95,4.08,C.blue,1.5);line(s,7.95,3.18,7.95,4.08,C.blue,1.5);line(s,7.95,3.18,8.23,3.18,C.blue,1.5,true);line(s,10.33,3.18,10.94,3.18,C.blue,1.5,true);
 line(s,4.03,2.6,4.03,2.05,C.green,1.5);line(s,4.03,2.05,9.28,2.05,C.green,1.5);line(s,9.28,2.05,9.28,2.6,C.green,1.5,true);text(s,'Skip connections: ส่งรายละเอียดตำแหน่ง',4.35,1.66,4.65,.30,16,{color:C.green});
 text(s,'เรียนรู้ลักษณะ\nและบริบท',2.98,4.95,2.1,.95,22,{align:'center'});text(s,'ประมวลผล\nระดับลึก',5.62,4.95,2.05,.95,22,{align:'center'});text(s,'คืนความละเอียด\nรายพิกเซล',8.23,4.95,2.1,.95,22,{align:'center'});
 takeaway(s,'ใช้สถาปัตยกรรมเดียวกันทั้งสามวิธี Sampling',6.43);manifest.diagrams.push({slide:9,type:'editable actual-model flow'});
}
// 10. Event membership can be read directly rather than inferred from counts.
{
 const s=slide('กันหนึ่งเหตุการณ์ออกเป็น Validation','02 ข้อมูลและวิธีทดลอง','แต่ละแถวคือการฝึกโมเดลใหม่ของหนึ่งfold สีฟ้าคือTRAIN สีส้มคือVALID ตัวอย่างแถวSriLankaฝึกด้วยอีกหกกลุ่ม201ภาพและใช้SriLanka42ภาพเป็นVALID eventนั้นจึงไม่อยู่ในTRAINของโมเดลแถวนั้น อีกสองfoldกันUSAและSpainตามลำดับ VALIDใช้เลือกcheckpointด้วยจึงเป็นdevelopmentvalidation และนี่ไม่ใช่การหมุนครบทั้งเจ็ดevents IndiaParaguayGhanaกับBoliviaไม่อยู่ในdevelopmentpoolนี้','ต่อไปต้องกำหนดว่าพื้นที่น้ำที่ทำนายตรงกับreferenceมากเพียงใด',['C04','C05','C21'],['presentation/evidence/verified_splits.csv'],'ส้ม = VALID ใช้เลือก checkpoint • ฟ้า = TRAIN • ผลปัจจุบันเป็น Development Validation');
 const groups=[['Mekong',30],['Nigeria',18],['Pakistan',28],['Somalia',26],['Spain',30],['Sri Lanka',42],['USA',69]],holds=['USA','Sri Lanka','Spain'];
 groups.forEach((g,i)=>text(s,g[0],1.78+i*1.55,1.87,1.45,.34,14,{align:'center'}));
 holds.forEach((e,i)=>{text(s,'Fold '+(i+1),.74,2.48+i*1.15,.95,.44,18,{bold:true});groups.forEach((g,j)=>node(s,String(g[1]),1.78+j*1.55,2.4+i*1.15,1.45,.69,g[0]===e?C.orange:C.blue,C.white,21));text(s,`${[174,201,213][i]} TRAIN / ${[69,42,30][i]} VALID`,8.12,3.12+i*1.15,4.40,.30,15,{align:'right',color:C.gray});});
 takeaway(s,'เช่น Fold Sri Lanka: ฝึกอีก 6 events แล้วตรวจ Sri Lanka ทั้งเหตุการณ์',6.42);manifest.diagrams.push({slide:10,type:'editable event membership',groups,holds});
}
// 11. Teach the score before comparing it.
{
 const s=slide('Water IoU วัดการทับซ้อนของพื้นที่น้ำ','02 ข้อมูลและวิธีทดลอง','IoUดูพื้นที่น้ำที่ทำนายถูกเทียบกับพื้นที่ที่เป็นน้ำจริงหรือถูกทำนายเป็นน้ำ TPคือน้ำที่ถูกต้อง FPคือพื้นดินที่ทำนายเป็นน้ำ FNคือน้ำที่พลาด ตารางนี้เป็นภาพอธิบายตำแหน่งของสามประเภท ค่าIoUคำนวณTPหารด้วยTPบวกFPบวกFN ในผลหลักเรารวมconfusioncountsภายในeventก่อน เฉลี่ยสามeventsเท่ากันต่อseed แล้วสรุปMeanและSampleSDข้ามสามseeds คะแนน0.6143จึงไม่ใช่accuracy61.43เปอร์เซ็นต์ กรณีunionเป็นศูนย์ให้NaN','ด้วยเกณฑ์นี้ เราจึงเปรียบเทียบวิธีเลือกภาพทั้งสามแบบ',['C12'],['train_sar_unet.py','presentation/evidence/verified_seed_macros.csv']);
 table(s,[['Ground Truth','ทำนายเป็นน้ำ','ทำนายเป็นพื้นดิน'],['น้ำจริง','TP: ตรวจน้ำถูก','FN: พลาดน้ำ'],['พื้นดิน','FP: ระบุน้ำเกิน','TN: พื้นดินถูก']],.78,1.87,7.35,2.62,[2.25,2.55,2.55],20);
 text(s,'Water IoU',8.73,2.00,3.7,.46,26,{bold:true,color:C.blue});text(s,'TP',8.85,2.66,3.2,.44,30,{align:'center'});line(s,8.75,3.20,12.20,3.20,C.ink,1.2);text(s,'TP + FP + FN',8.75,3.33,3.45,.50,25,{align:'center'});
 rows(s,[['1','รวม TP, FP, FN ภายในเหตุการณ์ แล้วคำนวณ IoU'],['2','เฉลี่ย IoU ของ 3 เหตุการณ์เท่ากันต่อ seed'],['3','รายงาน Mean และ Sample SD ข้าม 3 seeds']],.86,4.95,11.5,.57,20);
}
// 12. Meaningful method names precede internal version labels.
{
 const s=slide('เปลี่ยนโอกาสเลือกภาพระหว่างฝึก','02 ข้อมูลและวิธีทดลอง','BaselineสลับภาพTRAINตามปกติหนึ่งครั้งต่อepoch V2Aให้น้ำหนักภาพตามขนาดeventเพื่อให้แต่ละeventมีโอกาสถูกเลือกเท่ากันในความคาดหมาย V2Bใช้ส่วนผสมห้าสิบเปอร์เซ็นต์สุ่มภาพแบบuniformและอีกห้าสิบเปอร์เซ็นต์เลือกcoveragebinแบบuniformแล้วเลือกภาพในbin ทั้งV2AและV2Bสุ่มคืนตัวอย่าง จำนวนdrawsต่อepochเท่ากับNtrain ห้ากลุ่มจึงไม่ได้ถูกสุ่มเท่ากันทั้งหมดในV2B และweightsอ้างfullchipTRAINlabelsเท่านั้น','แต่ละวิธีถูกฝึกซ้ำหลายseedและหลายfoldเพื่อไม่อิงผลครั้งเดียว',['C08','C09','C10'],['train_sar_unet.py','train_v2a_eventbalanced.py','m76b_water_sampler.py']);
 const a=[['Baseline','Shuffle ภาพ TRAIN ตามปกติ','ภาพแต่ละภาพถูกใช้หนึ่งครั้งต่อ epoch',C.blue],['Event-balanced (V2-A)','ให้โอกาสเลือกแต่ละเหตุการณ์เท่ากันโดยเฉลี่ย','ปรับโอกาสใช้ภาพจากเหตุการณ์ที่มีจำนวนภาพต่างกัน',C.orange],['Water-coverage (V2-B)','50% สุ่มภาพตามปกติ + 50% สุ่มตามกลุ่มสัดส่วนน้ำ','ปรับโอกาสเลือกภาพตามสัดส่วนน้ำใน TRAIN',C.green]];
 a.forEach((r,i)=>{text(s,r[0],.80,1.80+i*1.45,11.7,.42,24,{bold:true,color:r[3]});text(s,r[1],.82,2.30+i*1.45,11.65,.44,24);text(s,r[2],.82,2.85+i*1.45,11.65,.35,18,{color:C.gray});});
}
// 13. Experimental design, all runs retained.
{
 const s=slide('เปรียบเทียบ 27 ครั้งภายใต้กติกาหลักเดียวกัน','02 ข้อมูลและวิธีทดลอง','สามmethodsแต่ละวิธีฝึกด้วยseeds42,123และ777ครบสามDEVfoldsรวม27runs ไม่ใช่27สถาปัตยกรรม คงโมเดลlossnormalizationfoldsthresholdและtrainingprotocolหลักเดียวกัน สิ่งที่เปลี่ยนคือsamplingpolicy การสุ่มcropและลำดับข้อมูลไม่จำเป็นต้องเหมือนกันทั้งหมดแม้ใช้seedเลขเดียวกัน เรารายงานทุกseedรวมseedที่ได้คะแนนต่ำ เพื่อไม่เลือกเฉพาะผลดี','เริ่มตอบRQ1ด้วยผลคะแนนรวมของสามวิธี',['C07','C11','C12'],['presentation/evidence/verified_runs.csv']);
 const a=[['3','วิธี Sampling'],['3','Seeds\n42 / 123 / 777'],['3','DEV folds']];
 a.forEach((r,i)=>{text(s,r[0],.85+i*4.15,1.95,3.4,.95,70,{bold:true,color:C.blue});para(s,r[1],.90+i*4.15,3.08,3.65,.90,22);});
 text(s,'รวม 27 training runs',.90,4.20,11.7,.65,34,{bold:true,color:C.navy});
 para(s,'เปลี่ยน seed เพื่อฝึกซ้ำด้วยความสุ่มต่างกัน\nคง architecture, loss, normalization และ threshold 0.50',.92,5.26,11.6,1.10,24);
}

// 14. The score now answers a previously introduced question.
{
 const s=slide('RQ1: Sampling ยังไม่เพิ่มคะแนนรวมบน DEV','03 ผลและข้อค้นพบ','กราฟนี้แสดงMacroDEVWaterIoUเฉลี่ยข้ามสามseedmacro scores Baselineได้0.6143 V2A0.5979และV2B0.5879 เส้นerrorbarคือSampleSDของสามseedmacro scores ผลต่างจากBaselineคือประมาณลบ0.0164และลบ0.0264ตามลำดับ ภายใต้กติกานี้Baselineมีค่าเฉลี่ยสูงสุด และยังไม่พบหลักฐานจากDEVว่าวิธีsamplingที่ทดลองเพิ่มคะแนนรวม ผลนี้ไม่ใช่ข้อพิสูจน์ว่าสองวิธีใช้ไม่ได้กับข้อมูลทุกชุด และยังไม่อ้างนัยสำคัญทางสถิติ','คะแนนรวมอาจซ่อนความแตกต่างระหว่างเหตุการณ์ จึงต้องแยกดูต่อ',['C12','C13'],['presentation/evidence/verified_models.csv'],'Development Validation • Error bars = Sample SD ข้ามสาม seed macro scores');
 const series=data.models.map((r,i)=>({name:['Baseline','V2-A','V2-B'][i],labels:['Macro DEV Water IoU'],values:[+r.macro_dev_iou]}));
 chart(s,series,.60,1.82,8.90,4.85,{valAxisMaxVal:.8,valAxisMajorUnit:.2,dataLabelPosition:'ctr',dataLabelColor:C.white,dataLabelFontBold:true,dataLabelFontSize:21},data.models.map(r=>[+r.seed_macro_sample_sd]));
 para(s,'Baseline สูงสุด\nใน DEV ชุดนี้',9.8,2.12,2.8,1.3,25,{bold:true,color:C.blue});
 para(s,'ผลต่างจาก Baseline\n\nV2-A  −0.0164\nV2-B  −0.0264\n\nหน่วย: IoU points',9.8,3.87,2.8,2.5,20);
}
// 15. All three seed results are visible, not just an SD whisker.
{
 const s=slide('RQ2: ความเสถียรต่างกันตามเหตุการณ์','03 ผลและข้อค้นพบ','หน้านี้แสดงผลBaselineสามseedsแยกตามevent USAและSpainมีคะแนนข้ามseedsใกล้กันกว่าSriLankaในผลที่มี SriLankaseed42และ123ได้ประมาณ0.7065และ0.7011แต่seed777เหลือ0.3891 ตัวเลขนี้แสดงความไวต่อการฝึกซ้ำในบางevent ไม่ได้เป็นcausalcountryeffect เพราะแต่ละeventมาจากโมเดลประจำfoldของตน เราเก็บseed777ไว้ในผลรวมทั้งหมดเพื่อสะท้อนความไม่เสถียรจริง','ดูภาพจริงเพื่อเข้าใจว่าคะแนนSriLankaที่ลดลงมีลักษณะอย่างไร',['C14'],['presentation/evidence/verified_runs.csv','presentation/evidence/verified_events.csv'],'Baseline เท่านั้น • ทุก seed อยู่ในการรายงาน • แต่ละ event ใช้โมเดลของ fold ตนเอง');
 const series=[42,123,777].map(seed=>({name:'Seed '+seed,labels:['USA','Sri Lanka','Spain'],values:evs.map(e=>+data.runs.find(r=>r.method==='baseline'&&+r.seed===seed&&r.event===e).iou)}));
 chart(s,series,.65,1.85,9.0,4.83,{chartColors:[C.blue,C.green,C.orange],dataLabelFontSize:14,valAxisMaxVal:.8});
 text(s,'Sri Lanka',9.91,2.05,2.7,.46,25,{bold:true,color:C.navy});para(s,'Seed 42   0.7065\nSeed 123 0.7011',9.91,2.85,2.7,1.1,21);text(s,'Seed 777',9.91,4.37,2.7,.43,22,{bold:true,color:C.orange});text(s,'0.3891',9.91,4.95,2.7,.62,35,{bold:true,color:C.orange});
}
// 16. Four large maps, with Thai labels and one common legend.
{
 const s=slide('Seed 777 พลาดน้ำมากในภาพตัวอย่างนี้','03 ผลและข้อค้นพบ','เริ่มจากGroundTruthซึ่งมีน้ำ98.14เปอร์เซ็นต์ของvalidpixelsในภาพSriLanka534068 จากนั้นเทียบpredictionที่threshold0.50ของสามseeds สองseedsแรกครอบคลุมน้ำเกือบทั้งภาพ ส่วนseed777ตรวจพบเพียงบางส่วน IoUจึงเป็น0.9917 0.9859และ0.2267ตามลำดับ นี่เป็นselectedDEVcaseซึ่งอธิบายลักษณะความผิดพลาดได้ แต่ไม่แทนทุกภาพและไม่พิสูจน์ว่าสัดส่วนน้ำเป็นสาเหตุเพียงอย่างเดียว','เมื่อผลจากต่างseedsต่างกัน เราจึงศึกษาการรวมprobabilityด้วยBaselineEnsemble',['C15'],['presentation/evidence/verified_high_water_cases.csv','presentation/deck_v2/asset_manifest.json'],'Selected DEV case: Sri-Lanka_534068 • สีน้ำเงิน = น้ำ • สีเทา = พื้นดิน');
 const panels=[['failure_gt','Ground Truth','น้ำใน GT 98.14%'],['failure_seed42','Seed 42','IoU 0.9917'],['failure_seed123','Seed 123','IoU 0.9859'],['failure_seed777','Seed 777','IoU 0.2267']];
 for(let i=0;i<4;i++){const x=.78+i*3.0;text(s,panels[i][1],x,1.90,2.8,.43,22,{bold:true,color:i===3?C.orange:C.navy});await img(s,panels[i][0],x,2.63,2.8,2.8);text(s,panels[i][2],x,5.70,2.8,.42,21,{bold:i===3,color:i===3?C.orange:C.ink});}
 takeaway(s,'พบ missed water รุนแรงในบาง seed แต่ยังไม่ได้แยกสาเหตุเชิงทดลอง',6.42);
}
// 17. Editable ensemble arithmetic; values are visibly illustrative.
{
 const s=slide('Baseline Deep Ensemble รวมผลอย่างไร','03 ผลและข้อค้นพบ','สำหรับvalidationeventหนึ่ง เราใช้เฉพาะBaselinecheckpointsของสามseedsที่ฝึกในfoldนั้น แล้วเฉลี่ยPwaterต่อพิกเซลก่อนใช้threshold ตัวเลข0.85 0.90และ0.10ในหน้านี้เป็นตัวอย่างสมมติเพื่ออธิบายการคำนวณ เฉลี่ยได้ประมาณ0.617จึงจัดเป็นน้ำที่threshold0.50 การรวมจริงไม่ได้เอาBaselineV2AและV2Bมารวม และไม่ได้ใช้สมาชิกข้ามfoldเพื่อประเมินDEVevent เพราะสมาชิกจากfoldอื่นอาจเคยฝึกด้วยeventนั้น','ต่อไปเป็นคะแนนที่ได้จริงจากการรวมBaselineสามseeds',['C16'],['results/event_level_v2/m80a_dev_ensemble_uq/m80a_members.csv',refs.ensemble],'ตัวอย่างตัวเลขสมมติเพื่ออธิบายวิธี • การทดลองจริงใช้ Baseline 3 seeds ภายใน fold เดียวกัน');
 const yy=[2.0,3.32,4.64];['0.85','0.90','0.10'].forEach((v,i)=>{node(s,'สมาชิก '+(i+1)+'\nP(water) = '+v,.88,yy[i],3.4,.99,C.pale,C.ink,22);line(s,4.28,yy[i]+.50,5.10,yy[i]+.50,C.blue,1.3);});
 line(s,5.10,2.50,5.10,5.14,C.blue,1.3);line(s,5.10,3.82,5.65,3.82,C.blue,1.5,true);
 node(s,'เฉลี่ย probability\n(0.85 + 0.90 + 0.10) / 3',5.65,3.19,3.6,1.25,C.pale,C.ink,20);line(s,9.25,3.82,9.82,3.82,C.blue,1.5,true);
 node(s,'0.617\nจัดเป็นน้ำ',9.82,3.19,2.68,1.25,C.blue,C.white,25);
 takeaway(s,'เฉลี่ยความน่าจะเป็นก่อน แล้วใช้ Threshold 0.50',6.44);manifest.diagrams.push({slide:17,type:'editable illustrative ensemble arithmetic',probabilities:[.85,.90,.10]});
}
// 18. Different estimands are named, with a cautious interpretation.
{
 const s=slide('RQ3: Ensemble ให้ Macro DEV IoU สูงขึ้น','03 ผลและข้อค้นพบ','BaselineEnsembleให้macroDEVIoU0.6483เทียบกับmeanของsinglemodelmacroIoU0.6143 ผลต่าง0.0340IoUpoints รายeventUSAเพิ่มจาก0.5383เป็น0.5487 SriLankaจาก0.5989เป็น0.6858 และSpainจาก0.7058เป็น0.7105 ตัวเลขสองชุดคำนวณต่างกัน ชุดแรกเฉลี่ยคะแนนโมเดลเดี่ยว อีกชุดเฉลี่ยprobabilityก่อนคำนวณคะแนน เราจึงรายงานเป็นความแตกต่างเชิงพรรณนา ไม่อ้างว่าชนะทุกseedทุกพื้นที่หรือมีนัยสำคัญ และยังเป็นDEVที่ใช้เลือกcheckpointแล้ว Ensembleยังมีต้นทุนinferenceมากกว่าโมเดลเดี่ยว','นอกจากแผนที่เฉลี่ย เราใช้ผลสมาชิกศึกษาความไม่แน่นอนได้ด้วย',['C17','C18'],['presentation/evidence/verified_ensemble_events.csv','presentation/evidence/verified_models.csv'],'Development Validation • Mean(single-model IoU) และ IoU(mean probabilities) คำนวณต่างกัน');
 text(s,'0.6143',.82,1.80,3.4,.65,39,{bold:true,color:C.blue});text(s,'Mean single-model Macro IoU',.86,2.49,5.3,.35,17,{color:C.gray});
 text(s,'0.6483',7.1,1.80,3.4,.65,39,{bold:true,color:C.green});text(s,'Macro Ensemble IoU',7.14,2.49,4.9,.35,17,{color:C.gray});
 text(s,'+0.0340 IoU points',4.25,1.98,2.8,.36,18,{color:C.gray,align:'center'});
 const series=[{name:'Mean single-model IoU',labels:['USA','Sri Lanka','Spain'],values:evs.map(e=>+data.events.find(r=>r.method==='baseline'&&r.event===e).mean_iou)},{name:'IoU of probability ensemble',labels:['USA','Sri Lanka','Spain'],values:evs.map(e=>+data.ensemble.find(r=>r.validation_event===e).iou)}];
 chart(s,series,.64,3.0,12.0,3.76,{chartColors:[C.blue,C.green],valAxisMaxVal:.8,dataLabelFontSize:17,legendFontSize:14});
}
// 19. A compact counterexample separates uncertainty and disagreement.
{
 const s=slide('Entropy กับ MI วัดคนละลักษณะของความไม่แน่นอน','03 ผลและข้อค้นพบ','PredictiveEntropyวัดความไม่แน่นอนของprobabilityเฉลี่ย โดยสูงเมื่อค่าเฉลี่ยใกล้0.5 MIคำนวณentropyของค่าเฉลี่ยลบค่าเฉลี่ยentropyของสมาชิกและใช้เป็นตัวแทนdisagreement ในตัวอย่างสมมติแรกทุกสมาชิกให้0.5จึงมีEntropyหนึ่งbitแต่MIศูนย์ ตัวอย่างที่สองให้0.95 0.95และ0.05 ค่าเฉลี่ย0.65มีEntropyประมาณ0.9341และMI0.6477bits สมาชิกจึงเห็นต่างกัน ทั้งนี้ถ้าสมาชิกมั่นใจผิดเหมือนกัน MIอาจต่ำ จึงไม่ใช่probabilityของการทำนายผิด','นำความหมายนี้ไปอ่านแผนที่จริงและดูขอบเขตการตรวจerror',['C20'],['m80a_dev_ensemble_uq.py',refs.ensemble],'ตัวอย่างสมมติ • Entropy และ MI ใช้หน่วย bits • MI เป็นตัวแทน disagreement');
 text(s,'Predictive Entropy',.82,1.81,5.75,.45,26,{bold:true,color:C.blue});para(s,'ความไม่แน่นอนของ\nprobability เฉลี่ย',.84,2.42,5.7,.95,24);
 text(s,'Mutual Information (MI)',7.04,1.81,5.55,.45,26,{bold:true,color:C.blue});para(s,'ความเห็นต่างของ\nสมาชิก Ensemble',7.06,2.42,5.5,.95,24);
 const H=p=>-p*Math.log2(p)-(1-p)*Math.log2(1-p);const h=H(.65),mi=h-H(.95);
 table(s,[['ตัวอย่างสมมติ','P(water) จากสมาชิก','Entropy','MI'],['ทุกตัวให้ค่าใกล้ 0.5','0.50 / 0.50 / 0.50','1.0000','0.0000'],['สมาชิกให้ค่าต่างกัน','0.95 / 0.95 / 0.05',f(h),f(mi)]],.77,3.80,11.85,1.80,[3.45,4.1,2.15,2.15],19);
 takeaway(s,'หากทุกตัวผิดเหมือนกันอย่างมั่นใจ MI ก็อาจต่ำ',6.35,C.orange);
}
// 20. A selected map is separate from the population summary.
{
 const s=slide('RQ3: UQ ให้ข้อมูลเพิ่ม แต่ยังพลาดข้อผิดพลาดได้','03 ผลและข้อค้นพบ','ภาพนี้เป็นselectedDEVcaseSriLanka845821 น้ำในGTมี97.42เปอร์เซ็นต์ เริ่มดูGTและข้อผิดพลาดสีส้มคือน้ำที่Ensembleพลาด แล้วเทียบEntropyและMIบนสเกลศูนย์ถึงหนึ่งbits MIสามารถต่ำได้แม้มีmissedwater ผลEnsembleและสรุปUQระดับภาพมีครบ141ภาพ แต่การตรวจpixelerrordetectionแบบละเอียดมีarraysที่เลือกไว้เพียง9ภาพ ในภาพตัวอย่างนี้Entropyจับerrorได้46.8เปอร์เซ็นต์ส่วนMIได้2.6เปอร์เซ็นต์เมื่อเลือกtop10เปอร์เซ็นต์ วิธีtop10เปอร์เซ็นต์errorcaptureคือเลือกพิกเซลuncertaintyสูงสุดสิบเปอร์เซ็นต์ภายในแต่ละภาพ แล้วหารจำนวนerrorที่จับได้ด้วยerrorทั้งหมดในภาพที่เลือก ไม่ขยายผลจาก9ภาพไปแทนทั้ง141ภาพ','เราสามารถกลับมาตอบคำถามสามข้อพร้อมข้อจำกัดได้แล้ว',['C18','C19','C20'],['presentation/evidence/verified_selected_uq_images.csv','presentation/evidence/verified_selected_uq_events.csv','presentation/deck_v2/asset_manifest.json'],'Selected DEV case: Sri-Lanka_845821 • แผนที่ Entropy/MI ใช้สเกล 0–1 bits');
 const pp=[['Sri-Lanka_845821_gt','Ground Truth'],['Sri-Lanka_845821_error','ข้อผิดพลาด'],['Sri-Lanka_845821_predictive_entropy_bits','Entropy'],['Sri-Lanka_845821_mutual_information_bits','MI']];
 for(let i=0;i<4;i++){text(s,pp[i][1],.78+i*3,1.84,2.8,.43,22,{bold:true});await img(s,pp[i][0],.78+i*3,2.54,2.8,2.8);}
 text(s,'ขาว = Ignore   Error: เขียว = น้ำถูก / ส้ม = พลาดน้ำ / แดง = ระบุน้ำเกิน',.82,5.40,11.8,.27,14.5,{color:C.gray});
 text(s,'141 ภาพ',.84,5.84,4.7,.46,28,{bold:true,color:C.blue});text(s,'ผลรวมระดับภาพ Ensemble / UQ',.86,6.41,5.5,.40,19);
 const cap=assets.cases.find(v=>v.stem==='Sri-Lanka_845821');
 text(s,'9 ภาพที่เลือกไว้',7.10,5.84,5.4,.46,28,{bold:true,color:C.orange});
 para(s,`Top-10% error capture:\nในภาพนี้ Entropy ${(100*cap.entropy_capture).toFixed(1)}% / MI ${(100*cap.mi_capture).toFixed(1)}%`,7.12,6.34,5.4,.63,17.5);
}
// 21. Close the RQ loop before discussing project management.
{
 const s=slide('คำตอบปัจจุบันและขอบเขตข้อสรุป','03 ผลและข้อค้นพบ','RQ1samplingสองแบบยังไม่เพิ่มคะแนนรวมบนDEV RQ2พบความไวต่อeventและseedโดยเฉพาะSriLanka RQ3BaselineEnsembleให้คะแนนDEVสูงขึ้นเชิงพรรณนาและสร้างแผนที่ความไม่แน่นอนได้ แต่pixelerrordiagnosticsยังมีข้อจำกัดจากการเลือกภาพ ข้อจำกัดที่ส่งผลต่อการอ้างผลคือมีvalidationeventsเพียงสามevents ใช้VALIDเลือกcheckpoint และยังไม่มีindependentfinaltest การพลาดน้ำในบางseedเป็นข้อสังเกตที่ยังไม่ได้แยกสาเหตุเชิงทดลอง','จากข้อค้นพบเหล่านี้ ผมจะสรุปว่างานถึงขั้นไหนแล้วและยังเหลืออะไร',['C13','C14','C17','C19','C21'],['presentation/evidence/unresolved_questions_TH.md','presentation/evidence/verified_models.csv']);
 table(s,[['คำถาม','คำตอบจาก DEV ปัจจุบัน'],['RQ1  Sampling','ยังไม่เพิ่มคะแนนรวมเหนือ Baseline'],['RQ2  ความเสถียร','พบความไวต่อ event / seed โดยเฉพาะ Sri Lanka'],['RQ3  Ensemble / UQ','ได้คะแนน DEV สูงขึ้น และแผนที่ uncertainty\nแต่ยังระบุข้อผิดพลาดได้ไม่ครบ']],.78,1.86,11.83,3.18,[3.8,8.03],22);
 para(s,'ขอบเขตสำคัญ\n3 validation events และยังไม่มี Independent Final TEST',.84,5.53,11.6,1.03,25,{bold:true,color:C.orange});
}
// 22. No artificial completion percentage.
{
 const s=slide('ตอนนี้โครงการถึงขั้นไหนแล้ว','04 สถานะโครงการปัจจุบัน','ขณะนี้เสร็จขั้นพัฒนาและวิเคราะห์ผลเบื้องต้นแล้ว PipelineSARonlySmallUNetและprotocolพร้อม เปรียบเทียบสามmethodsครบ27runs มีeventseedfailureanalysis รวมถึงBaselineEnsemble141DEVimages และpixelUQselecteddiagnostics9ภาพ มีการตรวจหลักฐานcheckpointและผลการทดลองครบตามขอบเขตที่บันทึกไว้ Manuscriptและpresentationมีร่างและกำลังปรับการเรียบเรียง ส่วนindependentfinaltestและThailandquantitativeGTยังไม่พร้อม เราจึงไม่รายงานเปอร์เซ็นต์ความสำเร็จที่ไม่มีเกณฑ์','งานสำคัญถัดไปคือการยืนยันผลบนข้อมูลอิสระภายใต้กติกาที่ล็อกไว้',['C11','C18','C19','C21','C22','C24'],['presentation/evidence/verification_report_TH.md','presentation/evidence/unresolved_questions_TH.md'],'สถานะตามหลักฐานในโปรเจ็กต์ ณ 18 พฤศจิกายน 2569');
 table(s,[['ส่วนงาน','สถานะปัจจุบัน'],['Pipeline / DEV splits / protocol','ทำแล้ว'],['สามวิธี Sampling + event / seed analysis','ครบ 27 runs'],['Baseline Ensemble / image-level UQ','141 DEV images'],['Detailed pixel UQ diagnostics','9 selected images'],['Manuscript / Presentation','มีร่าง กำลังปรับการเรียบเรียง'],['Independent Final TEST / Thailand GT','ยังไม่มีผลยืนยัน / GT ยังไม่พร้อม']],.78,1.77,11.83,4.23,[7.7,4.13],20,{margin:[2,9,2,9]});
 takeaway(s,'ผ่านช่วงพัฒนาและวิเคราะห์เบื้องต้น กำลังเตรียมขั้นยืนยันผล',6.50);
}
// 23. A proposed confirmation experiment, explicitly distinguished from 27 completed runs.
{
 const s=slide('ขั้นถัดไป: ยืนยันด้วย Independent Final TEST','05 แผนดำเนินงานจนเสร็จ','หน้านี้เป็นแผนเสนอ ยังไม่ได้ทำfinalexperiment ขั้นแรกคือจัดหาlabelledeventsใหม่และตรวจoverlapกับข้อมูลเดิมทั้งeventเวลาและfootprint จากนั้นล็อกmethodsseedsstoppingrulethresholdmetricsและaggregationก่อนดูคะแนนTEST ข้อเสนอหากคงการเปรียบเทียบสามmethodsคือใช้developmentpool243ภาพฝึกfinalmodelsสามmethodsคูณสามseedsรวม9finalruns กำหนดจำนวนepochsจากDEVล่วงหน้าโดยไม่earlystopบนTEST และสร้างBaselineensembleจากสามseedsที่ฝึกชุดเดียวกัน จึงประเมินทุกวิธีบนTESTชุดเดียวตามprotocol ประวัติIndiaParaguayGhanaและBoliviaที่เคยตรวจแล้วไม่ใช่pristineconfirmationใหม่ จำนวนeventsต้องสอดคล้องกับขอบเขตการอ้างผล','สำหรับประเทศไทย การยืนยันเชิงปริมาณต้องเริ่มจากreferenceที่สอดคล้องกับงาน',['C05','C21'],['presentation/evidence/unresolved_questions_TH.md'],'แผนเสนอ • ยังไม่ได้ดำเนินการ • 9 final runs เป็นงานใหม่ แยกจาก 27 runs ที่เสร็จแล้ว');
 rows(s,[['1','หาเหตุการณ์ใหม่ที่มีแผนที่อ้างอิง\nตรวจความซ้ำด้านเหตุการณ์ เวลา และพื้นที่'],['2','ล็อกโมเดลและกติกาก่อนดูคะแนน TEST\nจำนวนรอบฝึก ค่าแบ่งน้ำ ตัวชี้วัด และวิธีรวมผล'],['3','ประเมินทุกวิธีบน TEST ชุดเดียวกัน\nรายงานผลครบ โดยไม่ปรับวิธีจากคะแนน TEST']],.83,1.83,11.7,1.30,24);
 text(s,'ข้อเสนอ final training: 3 methods × 3 seeds = 9 runs',.85,6.15,11.65,.40,22,{bold:true,color:C.orange});text(s,'ใช้ DEV 243 ภาพ และกำหนดกติกาหยุดฝึกจาก DEV ล่วงหน้า',.85,6.63,11.65,.28,17,{color:C.gray});
}
// 24. A usable reference has a definition, temporal alignment and a QC process.
{
 const s=slide('ประเทศไทยต้องมี Ground Truth ที่ประเมินได้','05 แผนดำเนินงานจนเสร็จ','พิมายปัจจุบันยังเป็นdiagnosticpilot เรายังไม่ใช้คะแนนที่เปรียบกับUNOSATตรงๆเป็นaccuracyของงานsurfacewater เพราะนิยามความครอบคลุมและเวลาอาจต่างกัน แผนคือเลือกเหตุการณ์เวลาและพื้นที่ที่เหมาะกับconfirmation จัดทำreferenceตามนิยามsurfacewaterตรวจCRSresolutiongridและvalidignoremaskพร้อมตรวจเวลาacquisition ผู้ทำreferenceควรไม่เห็นpredictionที่กำลังประเมิน ต้องมีannotationguideผู้ตรวจคุณภาพและกติกาบริเวณกำกวม พื้นที่ที่ไม่มีannotationไม่ควรถูกถือเป็นlandโดยอัตโนมัติ ถ้าจัดหาreferenceคุณภาพพอไม่ได้ ต้องปรับขอบเขตการอ้างผลไทยร่วมกับอาจารย์','นำงานที่เหลือทั้งหมดมาเรียงเป็นขั้นตอนและสิ่งส่งมอบที่ตรวจได้',['C22'],['presentation/evidence/unresolved_questions_TH.md'],'แผนเสนอ • พิมายปัจจุบันเป็น Diagnostic Pilot • ยังไม่รายงาน Thailand quantitative accuracy');
 rows(s,[['1','นิยามตรงกัน\nแผนที่อ้างอิงระบุน้ำผิวดินตามเป้าหมายของงาน'],['2','เวลาและตำแหน่งตรงกัน\nตรวจเวลาถ่ายภาพ พิกัด ความละเอียด และ masks'],['3','มีการตรวจคุณภาพ labels\nคู่มือทำ label ผู้ตรวจ และกติกาบริเวณกำกวม']],.83,1.87,11.7,1.32,24);
 takeaway(s,'สิ่งส่งมอบ: คู่ SAR / GT พร้อมที่มาข้อมูลและบันทึกคุณภาพ',6.43,C.orange);
}
// 25. Deliverables and gates, not invented calendar promises.
{
 const s=slide('แผนดำเนินงานจนส่งฉบับสุดท้าย','05 แผนดำเนินงานจนเสร็จ','เริ่มจากรับfeedbackและล็อกขอบเขตพร้อมเติมrelatedwork จากนั้นขยายpixelUQauditให้ครบ141DEVด้วยกติกาคงที่ ยังคงป้ายDEV เตรียมindependentreferenceและThailandGTแล้วfreezefinaltrainingevaluationplanก่อนคะแนนTEST ทำfinalrunsและตรวจartifacts รันevaluationครบตามprotocolรายงานรายeventmacroและUQพร้อมข้อผิดพลาดและต้นทุนinference สุดท้ายอัปเดตmanuscriptfiguresและreproducibilitypackageก่อนซ้อมนำเสนอ ยังไม่รับปากระยะเวลาเพราะขึ้นกับวันส่งข้อมูลและผู้ตรวจlabels หากจะให้confidenceintervalต้องคำนึงถึงการพึ่งพากันภายในevent ไม่ถือพิกเซลหรือseedsเป็นภูมิภาคอิสระจำนวนมาก','ปิดด้วยสิ่งที่มีแล้วและสิ่งที่จะส่งเมื่อโครงการเสร็จ',['C19','C21','C22'],['presentation/plan_v2/SLIDE_STORYBOARD_TH.md'],'แผนเสนอ • ลำดับและเกณฑ์จบ • กำหนดเวลาเมื่อทราบวันส่งและความพร้อมของ reference');
 table(s,[['ขั้น','งานที่จะทำ','สิ่งส่งมอบ / เงื่อนไขผ่าน'],['A','รับคำแนะนำและปิดขอบเขต\nเติมงานที่เกี่ยวข้อง','คำถาม วิธีทดลอง และข้อกล่าวอ้างตรงกัน'],['B','ขยายการตรวจ UQ รายพิกเซล\nให้ครบ 141 DEV ภาพ','ผลครบตามกติกาเดียวกัน\nยังรายงานเป็น DEV'],['C','เตรียมเหตุการณ์อิสระ\nและ Ground Truth ไทย','คู่ SAR / GT ผ่านตรวจคุณภาพ\nมีที่มาและตรวจการซ้ำของข้อมูล'],['D','ล็อกกติกาขั้นสุดท้าย\nฝึกและตรวจโมเดล','ไฟล์โมเดลและบันทึกการฝึกครบ\nไม่ใช้ TEST เลือกโมเดล'],['E','ประเมินและวิเคราะห์\nรายเหตุการณ์และภาพรวม','คะแนนครบ ข้อผิดพลาด และ UQ\nตามขอบเขตที่ประกาศ'],['F','เขียนรายงาน ตรวจรูป / ตัวเลข\nจัดชุดไฟล์และซ้อม','รายงาน สไลด์ และไฟล์ประกอบ\nตรงกันและตรวจย้อนกลับได้']],.75,1.75,11.88,4.97,[.80,5.30,5.78],18,{margin:[2,6,2,6]});
}
// 26. Completion means answering the questions, including negative results.
{
 const s=slide('ข้อสรุปและสิ่งที่จะส่งเมื่อจบโครงการ','05 แผนดำเนินงานจนเสร็จ','ขณะนี้มีหลักฐานเชิงพัฒนาเรื่องsamplingความไวต่อseedและBaselineEnsembleUQแล้ว ขั้นที่เหลือมุ่งยืนยันข้อค้นพบด้วยindependentlabelledeventsและreferenceที่สอดคล้องกับtarget สิ่งส่งมอบสุดท้ายคือคำตอบRQที่มีขอบเขตชัด ผลfinalevaluationและerroranalysis manuscriptpresentationและcodeconfigsplitrunmanifestที่ตรวจย้อนกลับได้ เกณฑ์จบงานคือคำถามวิจัยได้รับคำตอบตามหลักฐานและขอบเขตที่ตกลงไว้ ไม่กำหนดว่าคะแนนต้องดีขึ้นจึงถือว่าเสร็จ','ขอบคุณครับ พร้อมรับคำแนะนำเกี่ยวกับขอบเขต confirmation และแผน reference ประเทศไทย',['C13','C14','C17','C21','C22'],['presentation/plan_v2/SLIDE_STORYBOARD_TH.md']);
 text(s,'มีแล้ว',.84,1.88,2.1,.48,29,{bold:true,color:C.blue});para(s,'ผลพัฒนาเรื่อง Sampling และความไวต่อ seed\nรวมถึง Baseline Ensemble / UQ',3.30,1.88,9.15,1.00,27);
 text(s,'ทำต่อ',.84,3.63,2.1,.48,29,{bold:true,color:C.orange});para(s,'ยืนยันบนเหตุการณ์ใหม่ที่แยกจากการพัฒนา\nพร้อม Ground Truth ที่สอดคล้องกับงาน',3.30,3.63,9.15,1.00,27);
 text(s,'ส่งมอบ',.84,5.38,2.1,.48,29,{bold:true,color:C.green});para(s,'ผลยืนยันและบทวิเคราะห์ รายงาน สไลด์\nและชุดไฟล์สำหรับตรวจย้อนกลับ',3.30,5.38,9.15,1.00,27);
}

if(number!==26)throw new Error('Expected exactly 26 slides');
await fs.mkdir(path.join(D,'.build'),{recursive:true});await fs.mkdir(path.join(P,'output'),{recursive:true});
const draft=path.join(D,'.build','revised26_draft.pptx');
await pptx.writeFile({fileName:draft,compression:true});
const zip=await JSZip.loadAsync(await fs.readFile(draft));
let ct=await zip.file('[Content_Types].xml').async('string');
ct=ct.replace(/<Override\b[^>]*\bPartName="([^"]+)"[^>]*\/>/g,(entry,name)=>zip.file(name.replace(/^\//,''))?entry:'');zip.file('[Content_Types].xml',ct);
for(const spec of errors){let xml=await zip.file(spec.part).async('string'),si=0;xml=xml.replace(/<c:ser>([\s\S]*?)<\/c:ser>/g,(_,body)=>{const v=spec.sd[si++];if(!v)throw Error('Missing SD');const lit='<c:numLit><c:formatCode>0.0000</c:formatCode><c:ptCount val="'+v.length+'"/>'+v.map((n,i)=>'<c:pt idx="'+i+'"><c:v>'+n+'</c:v></c:pt>').join('')+'</c:numLit>';const err='<c:errBars><c:errDir val="y"/><c:errBarType val="both"/><c:errValType val="cust"/><c:noEndCap val="0"/><c:plus>'+lit+'</c:plus><c:minus>'+lit+'</c:minus><c:spPr><a:ln w="12700"><a:solidFill><a:srgbClr val="183047"/></a:solidFill></a:ln></c:spPr></c:errBars>';return'<c:ser>'+body.replace('<c:cat>',err+'<c:cat>')+'</c:ser>';});if(si!==spec.sd.length)throw Error('SD series mismatch');zip.file(spec.part,xml);}
const dest=path.join(P,'output',process.argv[2]||'FloodAI_Research_Revised26_TH_Final.pptx');
await fs.writeFile(dest,await zip.generateAsync({type:'nodebuffer',compression:'DEFLATE'}));
await fs.writeFile(path.join(D,'manifest.json'),JSON.stringify(manifest,null,2)+'\n');
const guide='# บทพูดและคำเชื่อมรายหน้า\n\nฉบับ 26 หน้า จัดตามโครงใหม่ ข้อมูลหลักเป็น DEV และหน้าแผนเป็นข้อเสนอที่ยังไม่ได้ดำเนินการ\n\n'+manifest.slides.map(v=>'## '+String(v.number).padStart(2,'0')+' '+v.title+'\n\n'+v.narration.replace(/([ก-๙])([A-Za-z0-9])/g,'$1 $2').replace(/([A-Za-z0-9])([ก-๙])/g,'$1 $2')+'\n\n**เชื่อมไปหน้าถัดไป:** '+v.transition+'\n\n**ขอบเขต:** '+v.scope+'\n\n**Sources:**\n'+v.sources.map(p=>'- '+p).join('\n')).join('\n\n');
await fs.writeFile(path.join(P,'plan_v2/SPEAKER_GUIDE_26_TH.md'),guide+'\n');
console.log(JSON.stringify({file:dest,slides:number,charts:manifest.charts.length,tables:manifest.tables.length,diagrams:manifest.diagrams.length},null,2));
