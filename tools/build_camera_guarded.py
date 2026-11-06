"""Build a frozen working-camera snapshot; never access/program the board."""
import argparse,hashlib,json,os,shutil,subprocess,time
from pathlib import Path
import psutil

p=argparse.ArgumentParser()
p.add_argument('--vivado',required=True)
p.add_argument('--out',required=True)
p.add_argument('--min-free-gib',type=float,default=1.5)
p.add_argument('--timeout-min',type=float,default=45)
p.add_argument('--format',choices=('yuyv','rgb565'),default='yuyv')
readout_profiles = ('baseline', 'reference2x', 'reference2x-fast')
p.add_argument('--readout',choices=readout_profiles,default='baseline')
a=p.parse_args()
reference_readout = readout_profiles.index(a.readout)
root=Path(__file__).resolve().parents[1]
source=root/'camera/working'
out=Path(a.out).resolve()
if out.exists():raise SystemExit('Use a NEW output directory')
if psutil.virtual_memory().available<3*2**30:raise SystemExit('Need at least 3 GiB free to start; sources are saved')
for proc in psutil.process_iter(['pid','name','cmdline']):
    try:
        if (proc.info['name'] or '').lower() in ('vivado.exe','vitis_hls.exe'):
            args=' '.join(proc.info['cmdline'] or []).lower()
            if '-mode batch' in args or (proc.info['name'] or '').lower()=='vitis_hls.exe':
                raise SystemExit('Another batch compiler is running; not launching a duplicate')
    except (psutil.NoSuchProcess,psutil.AccessDenied):pass
out.mkdir(parents=True)
snapshot=out/'source'
for folder in ('rtl','constraints'):
    shutil.copytree(source/folder,snapshot/folder)
(snapshot/'scripts').mkdir()
text=(source/'scripts/build.tcl').read_text()
text=text.replace('set_param general.maxThreads 2','set_param general.maxThreads 1')
(snapshot/'scripts/build.tcl').write_text(text)
hashes={str(f.relative_to(snapshot)).replace('\\','/'):hashlib.sha256(f.read_bytes()).hexdigest() for f in snapshot.rglob('*') if f.is_file()}
(out/'SOURCE_SHA256.json').write_text(json.dumps(hashes,indent=2)+'\n')
status={'state':'starting','output':str(out),'source_snapshot':str(snapshot),'memory_guard_gib':a.min_free_gib,'threads':1,'board_programming':False,'camera_format':a.format,'rgb565_generic':int(a.format=='rgb565'),'readout_profile':a.readout,'reference_readout_generic':reference_readout}
def save():
    status['updated_at_local']=time.strftime('%Y-%m-%d %H:%M:%S')
    temp=out/'STATUS.tmp';temp.write_text(json.dumps(status,indent=2)+'\n');temp.replace(out/'STATUS.json')
def stop_tree(proc):
    try:
        parent=psutil.Process(proc.pid);owned=parent.children(recursive=True)+[parent]
        for item in reversed(owned):
            try:item.terminate()
            except psutil.NoSuchProcess:pass
        _,alive=psutil.wait_procs(owned,timeout=5)
        for item in alive:
            try:item.kill()
            except psutil.NoSuchProcess:pass
    except psutil.NoSuchProcess:pass
save()
args=[a.vivado,'-mode','batch','-notrace','-log',str(out/'vivado.log'),'-journal',str(out/'vivado.jou'),'-source',str(snapshot/'scripts/build.tcl'),'-tclargs',str(out),str(int(a.format=='rgb565')),str(reference_readout)]
if os.name=='nt' and Path(a.vivado).suffix.lower() in ('.bat','.cmd'):
    args=[os.environ.get('COMSPEC','cmd.exe'),'/d','/s','/c',subprocess.list2cmdline(args)]
started=time.monotonic();last_print=0
with (out/'build_terminal.txt').open('w') as log:
    proc=subprocess.Popen(args,cwd=out,stdout=log,stderr=subprocess.STDOUT)
    status.update(state='running',launcher_pid=proc.pid);save()
    try:
        while proc.poll() is None:
            free=psutil.virtual_memory().available/2**30
            elapsed=time.monotonic()-started
            if free<a.min_free_gib:raise RuntimeError(f'Memory guard: {free:.2f} GiB available; partial results preserved')
            if elapsed>a.timeout_min*60:raise RuntimeError('Bounded build time limit reached; partial results preserved')
            if elapsed-last_print>=30:
                status.update(elapsed_seconds=round(elapsed),available_ram_gib=round(free,2));save()
                print(f'Camera diagnostic build running: {elapsed/60:.1f} min, {free:.2f} GiB free RAM',flush=True)
                last_print=elapsed
            time.sleep(2)
        if proc.returncode:raise RuntimeError(f'Vivado exited with code {proc.returncode}')
        timing=json.loads((out/'timing_values.json').read_text())
        assert timing['setup_wns_ns']>=0 and timing['hold_whs_ns']>=0,'Timing failed'
        bit=out/'camera_hdmi.bit'
        if not bit.exists():raise RuntimeError('Missing bitstream')
        status.update(state='complete',elapsed_seconds=round(time.monotonic()-started),timing=timing,bitstream_sha256=hashlib.sha256(bit.read_bytes()).hexdigest());save()
        print(json.dumps(status,indent=2),flush=True)
    except BaseException as exc:
        if proc.poll() is None:stop_tree(proc)
        status.update(state='stopped',reason=str(exc),elapsed_seconds=round(time.monotonic()-started));save()
        raise
