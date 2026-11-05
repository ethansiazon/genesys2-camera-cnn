"""Render a frozen, actual framebuffer-write snapshot (RGB565 diagnostic copy)."""
import argparse,json
from pathlib import Path
import numpy as np
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]
def main():
 p=argparse.ArgumentParser();p.add_argument('file',nargs='?',type=Path);a=p.parse_args()
 if a.file is None:
  status=json.loads((ROOT/'reports/LAST_SNAPSHOT.json').read_text(encoding='utf-8-sig'))
  if not status['complete']:raise RuntimeError('Incomplete UART transfer')
  a.file=Path(status['file'])
 packets=[[int(w,16) for w in l.split()] for l in a.file.read_text().splitlines() if l.strip()]
 if len(packets)!=5487:raise RuntimeError('Wrong packet count')
 pixels=[]
 for i,w in enumerate(packets):
  if len(w)!=8 or w[0]!=(0xD16A0000|i):raise RuntimeError(f'Bad packet {i}')
  if i<5486:
   for word in w[1:]:pixels.extend([word&65535,word>>16])
 meta=packets[-1]
 if meta[5:]!=[76800,16,0x534e4150]:raise RuntimeError('Bad metadata')
 values=np.array(pixels[:76800],dtype=np.uint16).reshape(240,320)
 rgb=np.stack([((values>>11).astype(np.uint32)*255+15)//31,
               (((values>>5)&63).astype(np.uint32)*255+31)//63,
               ((values&31).astype(np.uint32)*255+15)//31],axis=-1).astype(np.uint8)
 image=Image.fromarray(rgb);image.save(a.file.with_suffix('.png'))
 image.resize((960,720),Image.Resampling.NEAREST).save(a.file.with_suffix('.preview.png'))
 result=dict(source=str(a.file),pixels_recorded=meta[1],address_sequence_errors=meta[2],
             camera_frame=meta[3],finish_reason=meta[4],
             complete_sequential_frame=(meta[1]==76800 and meta[2]==0 and meta[4]==1),
             image=str(a.file.with_suffix('.preview.png')),
             scope='RGB565 copy of actual framebuffer write inputs before storage/display; '
                   'not a readback of BRAM contents or a screenshot of HDMI.')
 a.file.with_suffix('.analysis.json').write_text(json.dumps(result,indent=2))
 print(json.dumps(result,indent=2))
if __name__=='__main__':main()
