"""Diagnostic comparison for fixed OV5640 internal colour bars ONLY."""
import argparse,json,collections
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
def load(path):
 packets=[[int(w,16) for w in l.split()] for l in path.read_text().splitlines() if l.strip()]
 if len(packets)!=5487:raise RuntimeError('Incomplete frame transfer')
 meta=packets[-1]
 if meta[1]!=76800 or meta[2]!=0 or meta[4]!=1:raise RuntimeError('Frame count/address metadata failed')
 values=[]
 for p in packets[:-1]:
  for w in p[1:]:values.extend([w&65535,w>>16])
 return np.array(values[:76800],dtype=np.uint16).reshape(240,320)
def main():
 p=argparse.ArgumentParser();p.add_argument('snapshot',type=Path);args=p.parse_args()
 baseline=ROOT.parent/'frame_snapshot/reports'
 inputs=[baseline/'snapshot_20261019_234052.txt',baseline/'snapshot_20261019_234817.txt']
 combined=np.concatenate([load(f) for f in inputs])
 ref=np.array([collections.Counter(combined[:,x]).most_common(1)[0][0] for x in range(320)])
 a=load(args.snapshot);rows=[]
 for y in range(240):
  xs=np.where(a[y]!=ref)[0]
  if len(xs):rows.append(dict(row=y,changed_pixels=len(xs),first_x=int(xs[0]),last_x=int(xs[-1])))
 result=dict(source=str(args.snapshot),reference_files=[str(f) for f in inputs],
             rows_with_32_or_more_changed_pixels=sum(r['changed_pixels']>=32 for r in rows),
             total_changed_pixels=int(np.sum(a!=ref)),rows=rows,
             scope='Synthetic static colour-bar comparison only, assumes unchanged camera mode. '
                   'Minor edge changes may be normal. Not a general live-image quality metric.')
 args.snapshot.with_suffix('.bar_comparison.json').write_text(json.dumps(result,indent=2))
 print(json.dumps(result,indent=2))
if __name__=='__main__':main()
