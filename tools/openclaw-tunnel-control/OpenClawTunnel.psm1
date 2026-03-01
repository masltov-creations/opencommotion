Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Get-ProjectRoot {
  Split-Path -Parent $PSScriptRoot
}

function Get-ConfigPath {
  Join-Path $PSScriptRoot 'config.json'
}

function Get-DefaultConfig {
  @{
    TunnelPort = 18789
    WslDistro = ''
    WslUser = ''
    SshPath = 'ssh.exe'
    ControlUrl = 'http://127.0.0.1:18789/'
    LaunchMode = 'edge-app'
    EdgePath = 'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
    TaskName = 'OpenClawTunnelAutoStart'
    AutoOpenControlOnAutoStart = $true
  }
}

function Initialize-Config {
  $path = Get-ConfigPath
  if (-not (Test-Path $path)) {
    $default = Get-DefaultConfig | ConvertTo-Json -Depth 5
    Set-Content -Path $path -Value $default -Encoding UTF8
  }
}

function Get-Config {
  Initialize-Config
  $raw = Get-Content -Path (Get-ConfigPath) -Raw
  $cfg = $raw | ConvertFrom-Json
  $default = Get-DefaultConfig
  foreach ($prop in $default.Keys) {
    if (-not ($cfg.PSObject.Properties.Name -contains $prop)) {
      $cfg | Add-Member -NotePropertyName $prop -NotePropertyValue $default[$prop]
    }
  }
  return $cfg
}

function Save-Config {
  param(
    [Parameter(Mandatory = $true)]
    [psobject]$Config
  )
  $path = Get-ConfigPath
  $json = $Config | ConvertTo-Json -Depth 6
  Set-Content -Path $path -Value $json -Encoding UTF8
}

function Invoke-WslCommand {
  param(
    [Parameter(Mandatory = $true)]
    [string]$Command,
    [string]$Distro
  )

  $args = @()
  if ($Distro -and $Distro.Trim()) {
    $args += @('-d', $Distro)
  }
  $args += @('bash', '-lc', $Command)

  & wsl.exe @args
}

function Get-WslUser {
  param([psobject]$Config)
  if ($Config.WslUser -and $Config.WslUser.Trim()) {
    return $Config.WslUser.Trim()
  }
  $name = Invoke-WslCommand -Command 'whoami' -Distro $Config.WslDistro
  return ($name | Out-String).Trim()
}

function Get-WslIp {
  param([psobject]$Config)
  $ip = Invoke-WslCommand -Command "ip -4 addr show eth0 | sed -n 's/.*inet \\([0-9.]*\\)\\/.*/\\1/p' | head -n1" -Distro $Config.WslDistro
  $value = ($ip | Out-String).Trim()
  if (-not $value) {
    throw 'Could not resolve WSL IP address.'
  }
  return $value
}

function Get-TunnelPattern {
  param([int]$Port)
  return "127.0.0.1:$Port:127.0.0.1:$Port"
}

function Get-TunnelProcesses {
  param([psobject]$Config)
  $port = [int]$Config.TunnelPort
  $listeners = Get-NetTCPConnection -LocalAddress '127.0.0.1' -LocalPort $port -State Listen -ErrorAction SilentlyContinue
  if (-not $listeners) {
    return @()
  }
  $result = @()
  $processIds = @($listeners | Select-Object -ExpandProperty OwningProcess -Unique)
  foreach ($processId in $processIds) {
    $proc = Get-CimInstance Win32_Process -Filter "ProcessId = $processId" -ErrorAction SilentlyContinue
    if ($proc -and $proc.Name -ieq 'ssh.exe') {
      $result += $proc
    }
  }
  return @($result)
}

function Test-TunnelReachable {
  param([psobject]$Config)
  try {
    $resp = Invoke-WebRequest -Uri $Config.ControlUrl -UseBasicParsing -TimeoutSec 2
    return ($resp.StatusCode -ge 200 -and $resp.StatusCode -lt 400)
  }
  catch {
    return $false
  }
}

