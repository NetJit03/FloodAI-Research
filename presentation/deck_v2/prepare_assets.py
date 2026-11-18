"""Render measured arrays as scientific image panels, without model fitting."""
from pathlib import Path
import csv,json,hashlib
import numpy as np
import rasterio
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap

ROOT=Path(__file__).resolve().parents[2]
D=Path(__file__).resolve().parent
A=D/'assets';A.mkdir(exist_ok=True)
rows=list(csv.DictReader((ROOT/'presentation/evidence/verified_rasters.csv').open()))
captures=list(csv.DictReader((ROOT/'presentation/evidence/verified_selected_uq_images.csv').open()))
manifest=[]
WATER='#2389BE';LAND='#E1E6EB';IGNORE='#FFFFFF'
ERROR=['#E1E6EB','#2E8B74','#D98C35','#CB5360']
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(name,arr,cmap,vmin,vmax,source,colorbar=False):
 p=A/(name+'.png')
 if colorbar:
  fig,ax=plt.subplots(figsize=(4.5,4.1),dpi=180)
  im=ax.imshow(arr,cmap=cmap,vmin=vmin,vmax=vmax,interpolation='nearest')
  ax.set_axis_off();fig.colorbar(im,ax=ax,fraction=.045,pad=.025,ticks=[0,.5,1])
  fig.subplots_adjust(left=.01,bottom=.01,top=.99,right=.92)
  fig.savefig(p,facecolor='white');plt.close(fig)
 else:plt.imsave(p,arr,cmap=cmap,vmin=vmin,vmax=vmax)
 manifest.append({'file':str(p.relative_to(ROOT)),'source':str(source.relative_to(ROOT)),
                  'source_sha256':sha(source),'sha256':sha(p),'type':'scientific rendering of measured arrays'})
def case(stem,fold):
 p=ROOT/'results/event_level_v2/m80a_dev_ensemble_uq/previews'/fold/(stem+'_S1Hand_ensemble.npz')
 with np.load(p,allow_pickle=False) as z:d={k:z[k] for k in z.files}
 r=next(r for r in rows if r['image']==stem+'_S1Hand.tif')
 sar=ROOT/r['sar_path'];gt=ROOT/r['label_path']
 with rasterio.open(sar) as src:x=src.read()
 v=d['valid'];y=d['gt_water'];pred=d['p_water']>=.5
 for key,arr in [('gt',y),('pred',pred)]:
  masked=np.where(v,arr.astype(int),2)
  save(stem+'_'+key,masked,ListedColormap([LAND,WATER,IGNORE]),0,2,p)
 err=np.zeros(y.shape,dtype=np.uint8)
 err[v&y&pred]=1;err[v&y&~pred]=2;err[v&~y&pred]=3
 save(stem+'_error',np.where(v,err,4),ListedColormap(ERROR+[IGNORE]),0,4,p)
 if stem=='Sri-Lanka_713926':
  for i,band in enumerate(['vv','vh']):
   save(stem+'_'+band,np.clip((x[i]-[-35,-40][i])/40,0,1),'gray',0,1,sar)
  save(stem+'_prob',np.where(v,d['p_water'],np.nan),'viridis',0,1,p,True)
 if stem=='Sri-Lanka_845821':
  for key in ['predictive_entropy_bits','mutual_information_bits']:
   save(stem+'_'+key,np.where(v,d[key],np.nan),'magma',0,1,p,True)
 cap=next(r for r in captures if r['image']==stem+'_S1Hand.tif')
 return {'stem':stem,'valid_pixels':int(v.sum()),'tp':int((v&y&pred).sum()),
         'fp':int((v&~y&pred).sum()),'fn':int((v&y&~pred).sum()),
         'entropy_capture':float(cap['entropy_capture']),'mi_capture':float(cap['mi_capture'])}
summary=[case('Spain_1167260','dev_fold_03_spain'),case('Sri-Lanka_713926','dev_fold_02_sri_lanka'),
         case('Sri-Lanka_845821','dev_fold_02_sri_lanka')]
p=ROOT/'results/event_level_v2/m74b_high_water_diagnostics/m74b_selected_probs.npz'
r=next(r for r in rows if r['image']=='Sri-Lanka_534068_S1Hand.tif')
gt=ROOT/r['label_path']
with rasterio.open(gt) as src:y=src.read(1)
save('failure_gt',np.where(y==-1,2,y),ListedColormap([LAND,WATER,IGNORE]),0,2,gt)
with np.load(p,allow_pickle=False) as z:
 for seed in [42,123,777]:
  pred=z[f'Sri-Lanka_534068_seed{seed}']>=.5
  save(f'failure_seed{seed}',np.where(y==-1,2,pred.astype(int)),ListedColormap([LAND,WATER,IGNORE]),0,2,p)
(D/'asset_manifest.json').write_text(json.dumps({'panels':manifest,'cases':summary},ensure_ascii=False,indent=2)+'\n')
print('Rendered',len(manifest),'scientific panels from stored arrays. No inference or training.')
