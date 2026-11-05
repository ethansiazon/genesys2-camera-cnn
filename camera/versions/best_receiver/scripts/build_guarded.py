"""One bounded compiler, two threads, 1.5 GiB RAM guard, no board programming."""
import ctypes,subprocess,time,json,os,sys,hashlib,tempfile,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
VIVADO=Path('C:/AMDDesignTools/2026.1/Vivado/bin/vivado.bat')
class Memory(ctypes.Structure):
    _fields_=[('length',ctypes.c_ulong),('load',ctypes.c_ulong)]+[(n,ctypes.c_ulonglong) for n in ['total','available','page_total','page_available','virtual_total','virtual_available','extended']]
def free_gib():
    m=Memory();m.length=ctypes.sizeof(m)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m)):raise ctypes.WinError()
    return m.available/2**30
def main():
    reports=ROOT/'reports';reports.mkdir(exist_ok=True)
    lock=ROOT/'BUILD_RUNNING.lock'
    try:fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY)
    except FileExistsError:raise RuntimeError('Build lock exists. Inspect the prior process before removing it.')
    os.write(fd,str(os.getpid()).encode());os.close(fd)
    run=None;result={'status':'starting','free_gib':free_gib()}
    try:
        if result['free_gib']<2.5:raise RuntimeError('Less than 2.5 GiB free; save work/close unused applications before building.')
        out=Path(tempfile.mkdtemp(prefix='g2cam_',dir=tempfile.gettempdir()))
        result.update(build_directory=str(out),rtl_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((ROOT/'rtl').glob('*.v'))})
        (reports/'BUILD_STATUS.json').write_text(json.dumps(result,indent=2))
        args=[str(VIVADO),'-mode','batch','-source',str(ROOT/'scripts/build.tcl'),'-tclargs',str(out)]
        # cmd.exe is needed for the vendor .bat; list2cmdline preserves paths.
        command=subprocess.list2cmdline(args)
        with (reports/'build_terminal.txt').open('w') as log:
            run=subprocess.Popen([os.environ.get('COMSPEC','cmd.exe'),'/d','/s','/c',command],cwd=out,stdout=log,stderr=subprocess.STDOUT)
            result.update(status='running',pid=run.pid)
            (reports/'BUILD_STATUS.json').write_text(json.dumps(result,indent=2))
            start=time.monotonic();last=-100;low=0
            while run.poll() is None:
                free=free_gib();low=low+1 if free<1.5 else 0
                elapsed=time.monotonic()-start
                if elapsed-last>=30:
                    print(f'Camera build running: {elapsed/60:.1f} min | free RAM {free:.2f} GiB',flush=True);last=elapsed
                if low>=3 or elapsed>1500:
                    subprocess.run(['taskkill','/PID',str(run.pid),'/T','/F'],capture_output=True)
                    run.wait(timeout=30)
                    raise RuntimeError('Memory guard stopped build' if low>=3 else 'Bounded 25-minute build time exceeded')
                time.sleep(5)
        result['returncode']=run.returncode
        for name in ['timing.rpt','utilization.rpt','drc.rpt','cdc.rpt','route_status.rpt','clock_interaction.rpt','timing_values.json']:
            if (out/name).exists():shutil.copy2(out/name,reports/name)
        if run.returncode!=0 or not (out/'camera_hdmi.bit').exists():raise RuntimeError('Compiler did not complete a timing-clean bitstream; inspect reports/build_terminal.txt')
        shutil.copy2(out/'camera_hdmi.bit',ROOT/'camera_hdmi.bit')
        result.update(status='complete',bitstream=str(ROOT/'camera_hdmi.bit'),bitstream_sha256=hashlib.sha256((ROOT/'camera_hdmi.bit').read_bytes()).hexdigest(),
          timing=json.loads((out/'timing_values.json').read_text()),physical_camera_tested=False)
        print('BUILD PASSED: '+str(ROOT/'camera_hdmi.bit'),flush=True)
    except Exception as exc:
        result.update(status='needs_attention',error=str(exc));raise
    finally:
        (ROOT/'reports/BUILD_STATUS.json').write_text(json.dumps(result,indent=2))
        lock.unlink(missing_ok=True)
if __name__=='__main__':main()
