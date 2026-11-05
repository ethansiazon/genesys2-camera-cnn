"""Optional guarded build; does not connect to hardware. pip install psutil."""
import argparse, pathlib, subprocess, time, psutil, os
p=argparse.ArgumentParser();p.add_argument('--vivado',required=True,help='Path to vivado.bat or vivado executable');p.add_argument('--variant',choices=['best_receiver','last_exposure_test','raw_recorder'],default='best_receiver');p.add_argument('--out',required=True);a=p.parse_args()
root=pathlib.Path(__file__).resolve().parents[1];out=pathlib.Path(a.out).resolve()
if out.exists():raise SystemExit('Use a NEW output directory; existing output preserved')
if psutil.virtual_memory().available<3*2**30:raise SystemExit('Need at least 3 GiB free to start')
out.mkdir(parents=True)
with (out/'guarded_build.log').open('w') as log:
    args=[a.vivado,'-mode','batch','-source',str(root/'versions'/a.variant/'scripts/build.tcl'),'-tclargs',str(out)]
    if os.name=='nt' and pathlib.Path(a.vivado).suffix.lower() in {'.bat','.cmd'}:
        args=[os.environ.get('COMSPEC','cmd.exe'),'/d','/s','/c',subprocess.list2cmdline(args)]
    proc=subprocess.Popen(args,cwd=out,stdout=log,stderr=subprocess.STDOUT)
    stopped=False
    try:
        while proc.poll() is None:
            if psutil.virtual_memory().available<1.5*2**30:
                stopped=True;raise RuntimeError('Stopped below 1.5 GiB free RAM; partial files retained')
            time.sleep(3)
    finally:
        if proc.poll() is None:
            try:
                owned=psutil.Process(proc.pid);children=owned.children(recursive=True)
                for child in reversed(children):
                    try:child.terminate()
                    except psutil.NoSuchProcess:pass
                owned.terminate();_,alive=psutil.wait_procs(children+[owned],timeout=5)
                for child in alive:
                    try:child.kill()
                    except psutil.NoSuchProcess:pass
            except psutil.NoSuchProcess:pass
    if proc.returncode:raise SystemExit(proc.returncode)
print('Build finished; inspect timing and bitstream in',out)
