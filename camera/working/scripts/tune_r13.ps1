param([string]$Port = 'COM3', [string]$OutDir = '', [switch]$Help)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

function Show-Help {
    Write-Host @'
  show                        Read the current picture settings
  exposure 400                Exposure in sensor lines (1 to 976 on R13)
  gain 1.25                   Sensor gain (1 to 4 times)
  wb auto                     Automatic white balance
  wb hold                     Freeze the current color gains
  wb 1.20 1.00 1.85           Manual red, green, blue gains (0.5 to 3.99 times)
  brightness 1                Digital brightness (-3 to +3)
  contrast 1                  Contrast (-3 to +3)
  saturation 1                Color strength (-3 to +3)
  gamma reference             Try the Espressif tone curve
  gamma start                 Restore the curve from when this session opened
  undo                        Reverse the most recent adjustment
  reset                       Restore settings from when this session opened
  save my_pick                Save a verified JSON snapshot to share
  help                        Show this list
  quit                        Close the terminal and keep live settings active
'@
}

if ($Help) { Show-Help; return }

$control = Join-Path $PSScriptRoot 'camera_control.ps1'
$catalog = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'camera_trials.json') -Raw | ConvertFrom-Json
$gammaAddresses = @(0x5480..0x5490 | ForEach-Object { '{0:X4}' -f $_ })
$wbGains = @('3400','3401','3402','3403','3404','3405')
$adjustable = @('3500','3501','3502','350A','350B','3406') + $wbGains +
    $gammaAddresses + @('5583','5584','5586','5587','5588','5580')
$profile = [ordered]@{
    '300A'=0x56; '300B'=0x40; '3035'=0x21; '3036'=0x5A; '3824'=5
    '380C'=7; '380D'=0x68; '380E'=3; '380F'=0xD8; '3814'=0x31; '3815'=0x31
    '4300'=0x61; '501F'=1; '503D'=0; '3503'=3
}
$addresses = @($profile.Keys) + @('5000','5001') + $adjustable
if (-not $OutDir) {
    $root = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '../../..')).Path
    $OutDir = Join-Path $root ('local_results/camera_tuner/' + (Get-Date -Format 'yyyyMMdd_HHmmss_fff'))
}
if (Test-Path -LiteralPath $OutDir) { throw 'Choose a new session directory.' }
New-Item -ItemType Directory -Path $OutDir | Out-Null
$OutDir = (Resolve-Path -LiteralPath $OutDir).Path
$history = [System.Collections.Generic.Stack[object]]::new()
$script:uncertainWrite = $false

function Read-Settings {
    $folder = Join-Path $OutDir ('read_' + [guid]::NewGuid().ToString('N'))
    & $control -Action Read -Port $Port -Registers $addresses -OutDir $folder 6>$null
    $session = Get-Content -LiteralPath (Join-Path $folder 'SESSION.json') -Raw | ConvertFrom-Json
    if ($session.state -ne 'complete') { throw 'Camera read did not finish.' }
    $values = [ordered]@{}
    foreach ($row in $session.reads) { $values[$row.address] = [Convert]::ToInt32($row.value, 16) }
    if ($values.Count -ne $addresses.Count) { throw 'Camera read was incomplete.' }
    foreach ($address in $profile.Keys) {
        if ($values[$address] -ne $profile[$address]) {
            throw "Camera mode differs at register $address. Load R13, select only SW6, and reopen the tuner."
        }
    }
    return $values
}

function Write-Settings($Before, $Target) {
    $prior = [ordered]@{}
    $writes = foreach ($address in $Target.Keys) {
        if ($Before[$address] -ne $Target[$address]) {
            $prior[$address] = $Before[$address]
            '{0}={1:X2}' -f $address, $Target[$address]
        }
    }
    if ($prior.Count -eq 0) { Write-Host 'Already at that setting.'; return $prior }
    $folder = Join-Path $OutDir ('write_' + [guid]::NewGuid().ToString('N'))
    $script:uncertainWrite = $true
    & $control -Action Write -Port $Port -Writes @($writes) -OutDir $folder 6>$null
    $session = Get-Content -LiteralPath (Join-Path $folder 'SESSION.json') -Raw | ConvertFrom-Json
    if ($session.state -ne 'complete' -or @($session.changes).Count -ne $prior.Count) {
        throw 'The camera did not verify the complete adjustment.'
    }
    foreach ($change in $session.changes) {
        if ($change.state -ne 'verified' -or [Convert]::ToInt32($change.actual, 16) -ne $Target[$change.address]) {
            throw 'The camera returned an unexpected value.'
        }
        $prior[$change.address] = [Convert]::ToInt32($change.before, 16)
    }
    if ($prior.Contains('3406')) {
        foreach ($address in $wbGains) {
            if ($prior['3406'] -eq 0) {
                $prior.Remove($address)
            } else {
                # Auto WB can replace the old manual gains before an undo.
                $prior[$address] = $Before[$address]
            }
        }
    }
    $script:uncertainWrite = $false
    Write-Host 'Applied and verified. Compare the HDMI image.'
    return $prior
}

