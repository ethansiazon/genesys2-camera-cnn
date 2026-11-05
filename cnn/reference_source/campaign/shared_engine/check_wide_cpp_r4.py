"""Small single-process host C++ full-CNN numeric check, NOT FPGA compilation.
May coexist with GPU training; own2GiB memory/time guards, no status overwrite.
"""
import sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent;sys.path.insert(0,str(ROOT))
import ctypes,json,os,subprocess,time,traceback
import numpy as np
from state import Memory,save
BUILD=Path.home()/'fpga_builds/g2_shared_engine_20261017_wide_r4_roi256_live'
REPORT=BUILD/'HOST_NUMERICAL_CHECK.json'

def free():
    m=Memory();m.length=ctypes.sizeof(m);ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m));return m.available/2**30

def run(stage,command,limit):
    path=BUILD/(stage+'.log')
    if path.exists():raise RuntimeError('Existing host stage preserved')
    if free()<2.5:raise RuntimeError('Insufficient RAM for light host check; training untouched')
    env=dict(os.environ);env['PATH']=r'C:\msys64\ucrt64\bin;'+env['PATH']
    with path.open('w',encoding='utf-8') as log:
        child=subprocess.Popen(command,cwd=BUILD,env=env,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NEW_PROCESS_GROUP);save(BUILD/'host_active.json',{'pid':child.pid,'stage':stage});start=time.monotonic()
        try:
            while child.poll() is None:
                time.sleep(2)
                if free()<2:raise RuntimeError('Stopped owned host child below2GiB reserve; GPU training untouched')
                if time.monotonic()-start>limit:raise RuntimeError('Bounded light host stage exceeded limit')
            if child.returncode:raise RuntimeError(stage+' failed; inspect saved log')
        except BaseException:subprocess.run(['taskkill','/PID',str(child.pid),'/T','/F'],capture_output=True);raise

def compare():
    program=json.loads((BUILD/'program.json').read_text());expected=np.load(BUILD/'expected.npy');values=np.fromfile(BUILD/'engine_results.bin',np.int32);length=sum(((h['shape_bchw'][1]+7)//8)*h['shape_bchw'][2]*h['shape_bchw'][3]*8 for h in program['heads'])
    if len(values)!=len(expected)*length:raise RuntimeError('Wide full-network output length mismatch')
    rows=[]
    for row in values.reshape(-1,length):
        offset=0;heads=[]
        for head in program['heads']:
            _,c,h,w=head['shape_bchw'];n=((c+7)//8)*h*w*8;code=row[offset:offset+n].reshape((c+7)//8,h,w,8).transpose(1,2,0,3).reshape(h,w,((c+7)//8)*8)[:,:,:c];heads.append(code.reshape(-1).astype(np.float64)/16384);offset+=n
        rows.append(np.concatenate(heads))
    actual=np.stack(rows);error=np.abs(actual-expected);return {'passed':bool((error==0).all()),'max_abs_error':float(error.max()),'different_values':int((error!=0).sum()),'compared_values':error.size,'vectors':len(expected)}

def main():
    if REPORT.exists():raise RuntimeError('Existing host numeric evidence preserved')
    result={'status':'running','passed':False,'scope':'Full55instruction trained-seed CNN, A24F14/W16,256x192. Actual Vitis ap_int headers in native host C++, exact independent FXfloat64 reference. No HLS/RTL/resource/timing or final ROI-trained accuracy claim.'};save(REPORT,result)
    try:
        run('host_compile',[r'C:\msys64\ucrt64\bin\g++.exe','-std=c++14','-O2',r'-IC:\AMDDesignTools\2026.1\Vitis\include','cnn_engine.cpp','test_engine.cpp','-o','test_engine.exe'],300)
        run('complete_cpp',[str(BUILD/'test_engine.exe')],900);numeric=compare();result.update(status='complete' if numeric['passed'] else 'needs_attention',passed=numeric['passed'],numerical=numeric);save(REPORT,result);print(json.dumps(result,indent=2))
        if not numeric['passed']:raise RuntimeError('Wide complete CNN numeric mismatch; inspect, no hardware compilation')
    except BaseException as exc:result.update(status='needs_attention',error=str(exc),traceback=traceback.format_exc());save(REPORT,result);raise

if __name__=='__main__':main()
