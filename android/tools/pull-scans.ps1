<#
.SYNOPSIS
  Copies Easy Scanner's exports and photo sessions from a phone to this computer over adb.

.DESCRIPTION
  The app writes scans/scan_<time>.ply and sessions/<id>/ into its app-specific storage
  (/sdcard/Android/data/com.rawmechatronics.easyscanner/files). On Android 11+ only the
  app itself and adb can read that directory, so the copy runs from the computer side.

  Each pass copies files that are new here or whose size changed on the phone. It never
  deletes anything, on the phone or here. A file modified less than -SettleSec seconds
  ago (phone clock) is left for the next pass, because it may still be being written.

  The phone is taken on USB when it is there. Otherwise it is reached over Wi-Fi: at
  the address mDNS announces, or else at the last address seen while it was on USB
  (kept in <Dest>\.adb-addr-<serial>). Android 14 announces a phone only while its
  Wireless debugging is on, hence the remembered address. Wi-Fi needs
  `adb -s <serial> tcpip 5555` once over USB, and a phone reboot turns it off again.

.EXAMPLE
  .\pull-scans.ps1 -Serial <serial>            # one pass
  .\pull-scans.ps1 -Serial <serial> -Watch     # a pass every 20 s until Ctrl+C
#>
param(
    [Parameter(Mandatory)] [string]$Serial,
    [string]$Dest = (Join-Path $HOME 'EasyScanner'),
    [switch]$Watch,
    [int]$IntervalSec = 20,
    [int]$SettleSec = 10,
    [string]$Remote = '/sdcard/Android/data/com.rawmechatronics.easyscanner/files'
)

$AddrFile = Join-Path $Dest ".adb-addr-$Serial"

function Resolve-Transport {
    if ((& adb -s $Serial get-state 2>$null) -eq 'device') {
        # remember where the phone listens on Wi-Fi, for when the cable is out
        # (parsed here: quotes inside an adb shell argument do not survive Windows PowerShell)
        $port = "$(& adb -s $Serial shell getprop service.adb.tcp.port)".Trim()
        $inet = "$(& adb -s $Serial shell ip -4 addr show wlan0)"
        if ($port -match '^[1-9]\d*$' -and $inet -match 'inet (\d+\.\d+\.\d+\.\d+)') {
            New-Item -ItemType Directory -Force -Path $Dest | Out-Null
            Set-Content -LiteralPath $AddrFile -Value "$($Matches[1]):$port"
        }
        return $Serial
    }
    $candidates = @()
    # an announced phone: adb-<serial> _adb._tcp <ip>:<port>
    $line = & adb mdns services 2>$null | Where-Object { $_ -match "^adb-$Serial\s+_adb\._tcp" } | Select-Object -First 1
    if ($line -match '(\d+\.\d+\.\d+\.\d+:\d+)') { $candidates += $Matches[1] }
    if (Test-Path -LiteralPath $AddrFile) { $candidates += (Get-Content -LiteralPath $AddrFile -TotalCount 1).Trim() }
    foreach ($addr in ($candidates | Select-Object -Unique)) {
        if ((& adb -s $addr get-state 2>$null) -ne 'device') { & adb connect $addr 2>$null | Out-Null }
        if ((& adb -s $addr get-state 2>$null) -eq 'device') { return $addr }
    }
    return $null
}

function Sync-Once([string]$transport) {
    # one round trip: the phone's clock, then "<size> <mtime> <path>" per file
    $out = & adb -s $transport shell "date +%s; cd $Remote 2>/dev/null && find scans sessions -type f -exec stat -c '%s %Y %n' {} + 2>/dev/null"
    if ($LASTEXITCODE -ne 0 -and -not $out) { Write-Warning "listing failed on $transport"; return }
    $now = [int64]($out | Select-Object -First 1)
    $copied = 0
    foreach ($l in ($out | Select-Object -Skip 1)) {
        if ($l -notmatch '^(\d+) (\d+) (.+)$') { continue }
        $size = [int64]$Matches[1]; $mtime = [int64]$Matches[2]; $rel = $Matches[3]
        if ($now - $mtime -lt $SettleSec) { continue }
        $local = Join-Path $Dest ($rel -replace '/', '\')
        if ((Test-Path -LiteralPath $local) -and (Get-Item -LiteralPath $local).Length -eq $size) { continue }
        New-Item -ItemType Directory -Force -Path (Split-Path $local) | Out-Null
        $part = "$local.part"
        & adb -s $transport pull "$Remote/$rel" $part 2>$null | Out-Null
        if ($LASTEXITCODE -ne 0) {
            Write-Warning "pull failed: $rel"
            Remove-Item -LiteralPath $part -ErrorAction SilentlyContinue
            continue
        }
        Move-Item -Force -LiteralPath $part -Destination $local
        $copied++
        Write-Host ("{0} {1} ({2:N0} KB)" -f (Get-Date -Format HH:mm:ss), $rel, ($size / 1KB))
        # Photos stop writes laser.ply last: the session is complete
        if ($rel -match '^sessions/([^/]+)/laser\.ply$') {
            Write-Host ("{0} session {1} complete: {2}" -f (Get-Date -Format HH:mm:ss), $Matches[1], (Split-Path $local))
        }
    }
    if (-not $Watch) { Write-Host "$copied file(s) copied to $Dest" }
}

$last = ''
do {
    $t = Resolve-Transport
    $state = if ($t) { "phone $Serial via $t" } else { "phone $Serial not reachable (USB or Wi-Fi)" }
    if ($state -ne $last) { Write-Host "$(Get-Date -Format HH:mm:ss) $state"; $last = $state }
    if ($t) { Sync-Once $t }
    if ($Watch) { Start-Sleep -Seconds $IntervalSec }
} while ($Watch)
