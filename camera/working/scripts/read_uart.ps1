param([string]$Port = '', [int]$Seconds = 20)
$ErrorActionPreference = 'Stop'
$availablePorts = [System.IO.Ports.SerialPort]::GetPortNames()
if (-not $Port) {
    if ($availablePorts.Count -ne 1) {
        Write-Host ('Available serial ports: ' + ($availablePorts -join ', '))
        throw 'Connect the board USB-UART port J15, then specify -Port COMx if needed.'
    }
    $Port = $availablePorts[0]
}
$reader = [System.IO.Ports.SerialPort]::new($Port,115200,[System.IO.Ports.Parity]::None,8,[System.IO.Ports.StopBits]::One)
$reader.ReadTimeout = 1200
$reader.NewLine = "`n"
$reportPath = Join-Path (Split-Path $PSScriptRoot) 'reports\camera_uart.txt'
try {
    $reader.Open()
    $until = [DateTime]::UtcNow.AddSeconds($Seconds)
    while ([DateTime]::UtcNow -lt $until) {
        try { $line = $reader.ReadLine().Trim() } catch [TimeoutException] { continue }
        Add-Content -LiteralPath $reportPath -Value $line
        $parts = $line -split '\s+'
        if ($parts.Count -eq 8 -and ($parts | Where-Object { $_ -notmatch '^[0-9A-Fa-f]{8}$' }).Count -eq 0) {
            $words = @($parts | ForEach-Object { [Convert]::ToUInt32($_,16) })
            Write-Host ('ID=0x{0:X4} | PCLK={1:N0} Hz | VSYNC={2}/sec | pixels/frame={3} | last x={4}, y={5}' -f $words[0],$words[1],$words[2],$words[6],($words[7] -band 1023),(($words[7] -shr 16) -band 1023))
        } else { Write-Host $line }
    }
} finally { if ($reader.IsOpen) { $reader.Close() }; $reader.Dispose() }
