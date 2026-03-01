param(
  [ValidateSet('Start', 'Stop', 'Status', 'Open', 'EnableAutoStart', 'DisableAutoStart', 'AutoStart')]
  [string]$Action = 'Status'
)

$ErrorActionPreference = 'Stop'
Import-Module (Join-Path $PSScriptRoot 'OpenClawTunnel.psm1') -Force

$config = Get-Config

switch ($Action) {
  'Start' {
    $result = Start-OpenClawTunnel -Config $config
    Write-Host $result.Message
  }
  'Stop' {
    $result = Stop-OpenClawTunnel -Config $config
    Write-Host $result.Message
  }
  'Status' {
    $status = Get-Status -Config $config
    $status | Format-List
  }
  'Open' {
    Open-ControlApp -Config $config
    Write-Host 'Control app launch requested.'
  }
  'EnableAutoStart' {
    Enable-AutoStart -Config $config
    Write-Host 'Auto start enabled.'
  }
  'DisableAutoStart' {
    Disable-AutoStart -Config $config
    Write-Host 'Auto start disabled.'
  }
  'AutoStart' {
    try {
      Start-OpenClawTunnel -Config $config | Out-Null
    }
    catch {
    }

    if ($config.AutoOpenControlOnAutoStart) {
      Start-Sleep -Seconds 1
      try {
        Open-ControlApp -Config $config
      }
      catch {
      }
    }
  }
}
