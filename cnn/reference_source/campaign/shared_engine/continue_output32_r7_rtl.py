"""Version the already-reviewed compact RTL adapter for the changed256MAC core.
Preserve R6, original harness templates, all generated RTL and numerical gates.
"""
from pathlib import Path
import hashlib,json,subprocess,sys
HERE=Path(__file__).resolve().parent

def main():
    driver=HERE/'continue_output32_r7_rtl_driver.py'
    if driver.exists():raise RuntimeError('Existing R7 driver preserved')
    source=HERE/'continue_weight_reuse_r6_rtl.py';text=source.read_text()
    for old,new in [('g2_roi_epoch11_reuse_r6','g2_roi_epoch11_output32_r7'),('compact_reuse_r6','compact_output32_r7'),('WEIGHT_REUSE_R6','OUTPUT32_R7'),('R6_RTL','R7_RTL'),('weight_reuse_r6','output32_r7'),('R6','R7')]:text=text.replace(old,new)
    driver.write_text(text)
    (HERE/'OUTPUT32_R7_RTL_DRIVER_PROVENANCE.json').write_text(json.dumps({'source_adapter':str(source),'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'driver':str(driver),'driver_sha256':hashlib.sha256(driver.read_bytes()).hexdigest(),'adaptation':'Only versioned build/artifact/gate names. Same fullgeneratedRTL copy and exact rawoutput tests; CNNRTL unedited. OriginalROI11compactRAMunitmodels/stalls preserved.'},indent=2))
    subprocess.run([sys.executable,'-u',str(driver)],cwd=HERE.parent,check=True)

if __name__=='__main__':main()
