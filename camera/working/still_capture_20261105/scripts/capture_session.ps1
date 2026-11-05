param([string]$Port='', [string]$Python='python', [string]$OutDir='')
$ErrorActionPreference='Stop'
$capture=Join-Path $PSScriptRoot 'capture_image.ps1'
Write-Host 'GENESYS 2 CAMERA PHOTOS' -ForegroundColor Cyan
Write-Host 'Keep UART/J15 connected and SW6 UP. Lower SW7 before each new photo.'
Write-Host 'Raise SW7 only when READY appears. Do not press BTNC during capture.'
do {
 try {
  & $capture -Port $Port -Python $Python -OutDir $OutDir
 } catch {
  Write-Host ('Capture stopped: '+$_.Exception.Message) -ForegroundColor Red
  Write-Host 'Any existing images are safe. Fix the reported issue before starting another capture.'
 }
 Write-Host ''
 $next=Read-Host 'Lower SW7. Press ENTER for another photo, or type Q then ENTER to finish'
 if($null -eq $next -or $next.Trim() -eq 'Q'){break}
} while($true)
Write-Host 'Camera capture session finished. The serial port is released.'
