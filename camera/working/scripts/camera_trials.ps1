param(
 [ValidateSet('List','Plan','Apply','Restore','SelfTest')][string]$Action='List',
 [string]$Trial='', [string]$Port='COM3',
 [ValidateSet('YUYV','RGB565')][string]$ExpectedFormat='YUYV',
 [string]$OutDir='', [string]$RestoreFile=''
)
$ErrorActionPreference='Stop'
Set-StrictMode -Version Latest
$catalog=Get-Content -LiteralPath (Join-Path $PSScriptRoot 'camera_trials.json') -Raw | ConvertFrom-Json
$entries=@($catalog.trials.PSObject.Properties)
if($Action -eq 'List') {
 $entries | ForEach-Object { [pscustomobject]@{Trial=$_.Name;Description=$_.Value.label;HoldWBFirst=$_.Value.require_held_wb} } | Format-Table -AutoSize
 return
}
if($Action -eq 'SelfTest') {
 foreach($entry in $entries) {
  if(@($entry.Value.writes).Count -eq 0){throw 'Empty recipe'}
  foreach($w in $entry.Value.writes) {
   if($w -notmatch '^(340[0-6]|350[0-2]|538[1-9AB]|548[0-9A-F]|5490)=[0-9A-F]{2}$') {throw "Unexpected recipe register/value: $w"}
  }
 }
 Write-Host ('SELFTEST PASS: '+$entries.Count+' recipes; no hardware opened.')
 return
}
$recipe=$null
if($Action -ne 'Restore') {
 $property=$catalog.trials.PSObject.Properties[$Trial]
 if($null -eq $property){throw 'Select a trial from -Action List'}
 $recipe=$property.Value
 if($Action -eq 'Plan') {
  [ordered]@{trial=$Trial;format=$ExpectedFormat;label=$recipe.label;purpose=$recipe.purpose;writes=$recipe.writes;hold_wb_first=$recipe.require_held_wb;hardware_opened=$false} | ConvertTo-Json -Depth 5
  return
 }
} elseif(-not $RestoreFile -or -not (Test-Path -LiteralPath $RestoreFile)) {throw 'Restore requires the saved change SESSION.json'}
if(-not $OutDir) {
 $repoRoot=Split-Path (Split-Path (Split-Path $PSScriptRoot))
 if(-not (Test-Path -LiteralPath (Join-Path $repoRoot 'camera/working'))) {$repoRoot=Split-Path $PSScriptRoot}
 $OutDir=Join-Path $repoRoot ('local_results/picture_trials/'+(Get-Date -Format 'yyyyMMdd_HHmmss_fff'))
}
if(Test-Path -LiteralPath $OutDir){throw 'Choose a new output directory'}
New-Item -ItemType Directory -Path $OutDir | Out-Null
$OutDir=(Resolve-Path -LiteralPath $OutDir).Path
$control=Join-Path $PSScriptRoot 'camera_control.ps1'
# Read-only preflight is saved before any write. SW7 must be down, no capture
# reader or other serial client may own the port. Existing firmware enforces it.
& $control -Action Read -Port $Port -Registers '300A','300B','4300','501F','3503','3500','3501','3502','350A','350B','380E','380F','3406','3400','3401','3402','3403','3404','3405','5000','5001' -OutDir (Join-Path $OutDir 'preflight')
$before=Get-Content -LiteralPath (Join-Path $OutDir 'preflight/SESSION.json') -Raw | ConvertFrom-Json
if($before.state -ne 'complete'){throw 'Preflight incomplete; no trial writes'}
$regs=@{}
foreach($row in $before.reads){$regs[$row.address]=[Convert]::ToInt32($row.value,16)}
if($regs['300A'] -ne 0x56 -or $regs['300B'] -ne 0x40){throw 'Unexpected sensor ID; no trial writes'}
if($ExpectedFormat -eq 'RGB565'){$wantedFormat=0x61;$wantedMux=1}else{$wantedFormat=0x30;$wantedMux=0}
if($regs['4300'] -ne $wantedFormat -or $regs['501F'] -ne $wantedMux){throw 'Loaded sensor format differs from ExpectedFormat; no trial writes'}
if($Action -eq 'Restore') {
 & $control -Action Restore -Port $Port -RestoreFile $RestoreFile -OutDir (Join-Path $OutDir 'change')
} else {
 if($recipe.require_held_wb -and $regs['3406'] -ne 1){throw 'First let automatic WB settle, then apply HoldWB separately. No trial writes.'}
 if($recipe.family -eq 'exposure') {
  if($regs['3503'] -ne 3 -or $regs['350A'] -ne 0 -or $regs['350B'] -ne 0x10){throw 'Exposure bracket requires manual AEC/AGC and gain1x; no trial writes'}
  $vts=($regs['380E'] -shl 8) -bor $regs['380F']
  if($recipe.exposure_lines -gt $vts-8){throw 'Exposure too close to current frame length; no trial writes'}
 }
 $recipe | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $OutDir 'RECIPE.json') -Encoding UTF8
 & $control -Action Write -Port $Port -Writes @($recipe.writes) -OutDir (Join-Path $OutDir 'change')
}
Write-Host ('Readback and rollback values saved in '+(Join-Path $OutDir 'change/SESSION.json'))
Write-Host 'Keep scene fixed, allow settling, capture before/after, and restore this trial before testing another family. No automatic retry.'
