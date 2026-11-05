"""Inspect actual YUYV bytes; preserve all8bits before RGB conversion."""
import argparse,json
from pathlib import Path
import numpy as np
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]
def decode(y,u,v,full=False):
 y=y.astype(np.int32);u=u.astype(np.int32)-128;v=v.astype(np.int32)-128
 if full:
  t=256*y;r=t+359*v;g=t-183*v-88*u;b=t+454*u
 else:
  t=298*(y-16);r=t+409*v;g=t-208*v-100*u;b=t+516*u
 return np.clip((np.stack([r,g,b],axis=-1)+128)>>8,0,255).astype(np.uint8)
def main():
 p=argparse.ArgumentParser();p.add_argument('file',nargs='?',type=Path);a=p.parse_args()
 if a.file is None:
  status=json.loads((ROOT/'reports/LAST_RAW_YUV.json').read_text(encoding='utf-8-sig'))
  if not status['complete']:raise RuntimeError('Incomplete transfer')
  a.file=Path(status['file'])
 packets=[[int(w,16) for w in l.split()] for l in a.file.read_text().splitlines() if l.strip()]
 if len(packets)!=5487:raise RuntimeError('Incomplete packet count')
 values=[]
 for i,w in enumerate(packets):
  if len(w)!=8 or w[0]!=(0xd16c0000|i):raise RuntimeError(f'Invalid packet{i}')
  if i<5486:
   for z in w[1:]:values.extend([z&65535,z>>16])
 meta=packets[-1]
 if meta[1]!=76800 or meta[2]!=0 or meta[4]!=1 or meta[5:]!=[76800,16,0x59555630]:raise RuntimeError('Incomplete or misaligned raw frame')
 words=np.array(values[:76800],dtype=np.uint16)
 raw=np.column_stack([(words>>8).astype(np.uint8),(words&255).astype(np.uint8)]).ravel()
 a.file.with_suffix('.yuyv.bin').write_bytes(raw.tobytes())
 y=(words>>8).astype(np.uint8).reshape(240,320)
 u=np.repeat((words[::2]&255).astype(np.uint8),2).reshape(240,320)
 v=np.repeat((words[1::2]&255).astype(np.uint8),2).reshape(240,320)
 outputs={}
 for name,img in [('limited',decode(y,u,v)),('full',decode(y,u,v,True)),('uv_swapped',decode(y,v,u))]:
  out=a.file.with_suffix('.'+name+'.png');Image.fromarray(img).resize((960,720),Image.Resampling.NEAREST).save(out);outputs[name]=str(out)
 bits=((raw[:,None]>>np.arange(8))&1).astype(np.uint8)
 equal=[]
 for i in range(8):
  for j in range(i+1,8):equal.append(dict(bits=[i,j],equal_fraction=float(np.mean(bits[:,i]==bits[:,j]))))
 equal.sort(key=lambda z:z['equal_fraction'],reverse=True)
 result=dict(source=str(a.file),pixels=76800,camera_frame=meta[3],images=outputs,
  bit_one_fractions=[float(z) for z in bits.mean(axis=0)],bit_pair_equal_fractions=equal,
  percentiles={name:[float(z) for z in np.percentile(ch,[0,1,10,50,90,99,100])] for name,ch in [('Y',y),('Cb',u),('Cr',v)]},
  scope='Raw receiver bytes; alternate conversions are diagnostic views only. Bit correlation alone does not prove bad wiring.')
 a.file.with_suffix('.analysis.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
if __name__=='__main__':main()