function Start-OpenClawTunnel {
  param([psobject]$Config)

  $existing = @(Get-TunnelProcesses -Config $Config)
  if ($existing.Count -gt 0) {
    return [pscustomobject]@{
      Started = $false
      Message = 'Tunnel already running.'
    }
  }

  $ip = Get-WslIp -Config $Config
  $user = Get-WslUser -Config $Config

  $args = @(
    '-N',
    '-o', 'ExitOnForwardFailure=yes',
    '-o', 'ServerAliveInterval=30',
    '-o', 'ServerAliveCountMax=3',
    '-o', 'StrictHostKeyChecking=accept-new',
    '-L', "127.0.0.1:$($Config.TunnelPort):127.0.0.1:$($Config.TunnelPort)",
    "$user@$ip"
  )

  $proc = Start-Process -FilePath $Config.SshPath -ArgumentList $args -WindowStyle Hidden -PassThru
  Start-Sleep -Milliseconds 700

  if ($proc.HasExited) {
    throw "Tunnel failed to start. ssh.exe exited with code $($proc.ExitCode)."
  }

  return [pscustomobject]@{
    Started = $true
    Message = "Tunnel started to $user@$ip"
  }
}

function Stop-OpenClawTunnel {
  param([psobject]$Config)
  $procs = @(Get-TunnelProcesses -Config $Config)
  if ($procs.Count -eq 0) {
    return [pscustomobject]@{
      Stopped = $false
      Message = 'No tunnel process found.'
    }
  }
  foreach ($proc in $procs) {
    Stop-Process -Id $proc.ProcessId -Force -ErrorAction SilentlyContinue
  }
  return [pscustomobject]@{
    Stopped = $true
    Message = "Stopped $($procs.Count) tunnel process(es)."
  }
}

function Open-ControlApp {
  param([psobject]$Config)

  if ($Config.LaunchMode -eq 'edge-app' -and (Test-Path $Config.EdgePath)) {
    Start-Process -FilePath $Config.EdgePath -ArgumentList @("--app=$($Config.ControlUrl)") | Out-Null
    return
  }

  Start-Process -FilePath $Config.ControlUrl | Out-Null
}

function Get-AutoStartEnabled {
  param([psobject]$Config)
  $startupDir = [Environment]::GetFolderPath('Startup')
  $startupCmd = Join-Path $startupDir "$($Config.TaskName).cmd"
  return (Test-Path $startupCmd)
}

function Enable-AutoStart {
  param([psobject]$Config)

  $startupDir = [Environment]::GetFolderPath('Startup')
  $startupCmd = Join-Path $startupDir "$($Config.TaskName).cmd"
  $cliPath = Join-Path $PSScriptRoot 'OpenClawTunnelCli.ps1'
  $command = 'powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "{0}" -Action AutoStart' -f $cliPath
  $content = "@echo off`r`n$command`r`n"
  Set-Content -Path $startupCmd -Value $content -Encoding ASCII
}

function Disable-AutoStart {
  param([psobject]$Config)
  $startupDir = [Environment]::GetFolderPath('Startup')
  $startupCmd = Join-Path $startupDir "$($Config.TaskName).cmd"
  Remove-Item -Path $startupCmd -ErrorAction SilentlyContinue
}

function Get-Status {
  param([psobject]$Config)

  $running = (@(Get-TunnelProcesses -Config $Config)).Count -gt 0
  $reachable = Test-TunnelReachable -Config $Config
  $auto = Get-AutoStartEnabled -Config $Config

  [pscustomobject]@{
    TunnelRunning = $running
    DashboardReachable = $reachable
    AutoStartEnabled = $auto
    Port = [int]$Config.TunnelPort
    Url = [string]$Config.ControlUrl
  }
}

Export-ModuleMember -Function *
