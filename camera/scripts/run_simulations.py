"""Run archived camera test definitions in a NEW output folder; no board access."""
import argparse,shutil
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--variant',choices=['best_receiver','last_exposure_test','raw_recorder'],default='best_receiver');p.add_argument('--out',required=True);p.add_argument('--iverilog',default=shutil.which('iverilog'));p.add_argument('--vvp',default=shutil.which('vvp'));a=p.parse_args()
if not a.iverilog or not a.vvp:raise SystemExit('Install Icarus Verilog or supply --iverilog and --vvp paths')
root=Path(__file__).resolve().parents[1]/'versions'/a.variant;out=Path(a.out).resolve()
if out.exists():raise SystemExit('Choose a new simulation output folder')
out.mkdir(parents=True)
src=(root/'scripts/run_tests.py').read_text(encoding='utf-8-sig')
old="WORK=ROOT/'reports'/'simulation';WORK.mkdir(parents=True,exist_ok=True)"
assert old in src;src=src.replace(old,f'WORK=Path({str(out)!r})')
old="IVERILOG=Path('C:/iverilog/bin/iverilog.exe'); VVP=IVERILOG.with_name('vvp.exe')"
assert old in src;src=src.replace(old,f'IVERILOG=Path({a.iverilog!r}); VVP=Path({a.vvp!r})')
src=src.replace("(ROOT/'reports'/'FUNCTIONAL_TESTS.json')",f"Path({str(out/'FUNCTIONAL_TESTS.json')!r})")
exec(compile(src,str(root/'scripts/run_tests.py'),'exec'),{'__file__':str(root/'scripts/run_tests.py'),'__name__':'__main__'})
