"""Bounded functional simulations. No board access or changes to originals."""
from pathlib import Path
import subprocess, json, hashlib, time
ROOT=Path(__file__).resolve().parents[1]
WORK=ROOT/'reports'/'simulation';WORK.mkdir(parents=True,exist_ok=True)
IVERILOG=Path('C:/iverilog/bin/iverilog.exe'); VVP=IVERILOG.with_name('vvp.exe')
rtl=ROOT/'rtl';sim=ROOT/'sim'
tests={
 'tb_yuv_capture_qualified':['cam_capture','ycbcr2rgb','frame_buffer','dvp_clean_sampler'],
 'tb_banked_frame_memory':['banked_frame_memory'],
 'tb_frame_snapshot':['frame_snapshot'],
 'tb_tmds':['tmds_encoder'],
 'tb_pipeline_recorder':['pipeline_recorder'],
 'tb_sync_health_probe':['sync_health_probe'],
 'tb_init_readback':['ov5640_init'],
 'tb_ycbcr':['ycbcr2rgb'],
 'tb_vga':['vga_timing','pattern_gen'],
 'tb_sccb':['sccb_master'],
 'tb_yuv_capture':['cam_capture','ycbcr2rgb','frame_buffer'],
 'tb_yuv_capture_source':['cam_capture','ycbcr2rgb','frame_buffer'],
 'tb_camera_status_snapshot':['camera_status_snapshot'],
 'tb_top_wiring':['top_genesys2','cam_capture','ycbcr2rgb','frame_buffer',
 'sccb_master','ov5640_init','sync_health_probe','camera_status_snapshot','uart_tx','uart_report','dvp_probe','debug_overlay','pattern_gen','vga_timing'],
 'tb_top_wiring_inverted':['top_genesys2','cam_capture','ycbcr2rgb','frame_buffer',
 'sccb_master','ov5640_init','sync_health_probe','camera_status_snapshot','uart_tx','uart_report','dvp_probe','debug_overlay','pattern_gen','vga_timing'],
}
tests['tb_yuv_word_observer']=['frame_snapshot']
tests['tb_raw_word_snapshot']=['frame_snapshot']
tests['tb_top_live_control']=tests['tb_top_wiring_inverted'][:]
tests['tb_top_rgb565']=tests['tb_top_wiring_inverted'][:]

tests['tb_top_reference_readout']=tests['tb_top_rgb565'][:]
tests['tb_rgb565_word_snapshot']=['frame_snapshot']
tests['tb_uart_rx']=['uart_rx']
tests['tb_camera_uart_control']=['camera_uart_control']
tests['tb_init_host_control']=['ov5640_init']
results=[]
for test,files in tests.items():
    if 'frame_buffer' in files or 'frame_snapshot' in files: files=files+['banked_frame_memory']
    if "top_genesys2" in files: files=files+["frame_snapshot","dvp_clean_sampler","uart_rx","camera_uart_control"]
    sources=[rtl/(s+'.v') for s in files]+[sim/(test+'.v')]
    if test.startswith('tb_top_'):sources.append(sim/'ov5640_yuyv_model.v')
    if test=='tb_top_reference_readout':sources.append(sim/'tb_top_rgb565.v')
    target=WORK/(test+'.vvp')
    command=[str(IVERILOG),'-g2012','-DSYNTHESIS','-s',test,'-o',str(target),*map(str,sources)]
    compile_result=subprocess.run(command,capture_output=True,text=True,timeout=60)
    (WORK/(test+'_compile.txt')).write_text(compile_result.stdout+compile_result.stderr)
    if compile_result.returncode:raise RuntimeError('Compile failed: '+test+' '+compile_result.stderr)
    started=time.monotonic();run=subprocess.run([str(VVP),str(target)],capture_output=True,text=True,timeout=90)
    output=run.stdout+run.stderr;(WORK/(test+'.txt')).write_text(output)
    passed=run.returncode==0 and 'ALL TESTS PASS' in output and 'FAIL' not in output and 'WATCHDOG' not in output
    print(f'{test}: {"PASS" if passed else "FAIL"} ({time.monotonic()-started:.1f}s)',flush=True)
    results.append({'test':test,'passed':passed,'log':str(WORK/(test+'.txt'))})
    if not passed:
        print(output[-5000:]);raise RuntimeError('Simulation failed: '+test)
(ROOT/'reports'/'FUNCTIONAL_TESTS.json').write_text(json.dumps({'passed':True,'tests':results,
 'scope':'Functional tests and actual top-level camera wiring. Top integration substitutes clock/HDMI primitives; not physical timing or TMDS proof.',
 'rtl_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(rtl.glob('*.v'))}},indent=2))
