import ctypes,json,msvcrt,os,time,uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parent
PROJECT=ROOT.parent
START=time.time()
def save(path,data):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    # Windows readers/antivirus may briefly omit FILE_SHARE_DELETE. Keep writes
    # atomic, use a unique own temporary file, and tolerate only short sharing
    # conflicts. Never mask malformed data or a persistent permission problem.
    tmp=path.with_name(path.name+'.'+str(os.getpid())+'.'+uuid.uuid4().hex+'.tmp')
    tmp.write_text(json.dumps(data,indent=2,allow_nan=False),encoding='utf-8')
    for attempt in range(41):
        try:
            os.replace(tmp,path);return
        except PermissionError as exc:
            if getattr(exc,'winerror',None) not in (5,32,33) or attempt==40:raise
            time.sleep(min(.01*(attempt+1),.1))
def status(phase,**kw):
    record={'phase':phase,'pid':os.getpid(),'updated_local':time.strftime('%Y-%m-%d %H:%M:%S'),'elapsed_seconds':round(time.time()-START,1),**kw}
    save(ROOT/'status.json',record)
    text=time.strftime('%H:%M:%S')+' | '+phase+' | '+json.dumps(kw)
    print(text,flush=True)
    with (ROOT/'progress.log').open('a',encoding='utf-8') as f:f.write(text+'\n')
class Memory(ctypes.Structure):
    _fields_=[('length',ctypes.c_ulong),('load',ctypes.c_ulong),('total',ctypes.c_ulonglong),('available',ctypes.c_ulonglong),('page',ctypes.c_ulonglong),('available_page',ctypes.c_ulonglong),('virtual',ctypes.c_ulonglong),('available_virtual',ctypes.c_ulonglong),('extended',ctypes.c_ulonglong)]
def guard():
    m=Memory();m.length=ctypes.sizeof(m);ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
    if m.available<1.5*2**30:
        status('Waiting for laptop memory; recovery preserved',free_gib=m.available/2**30)
        end=time.time()+600
        while time.time()<end:
            time.sleep(10);ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
            if m.available>2*2**30:return
        raise RuntimeError('Available memory remained below safety reserve')
def lock():
    handle=(PROJECT/'genesys2_context_candidate/overnight.lock').open('a+b');handle.seek(0)
    msvcrt.locking(handle.fileno(),msvcrt.LK_NBLCK,1);return handle