function Get-Number([string]$Text, [double]$Min, [double]$Max, [switch]$Integer) {
    $number = 0.0
    if (-not [double]::TryParse($Text, [Globalization.NumberStyles]::Float,
            [Globalization.CultureInfo]::InvariantCulture, [ref]$number) -or
        [double]::IsNaN($number) -or $number -lt $Min -or $number -gt $Max -or
        ($Integer -and $number -ne [math]::Truncate($number))) {
        throw "Enter a value between $Min and $Max$(if ($Integer) { ' (whole numbers only)' })."
    }
    return $number
}

function Get-PictureSettings($Values) {
    $brightness = $Values['5587'] / 16.0
    if ($Values['5588'] -band 8) { $brightness = -$brightness }
    $contrastEnabled = [bool]($Values['5001'] -band 0x80) -and [bool]($Values['5580'] -band 4)
    $saturationEnabled = [bool]($Values['5001'] -band 0x80) -and
        (($Values['5580'] -band 2) -ne 0) -and (($Values['5588'] -band 0x40) -ne 0)
    [ordered]@{
        exposure_lines = ($Values['3500'] -shl 12) + ($Values['3501'] -shl 4) + ($Values['3502'] -shr 4)
        gain = (($Values['350A'] -shl 8) + $Values['350B']) / 16.0
        white_balance = if ($Values['3406'] -eq 0) { 'auto' } else { 'manual' }
        red_gain = [math]::Round((($Values['3400'] -shl 8) + $Values['3401']) / 1024.0, 3)
        green_gain = [math]::Round((($Values['3402'] -shl 8) + $Values['3403']) / 1024.0, 3)
        blue_gain = [math]::Round((($Values['3404'] -shl 8) + $Values['3405']) / 1024.0, 3)
        brightness = if ($contrastEnabled) { $brightness } else { 'off' }
        contrast = if ($contrastEnabled) { ($Values['5586'] - 32) / 8.0 } else { 'off' }
        saturation = if ($saturationEnabled) { ($Values['5583'] - 64) / 8.0 } else { 'stock' }
    }
}

function Save-Preset($Values, [string]$Label) {
    if ($Label -notmatch '^[a-zA-Z0-9_-]{1,40}$') { throw 'Use letters, numbers, hyphens or underscores in the preset name.' }
    $path = Join-Path $OutDir ($Label + '.json')
    if (Test-Path -LiteralPath $path) { throw 'That preset name already exists in this session.' }
    $readback = [ordered]@{}
    foreach ($address in $Values.Keys) { $readback[$address] = '{0:X2}' -f $Values[$address] }
    $startup = [ordered]@{}
    foreach ($address in $adjustable) {
        if ($Values['3406'] -eq 0 -and $address -in $wbGains) { continue }
        $startup[$address] = $readback[$address]
    }
    [ordered]@{
        schema = 1; expected_bitstream = 'R13'; saved_at = (Get-Date -Format o)
        settings = (Get-PictureSettings $Values); image_registers_hex = $startup
        sensor_readback_hex = $readback
    } | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $path -Encoding UTF8
    Write-Host "Saved preset: $path"
}

Write-Host 'R13 Camera Tuner. Watch HDMI while you type commands here.'
Write-Host 'Use UART/J15 only, leave only SW6 up, and avoid BTNC while tuning.'
$initial = Read-Settings
Write-Host "Connected to $Port. R13 sensor settings verified."
Write-Host "Session folder: $OutDir"
Show-Help

