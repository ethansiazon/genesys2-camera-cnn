param([string]$Port='COM3',[int]$Seconds=18,[string]$OutDir='')
$ErrorActionPreference='Stop'
$diagnosticRoot=Split-Path $PSScriptRoot
if(-not $OutDir){$OutDir=Join-Path $diagnosticRoot '..\..\local_results\captures'}
New-Item -ItemType Directory -Path $OutDir -Force | Out-Null
$OutDir=(Resolve-Path -LiteralPath $OutDir).Path
$diagnosticStamp=Get-Date -Format 'yyyyMMdd_HHmmss'
$rawPath=Join-Path $OutDir ('diagnostics_'+$diagnosticStamp+'.txt')
$jsonPath=Join-Path $OutDir ('diagnostics_'+$diagnosticStamp+'.json')
$registerAddresses=@('4740','4300','501F','300E','3017','3018','3034','3035','3036','3037','3108','3824','3808','3809','380A','380B','3008','4713','3503','3500','3501','3502','350A','350B')
$ispAddresses=@('5000','5001','5005','3400','3401','3402','3403','3404','3405','3406','5380','5381','5382','5383','5384','5385','5386','5387','5388','5389','538A','538B','5480','5580')
$measurements=New-Object System.Collections.Generic.List[object]
$reader=New-Object System.IO.Ports.SerialPort($Port,115200,[System.IO.Ports.Parity]::None,8,[System.IO.Ports.StopBits]::One)
$reader.ReadTimeout=1200;$reader.NewLine="`n"
try {
 $reader.Open();$until=[DateTime]::UtcNow.AddSeconds($Seconds)
 while([DateTime]::UtcNow -lt $until) {
  try{$line=$reader.ReadLine().Trim()}catch [TimeoutException]{continue}
  Add-Content -LiteralPath $rawPath -Value $line
  $parts=$line -split '\s+'
  if($parts.Count -ne 8 -or ($parts|Where-Object {$_ -notmatch '^[0-9a-fA-F]{8}$'}).Count -gt 0){continue}
  $w=@($parts|ForEach-Object{[Convert]::ToUInt32($_,16)})
  $row=[ordered]@{time=(Get-Date -Format o);tag=$parts[0];raw=$line}
  switch($parts[0]) {
   'D1640000' {
    $row.switches=('{0:X2}' -f (($w[2] -shr 8) -band 255));$row.id=('{0:X4}' -f $w[1]);$row.leds=('{0:X2}' -f ($w[2] -band 255));$row.pclk_hz=$w[3]
    $row.vsync_raw_edges_per_second=$w[4];$row.href_raw_edges_per_second=$w[5]
    $row.vsync_filtered_edges_per_second=$w[6];$row.href_filtered_edges_per_second=$w[7]
    Write-Host ('ID={0} PCLK={1} | VSYNC raw/filtered={2}/{3} | HREF raw/filtered={4}/{5}' -f $row.id,$w[3],$w[4],$w[6],$w[5],$w[7])
   }
   'D1640001' {
    $row.vsync_high_cycles=$w[1];$row.vsync_max_high_cycles=$w[2];$row.vsync_max_low_cycles=$w[3]
    $row.href_high_cycles=$w[4];$row.href_max_high_cycles=$w[5];$row.href_max_low_cycles=$w[6];$row.clock_hz=$w[7]
    Write-Host ('VSYNC high {0:N2}% longest high/low {1:N3}/{2:N3} us | HREF high {3:N2}%' -f (100.0*$w[1]/$w[7]),(1000000.0*$w[2]/$w[7]),(1000000.0*$w[3]/$w[7]),(100.0*$w[4]/$w[7]))
   }
   'D1640002' {
    $registers=[ordered]@{}
    for($i=0;$i -lt 24;$i++){$registers[$registerAddresses[$i]]=('{0:X2}' -f (($w[1+[math]::Floor($i/4)] -shr (8*($i%4))) -band 255))}
    $row.registers=$registers;$row.read_nack_mask=('{0:X6}' -f $w[7])
    Write-Host ('READBACK: '+(($registers.GetEnumerator()|ForEach-Object{$_.Key+'='+$_.Value}) -join ' ')+' NACK='+$row.read_nack_mask)
   }
   'D1640004' {
    $registers=[ordered]@{}
    for($i=0;$i -lt 24;$i++){$registers[$ispAddresses[$i]]=('{0:X2}' -f (($w[1+[math]::Floor($i/4)] -shr (8*($i%4))) -band 255))}
    $row.isp_registers=$registers;$row.isp_read_nack_mask=('{0:X6}' -f $w[7])
    Write-Host ('ISP READBACK: '+(($registers.GetEnumerator()|ForEach-Object{$_.Key+'='+$_.Value}) -join ' ')+' NACK='+$row.isp_read_nack_mask)
   }
   'D1640003' {
    $row.frame_counter=$w[2];$row.pixels_per_frame=$w[3];$row.x_max=($w[4] -band 1023);$row.y_max=(($w[4] -shr 16) -band 1023)
    $row.last_href_bytes=$w[5];$row.longest_href_bytes=$w[6];$row.href_rises_per_second=$w[7];$row.short_lines=($w[1] -band 65535)
    Write-Host ('CAPTURE: frame={0} pixels={1} xmax/ymax={2}/{3} HREF last/max bytes={4}/{5}' -f $w[2],$w[3],$row.x_max,$row.y_max,$w[5],$w[6])
   }
  }
  $measurements.Add([pscustomobject]$row)
 }
} finally {
 if($reader.IsOpen){$reader.Close()};$reader.Dispose()
 @($measurements.ToArray()) | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $jsonPath -Encoding UTF8
 Write-Host "Diagnostics saved: $jsonPath"
}
