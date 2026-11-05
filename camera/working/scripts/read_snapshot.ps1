param([string]$Port='COM3',[int]$Seconds=110,[string]$OutDir='',
 [ValidateSet('Auto','YUYV','RGB565')][string]$ExpectedFormat='Auto')
$ErrorActionPreference='Stop'
$traceRoot=Split-Path $PSScriptRoot
if(-not $OutDir){
 if(Test-Path -LiteralPath (Join-Path $traceRoot 'rtl')){$OutDir=Join-Path $traceRoot '..\..\local_results\captures'}
 else {$OutDir=Join-Path $traceRoot 'measurements/captures'}
}
New-Item -ItemType Directory -Path $OutDir -Force | Out-Null
$OutDir=(Resolve-Path -LiteralPath $OutDir).Path
$traceStamp=Get-Date -Format 'yyyyMMdd_HHmmss'
$outPath=Join-Path $OutDir ('raw_yuv_'+$traceStamp+'.txt')
$reader=New-Object System.IO.Ports.SerialPort($Port,115200,[System.IO.Ports.Parity]::None,8,[System.IO.Ports.StopBits]::One)
$reader.ReadTimeout=1000;$reader.NewLine="`n";$reader.ReadBufferSize=262144
$lines=New-Object System.Collections.Generic.List[string]
$nextIndex=0;$complete=$false;$resets=0
$detectedFormat=$null
try{
 $reader.Open();$until=[DateTime]::UtcNow.AddSeconds($Seconds)
 Write-Host 'Waiting for trace packet 0. SW7 must be up; board stays powered.'
 while([DateTime]::UtcNow -lt $until){
  try{$line=$reader.ReadLine().Trim()}catch [TimeoutException]{continue}
  $parts=$line -split '\s+'
  if($parts.Count -ne 8 -or $parts[0] -notmatch '^D16C[0-9A-Fa-f]{4}$' -or ($parts|Where-Object{$_ -notmatch '^[0-9A-Fa-f]{8}$'}).Count -gt 0){continue}
  $index=[Convert]::ToInt32($parts[0].Substring(4),16)
  if($index -eq 0){$lines.Clear();$nextIndex=0}
  if($index -ne $nextIndex){if($lines.Count){$resets++};$lines.Clear();$nextIndex=0;continue}
  $lines.Add($line);$nextIndex++
  if($nextIndex%256 -eq 0){Write-Host "Trace transfer: $nextIndex / 5487 packets"}
  if($nextIndex -eq 5487){
   $magic=$parts[7].ToUpper()
   if($magic -eq '59555630'){$detectedFormat='YUYV'}
   elseif($magic -eq '52353635'){$detectedFormat='RGB565'}
   else {throw 'Unknown capture format; saved data must not be guessed'}
   if($ExpectedFormat -ne 'Auto' -and $ExpectedFormat -ne $detectedFormat){throw 'Unexpected camera format; refusing to mark capture complete'}
   $complete=$true;break
  }
 }
}finally{
 if($reader.IsOpen){$reader.Close()};$reader.Dispose()
 $lines.ToArray()|Set-Content -LiteralPath $outPath -Encoding ASCII
 [ordered]@{time=(Get-Date -Format o);complete=$complete;format=$detectedFormat;packets=$lines.Count;resynchronizations=$resets;file=$outPath;sample_period_ns=$null;sample_count=76800;clock='camera PCLK'}|ConvertTo-Json|Set-Content -LiteralPath (Join-Path $OutDir 'LAST_RAW_YUV.json') -Encoding UTF8
}
if(-not $complete){throw "Trace incomplete. Kept $($lines.Count) packets in $outPath"}
Write-Host "TRACE COMPLETE: $outPath"
