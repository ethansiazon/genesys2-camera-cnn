"""Run supplied functional fixtures against camera/working without board access."""
import argparse, shutil
from pathlib import Path
p=argparse.ArgumentParser()
p.add_argument('--out',required=True)
p.add_argument('--iverilog',default=shutil.which('iverilog'))
p.add_argument('--vvp',default=shutil.which('vvp'))
p.add_argument('--only',nargs='+',help='Run selected named fixtures')
a=p.parse_args()
if not a.iverilog or not a.vvp:raise SystemExit('Icarus Verilog and vvp are required')
root=Path(__file__).resolve().parents[1]/'camera'/'working'
out=Path(a.out).resolve()
if out.exists():raise SystemExit('Choose a NEW output directory')
out.mkdir(parents=True)
src=(root/'scripts/run_tests.py').read_text(encoding='utf-8-sig')
if a.only:
    selected=repr(a.only)
    src=src.replace('results=[]',f"assert set({selected}) <= set(tests), 'Unknown fixture'\ntests={{k:v for k,v in tests.items() if k in {selected}}}\nresults=[]")
old="WORK=ROOT/'reports'/'simulation';WORK.mkdir(parents=True,exist_ok=True)"
assert old in src
src=src.replace(old,f'WORK=Path({str(out)!r})')
old="IVERILOG=Path('C:/iverilog/bin/iverilog.exe'); VVP=IVERILOG.with_name('vvp.exe')"
assert old in src
src=src.replace(old,f'IVERILOG=Path({a.iverilog!r}); VVP=Path({a.vvp!r})')
src=src.replace("(ROOT/'reports'/'FUNCTIONAL_TESTS.json')",f"Path({str(out/'FUNCTIONAL_TESTS.json')!r})")
exec(compile(src,str(root/'scripts/run_tests.py'),'exec'),{'__file__':str(root/'scripts/run_tests.py'),'__name__':'__main__'})