while ($true) {
    $line = Read-Host 'camera'
    if ($null -eq $line) { break }
    if (-not $line.Trim()) { continue }
    $parts = $line.Trim() -split '\s+'
    $command = $parts[0].ToLowerInvariant()
    if ($command -eq 'quit') { break }
    if ($command -eq 'help') { Show-Help; continue }
    try {
        $count = $parts.Count
        if (($command -in @('show','undo','reset') -and $count -ne 1) -or
            ($command -in @('exposure','gain','brightness','contrast','saturation','gamma','save') -and $count -ne 2) -or
            ($command -eq 'wb' -and $count -notin @(2,4))) { throw 'Check command syntax with help.' }
        if ($command -notin @('show','undo','reset','exposure','gain','brightness','contrast','saturation','gamma','save','wb')) {
            throw 'Unknown command. Type help for the list.'
        }
        $values = Read-Settings
        $target = [ordered]@{}
        if ($command -in @('brightness','contrast','saturation') -and -not ($values['5001'] -band 0x80)) {
            throw 'The camera digital-effects block is disabled.'
        }
        switch ($command) {
            'show' { [pscustomobject](Get-PictureSettings $values) | Format-List | Out-Host; continue }
            'save' { Save-Preset $values $parts[1]; continue }
            'exposure' {
                $max = (($values['380E'] -shl 8) + $values['380F']) - 8
                $encoded = [int](Get-Number $parts[1] 1 $max -Integer) -shl 4
                $target['3500'] = ($encoded -shr 16) -band 15
                $target['3501'] = ($encoded -shr 8) -band 255
                $target['3502'] = $encoded -band 240
            }
            'gain' {
                $target['350A'] = 0
                $target['350B'] = [int][math]::Round(16 * (Get-Number $parts[1] 1 4))
            }
            'wb' {
                if ($count -eq 2) {
                    if ($parts[1] -notin @('auto','hold')) { throw 'Use wb auto, wb hold, or wb RED GREEN BLUE.' }
                    $target['3406'] = [int]($parts[1] -eq 'hold')
                } else {
                    $target['3406'] = 1
                    for ($i = 0; $i -lt 3; $i++) {
                        $encoded = [int][math]::Round(1024 * (Get-Number $parts[$i+1] 0.5 3.99))
                        $target[$wbGains[2*$i]] = $encoded -shr 8
                        $target[$wbGains[2*$i+1]] = $encoded -band 255
                    }
                }
            }
            'brightness' {
                $level = [int](Get-Number $parts[1] -3 3 -Integer)
                $target['5587'] = 16 * [math]::Abs($level)
                $target['5588'] = ($values['5588'] -band 0xF7) -bor (8 * [int]($level -lt 0))
                $target['5580'] = $values['5580'] -bor 4
            }
            'contrast' {
                $target['5586'] = 32 + 8 * [int](Get-Number $parts[1] -3 3 -Integer)
                $target['5580'] = $values['5580'] -bor 4
            }
            'saturation' {
                $strength = 64 + 8 * [int](Get-Number $parts[1] -3 3 -Integer)
                $target['5583'] = $strength
                $target['5584'] = $strength
                $target['5588'] = $values['5588'] -bor 0x40
                $target['5580'] = $values['5580'] -bor 2
            }
            'gamma' {
                if ($parts[1] -eq 'start') {
                    foreach ($address in $gammaAddresses) { $target[$address] = $initial[$address] }
                } elseif ($parts[1] -eq 'reference') {
                    if (-not ($values['5000'] -band 0x20)) { throw 'The camera gamma block is disabled.' }
                    foreach ($assignment in $catalog.trials.GammaReference.writes) {
                        $address, $hex = $assignment.Split('=')
                        $target[$address] = [Convert]::ToInt32($hex, 16)
                    }
                } else { throw 'Use gamma reference or gamma start.' }
            }
            'undo' {
                if ($history.Count -eq 0) { Write-Host 'No adjustment to undo.'; continue }
                $target = $history.Peek()
            }
            'reset' {
                foreach ($address in $adjustable) {
                    if ($initial['3406'] -eq 0 -and $address -in $wbGains) { continue }
                    $target[$address] = $initial[$address]
                }
            }
        }
        if ($command -in @('show','save') -or $target.Count -eq 0) { continue }
        $prior = Write-Settings $values $target
        if ($command -eq 'undo') { $null = $history.Pop() }
        elseif ($command -eq 'reset') { $history.Clear() }
        elseif ($prior.Count -gt 0) { $history.Push($prior) }
    } catch {
        Write-Host $_.Exception.Message -ForegroundColor Yellow
        if ($script:uncertainWrite) {
            throw "An adjustment may be incomplete. Readbacks are in $OutDir. Press BTNC to restore R13 startup and reopen the tuner."
        }
    }
}
