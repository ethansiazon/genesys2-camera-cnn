param(
 [string]$Port='', [string]$Python='python', [string]$OutDir='',
 [ValidateRange(10,300)][int]$ArmTimeoutSeconds=90,
 [ValidateRange(45,300)][int]$TransferTimeoutSeconds=120,
 [switch]$SelfTest
)
$ErrorActionPreference='Stop'
Set-StrictMode -Version Latest
function Parse-CameraPacket([string]$Line) {
 $parts=$Line.Trim() -split '\s+'
 if($parts.Count -ne 8 -or @($parts | Where-Object {$_ -notmatch '^[0-9a-fA-F]{8}$'}).Count){return $null}
 return ,@($parts | ForEach-Object {[Convert]::ToUInt32($_,16)})
}
function Test-NormalView($Words) {
 if($null -eq $Words -or $Words[0] -ne 0xD1640000L){return $false}
 if(($Words[1] -band 65535) -ne 0x5640){throw 'Camera ID is not 5640; check the loaded bitstream and wiring'}
 $switches=($Words[2] -shr 8) -band 255
 # SW6 must be up; SW1/2/4/5/7 down. SW0 overlay and SW3 range are recorded.
 return (($switches -band 0xF6) -eq 0x40)
}
if($SelfTest) {
 $ok=Parse-CameraPacket 'D1640000 00005640 00004000 00000000 00000000 00000000 00000000 00000000'
 if(-not (Test-NormalView $ok)){throw 'Normal-view parser failed'}
 foreach($switches in @(0,0x42,0x44,0x50,0x60,0xC0)) {
  $bad=$ok.Clone();$bad[2]=$switches -shl 8
  if(Test-NormalView $bad){throw 'Bad switch state accepted'}
 }
 if($null -ne (Parse-CameraPacket 'D16A0000 BAD')){throw 'Malformed packet accepted'}
 Write-Host 'SELFTEST PASS: camera telemetry, switch gates and packet parsing; no hardware opened.'
 return
}
# Fail before opening serial if the local PNG decoder cannot run.
& $Python -c 'from PIL import Image'
if($LASTEXITCODE -ne 0){throw 'Python with Pillow is required; no serial connection opened'}
Write-Host 'PNG decoder ready.'
if(-not $Port) {
 $devices=@(Get-CimInstance Win32_PnPEntity | Where-Object {
  $_.PNPDeviceID -match 'VID_0403.PID_6001' -and $_.Name -match '\(COM\d+\)'
 })
 $known=@($devices | Where-Object {$_.PNPDeviceID -match 'AV0KS1EZ'})
 if($known.Count -eq 1){$devices=$known}
 if($devices.Count -ne 1){throw 'Cannot uniquely identify USB-UART/J15. Run with -Port COM3 (use your actual port); no automatic retries.'}
 $null=$devices[0].Name -match '\((COM\d+)\)';$Port=$Matches[1]
}
if(-not $OutDir){$OutDir=Join-Path ([Environment]::GetFolderPath('Desktop')) 'Genesys2-Camera-Images'}
$session=Join-Path $OutDir ('capture_'+(Get-Date -Format 'yyyyMMdd_HHmmss_fff'))
if(Test-Path -LiteralPath $session){throw 'Capture folder exists; existing images preserved'}
New-Item -ItemType Directory -Path $session -Force | Out-Null
$session=(Resolve-Path -LiteralPath $session).Path
$raw=Join-Path $session 'transfer.txt'
$lines=[System.Collections.Generic.List[string]]::new()
$state=[ordered]@{started=(Get-Date -Format o);port=$Port;state='waiting_for_normal_view';complete=$false;packets=0;resynchronizations=0;normal_view_telemetry=$null;source_bitstream='last_exposure_test';raw_file=$raw;image=$null}
function Save-CaptureState {$state | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $session 'CAPTURE.json') -Encoding UTF8}
$reader=[System.IO.Ports.SerialPort]::new($Port,115200,[System.IO.Ports.Parity]::None,8,[System.IO.Ports.StopBits]::One)
$reader.ReadTimeout=500;$reader.NewLine="`n";$reader.ReadBufferSize=262144
$ready=$false;$next=0;$complete=$false;$lastProgress=0
Save-CaptureState
try {
 $reader.Open();$reader.DiscardInBuffer()
 Write-Host ('Listening on '+$Port+'. Keep ONLY SW6 up and SW7 DOWN. Do not press BTNC now.')
 Write-Host 'Waiting for normal live-camera telemetry before allowing a fresh capture...'
 $deadline=[DateTime]::UtcNow.AddSeconds($ArmTimeoutSeconds)
 $absoluteDeadline=[DateTime]::UtcNow.AddSeconds($ArmTimeoutSeconds+$TransferTimeoutSeconds+15)
 while([DateTime]::UtcNow -lt $deadline -and [DateTime]::UtcNow -lt $absoluteDeadline) {
  try{$line=$reader.ReadLine().Trim()}catch [TimeoutException]{continue}
  $words=Parse-CameraPacket $line
  if($null -eq $words){continue}
  if(-not $ready) {
   if(Test-NormalView $words) {
    $ready=$true;$state.state='ready_for_switch';$state.normal_view_telemetry=$line;Save-CaptureState
    Write-Host 'READY: hold the camera still and raise SW7, leaving SW6 up. Do NOT press BTNC.'
    Write-Host 'The next complete camera frame will be saved. Leave SW7 up until transfer finishes.'
    $deadline=[DateTime]::UtcNow.AddSeconds($ArmTimeoutSeconds)
   }
   continue
  }
  if(($words[0] -band 0xFFFF0000L) -eq 0xD16C0000L){throw 'Raw-YUV/RGB experiment firmware is loaded. This project needs the original last_exposure_test bitstream.'}
  if(($words[0] -band 0xFFFF0000L) -ne 0xD16A0000L){continue}
  $index=[int]($words[0] -band 65535)
  if($index -eq 0) {
   $lines.Clear();$next=0;$lastProgress=0;$state.state='receiving'
   $deadline=[DateTime]::UtcNow.AddSeconds($TransferTimeoutSeconds)
  }
  if($index -ne $next) {
   if($lines.Count){$state.resynchronizations++}
   $lines.Clear();$next=0;continue
  }
  $lines.Add($line);$next++;$state.packets=$next
  if($next-$lastProgress -ge 512){Write-Host ('Receiving image: '+[math]::Floor(100*$next/5487)+'%');$lastProgress=$next;Save-CaptureState}
  if($next -eq 5487){$complete=$true;break}
 }
 if(-not $complete){throw 'Capture timed out. Keep the preferred bitstream loaded, use UART/J15 and follow the SW7 prompt; partial data was saved.'}
} catch {
 $state.state='failed';$state.error=$_.Exception.Message;throw
} finally {
 if($reader.IsOpen){$reader.Close()};$reader.Dispose()
 $lines.ToArray() | Set-Content -LiteralPath $raw -Encoding ASCII
 Save-CaptureState
}
try {
 & $Python (Join-Path $PSScriptRoot 'save_snapshot_image.py') --input $raw --out-dir $session
 if($LASTEXITCODE -ne 0){throw 'Image validation failed; keep transfer.txt for debugging. No image accepted.'}
 $state.state='complete';$state.complete=$true;$state.image=Join-Path $session 'image.png';Save-CaptureState
 Write-Host 'DONE. Lower SW7 to re-arm for the next picture; leave SW6 up.'
 Write-Host ('Image folder: '+$session)
} catch {$state.state='decode_failed';$state.error=$_.Exception.Message;Save-CaptureState;throw}
