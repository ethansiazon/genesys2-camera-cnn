$ErrorActionPreference='Stop'
$restoreRoot=$PSScriptRoot
$restoreBit=Join-Path $restoreRoot 'camera_hdmi.bit'
if((Get-FileHash -Algorithm SHA256 -LiteralPath $restoreBit).Hash.ToLower() -ne 'b0cb809916ab4df4265cfb1f2007d68e4598f4b6cde008da9a39093d6e46a9b3'){throw 'Bitstream hash mismatch'}
$restoreUsb=@(Get-PnpDevice -PresentOnly | Where-Object InstanceId -Match '^USB\VID_0403')
if(-not ($restoreUsb.InstanceId -match 'PID_6010') -or ($restoreUsb.InstanceId -match 'PID_6001')){throw 'Connect JTAG/J17 only, with UART/J15 unplugged'}
$restoreTools=@(Get-CimInstance Win32_Process | Where-Object Name -Match '^(vivado|hw_server|cs_server)\.exe$')
if($restoreTools.Count){throw 'Close existing Vivado/hardware tools before restoring'}
& 'C:\AMDDesignTools\2026.1\Vivado\bin\vivado.bat' -mode batch -source (Join-Path $restoreRoot 'scripts\program_diagnostics.tcl') -log (Join-Path $restoreRoot 'reports\restore.log') -journal (Join-Path $restoreRoot 'reports\restore.jou')
if($LASTEXITCODE -ne 0){throw 'Programming did not complete; inspect reports/restore.log'}
Write-Host 'Best saved camera receiver loaded. Only SW6 up, then press BTNC for live video.'
