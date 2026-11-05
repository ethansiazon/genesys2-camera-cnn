param(
 [ValidateSet('Ping','Read','Write','Preset','Restore','SelfTest')][string]$Action='Read',
 [string]$Port='COM3',
 [string[]]$Registers=@('300A','300B','3400','3401','3402','3403','3404','3405','3406','3503','3500','3501','3502','350A','350B'),
 [string[]]$Writes=@(),
 [ValidateSet('AutoWB','UnityWB','BaselineExposure')][string]$Preset='AutoWB',
 [string]$RestoreFile='', [string]$OutDir=''
)
$ErrorActionPreference='Stop'
Set-StrictMode -Version Latest
function New-ControlFrame([byte]$Id,[byte]$Opcode,[uint16]$Address,[byte]$Value) {
 [byte[]]$frame=@(0xA5,0x5A,$Id,$Opcode,($Address -shr 8),($Address -band 255),$Value,0)
 [byte]$checksum=0
 for($i=0;$i -lt 7;$i++){$checksum=$checksum -bxor $frame[$i]}
 $frame[7]=$checksum
 return ,$frame
}
function Convert-ControlReply([string]$Line) {
 $parts=$Line.Trim() -split '\s+'
 if($parts.Count -ne 8 -or @($parts|Where-Object {$_ -notmatch '^[0-9a-fA-F]{8}$'}).Count -ne 0){return $null}
 if($parts[0] -ne 'D1650001'){return $null}
 $v=@($parts|ForEach-Object {[Convert]::ToUInt32($_,16)})
 if($v[7] -ne 0x4C495645 -or $v[1] -gt 255 -or $v[2] -gt 255 -or $v[3] -gt 7 -or $v[4] -gt 65535 -or $v[5] -gt 255 -or $v[6] -gt 255){throw 'Invalid live-control response fields/signature'}
 return [pscustomobject]@{id=$v[1];opcode=$v[2];status=$v[3];address=$v[4];requested=$v[5];value=$v[6];raw=$Line}
}
function Parse-HexAddress([string]$Text) {
 if($Text -notmatch '^[0-9a-fA-F]{4}$'){throw 'Register addresses require exactly four hexadecimal digits'}
 return [Convert]::ToUInt16($Text,16)
}
if($Action -eq 'SelfTest') {
 $hex=([BitConverter]::ToString((New-ControlFrame 1 0x52 0x3406 0))).Replace('-','')
 if($hex -ne 'A55A01523406009E'){throw "Encoder self-test failed: $hex"}
 $reply=Convert-ControlReply 'D1650001 00000001 00000052 00000000 00003406 00000000 00000001 4C495645'
 if($reply.id -ne 1 -or $reply.address -ne 0x3406 -or $reply.value -ne 1){throw 'Decoder self-test failed'}
 if($null -ne (Convert-ControlReply 'D1640000 00005640 000040FF 00000000 00000000 00000000 00000000 00000000')){throw 'Telemetry filter self-test failed'}
 $caught=$false;try { $null=Convert-ControlReply 'D1650001 00000001 00000052 00000000 00003406 00000000 00000001 00000000' } catch {$caught=$true}
 if(-not $caught){throw 'Signature validation self-test failed'}
 Write-Host 'SELFTEST PASS: binary command, checksum, response decoder, telemetry filtering and signature rejection'
 return
}
if($Registers.Count -gt 64 -or $Writes.Count -gt 64){throw 'At most 64 register operations per invocation'}
foreach($item in $Registers){$null=Parse-HexAddress $item}
if($Action -eq 'Preset') {
 switch($Preset) {
  AutoWB {$Writes=@('3406=00')}
  UnityWB {$Writes=@('3406=01','3400=04','3401=00','3402=04','3403=00','3404=04','3405=00')}
  BaselineExposure {$Writes=@('3503=03','3500=00','3501=08','3502=00','350A=00','350B=10')}
 }
}
if($Action -eq 'Restore') {
 if(-not $RestoreFile){throw 'Restore requires the SESSION.json path from an earlier change'}
 $previous=Get-Content -LiteralPath $RestoreFile -Raw | ConvertFrom-Json
 $Writes=@($previous.changes | ForEach-Object {$_.address+'='+$_.before})
 [array]::Reverse($Writes)
}
foreach($item in $Writes){if($item -notmatch '^[0-9a-fA-F]{4}=[0-9a-fA-F]{2}$'){throw "Invalid register assignment: $item"}}
if($Action -eq 'Write' -and $Writes.Count -eq 0){throw 'Write requires -Writes 3406=01 (or another permitted assignment)'}
$repoRoot=Split-Path (Split-Path (Split-Path $PSScriptRoot))
if(-not $OutDir){$OutDir=Join-Path $repoRoot ('local_results/live_controls/'+(Get-Date -Format 'yyyyMMdd_HHmmss_fff'))}
if(Test-Path -LiteralPath $OutDir){throw 'Choose a new output directory for each session'}
New-Item -ItemType Directory -Path $OutDir -Force|Out-Null
$OutDir=(Resolve-Path -LiteralPath $OutDir).Path
$script:eventPath=Join-Path $OutDir 'transactions.jsonl'
$script:sessionPath=Join-Path $OutDir 'SESSION.json'
$script:requestId=0
$script:session=[ordered]@{started=(Get-Date -Format o);port=$Port;action=$Action;preset=$Preset;state='starting';changes=[System.Collections.Generic.List[object]]::new();reads=[System.Collections.Generic.List[object]]::new()}
function Save-Session {
 $script:session | ConvertTo-Json -Depth 7 | Set-Content -LiteralPath $script:sessionPath -Encoding UTF8
}
function Add-Event($Event) {$Event|ConvertTo-Json -Compress -Depth 5|Add-Content -LiteralPath $script:eventPath -Encoding UTF8}
$script:serial=[System.IO.Ports.SerialPort]::new($Port,115200,[System.IO.Ports.Parity]::None,8,[System.IO.Ports.StopBits]::One)
$script:serial.ReadTimeout=250;$script:serial.WriteTimeout=1000;$script:serial.NewLine="`n"
function Invoke-CameraRequest([byte]$Opcode,[uint16]$Address,[byte]$Value=0) {
 $script:requestId=($script:requestId%255)+1
 $id=[byte]$script:requestId
 $frame=New-ControlFrame $id $Opcode $Address $Value
 Add-Event ([ordered]@{time=(Get-Date -Format o);event='request';id=$id;opcode=$Opcode;address=('{0:X4}' -f $Address);requested=('{0:X2}' -f $Value)})
 $script:serial.Write($frame,0,$frame.Length)
 $deadline=[DateTime]::UtcNow.AddSeconds(6)
 while([DateTime]::UtcNow -lt $deadline) {
  try{$line=$script:serial.ReadLine().Trim()}catch [TimeoutException]{continue}
  Add-Event ([ordered]@{time=(Get-Date -Format o);event='wire';line=$line})
  $reply=Convert-ControlReply $line
  if($null -eq $reply -or $reply.id -ne $id){continue}
  if($reply.opcode -ne $Opcode -or $reply.address -ne $Address -or $reply.requested -ne $Value){throw 'Reply does not match the requested operation; stop without retry'}
  if($reply.status -ne 0) {
   $reason=@('OK','malformed command','register/value not allowed','SW7 recording active','camera NACK','operation timeout','UART framing error','write readback mismatch')[$reply.status]
   throw "Camera control failed: $reason. No automatic retry. A failed write may already have changed the camera; see saved before values."
  }
  return [byte]$reply.value
 }
 throw 'No verified live-control response within six seconds. Check r6 is loaded, UART/J15 connected and SW7 down. No automatic retry; write outcome may be unknown.'
}
Save-Session
try {
 $script:serial.Open();$script:serial.DiscardInBuffer()
 # Do not attempt any register mutation until the live-control firmware answers.
 $null=Invoke-CameraRequest 0x50 0
 $script:session.state='connected';Save-Session
 Write-Host 'Live camera control connected; command signature verified.'
 if($Action -eq 'Read') {
  foreach($item in $Registers) {
   $value=Invoke-CameraRequest 0x52 (Parse-HexAddress $item)
   $script:session.reads.Add([pscustomobject]@{address=$item.ToUpper();value=('{0:X2}' -f $value)})
   Save-Session;Write-Host ('{0} = {1:X2}' -f $item,$value)
  }
 } elseif($Action -in @('Write','Preset','Restore')) {
  foreach($item in $Writes) {
   $parts=$item.Split('=');$address=Parse-HexAddress $parts[0];$value=[Convert]::ToByte($parts[1],16)
   $before=Invoke-CameraRequest 0x52 $address
   $change=[pscustomobject]@{address=$parts[0].ToUpper();before=('{0:X2}' -f $before);requested=('{0:X2}' -f $value);actual=$null;state='pending'}
   $script:session.changes.Add($change);Save-Session
   try {
    $actual=Invoke-CameraRequest 0x57 $address $value
    if($actual -ne $value){throw 'Unexpected readback; stop'}
    $change.actual=('{0:X2}' -f $actual);$change.state='verified';Save-Session
    Write-Host ('{0}: {1} -> {2}; readback verified' -f $change.address,$change.before,$change.actual)
   } catch {$change.state='failed_or_uncertain';Save-Session;throw}
  }
 }
 $script:session.state='complete';Save-Session
} catch {
 $script:session.state='failed';$script:session.error=$_.Exception.Message;Save-Session;throw
} finally {
 if($script:serial.IsOpen){$script:serial.Close()};$script:serial.Dispose()
 Write-Host ('Session saved: '+$script:sessionPath)
}
