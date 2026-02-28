#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if ! command -v powershell.exe >/dev/null 2>&1; then
  exit 0
fi

if ! command -v wslpath >/dev/null 2>&1; then
  exit 0
fi

PS_SCRIPT="$(mktemp /tmp/opencommotion-shim-XXXXXX.ps1)"
cat >"$PS_SCRIPT" <<'PS1'
param([string]$WslRoot)
$ErrorActionPreference = "Stop"
if ([string]::IsNullOrWhiteSpace($WslRoot)) {
  throw "Missing WSL root path"
}

$targetDir = Join-Path $env:USERPROFILE ".local\bin"
New-Item -ItemType Directory -Force -Path $targetDir | Out-Null
$cmdPath = Join-Path $targetDir "opencommotion.cmd"

$cmdLine = "wsl.exe bash -lc ""cd ''{0}'' && bash ./opencommotion %*""" -f $WslRoot
$cmdContent = "@echo off`r`nsetlocal`r`n$cmdLine`r`n"
Set-Content -Path $cmdPath -Value $cmdContent -Encoding Ascii

$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ([string]::IsNullOrWhiteSpace($userPath)) {
  $userPath = ""
}
if ($userPath -notmatch [Regex]::Escape($targetDir)) {
  $newPath = if ($userPath.Length -gt 0) { "$userPath;$targetDir" } else { "$targetDir" }
  [Environment]::SetEnvironmentVariable("Path", $newPath, "User")
  Write-Output "Installed Windows launcher: $cmdPath"
  Write-Output "Added to user PATH: $targetDir"
  Write-Output "Restart PowerShell to use: opencommotion -run"
} else {
  Write-Output "Installed Windows launcher: $cmdPath"
}

# Add Windows Firewall inbound allow rules so WSL2 services are reachable from
# the Windows browser via the WSL2 localhost relay (NAT mode).
$fwPorts = @(8000, 8001, 8010, 8011, 5173)
foreach ($p in $fwPorts) {
  $rule = "OpenCommotion-$p"
  Remove-NetFirewallRule -DisplayName $rule -ErrorAction SilentlyContinue
  try {
    New-NetFirewallRule -DisplayName $rule -Direction Inbound -Protocol TCP `
      -LocalPort $p -Action Allow -Profile Any | Out-Null
    Write-Output "Firewall: allowed inbound TCP $p"
  } catch {
    Write-Output "Firewall: could not add rule for port $p (may need admin) - $_"
  }
}
PS1

WINDOWS_PS_SCRIPT="$(wslpath -w "$PS_SCRIPT")"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$WINDOWS_PS_SCRIPT" -WslRoot "$ROOT"
rm -f "$PS_SCRIPT"
