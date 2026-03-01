Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

$ErrorActionPreference = 'Stop'
Import-Module (Join-Path $PSScriptRoot 'OpenClawTunnel.psm1') -Force

$config = Get-Config

$form = New-Object System.Windows.Forms.Form
$form.Text = 'OpenClaw Tunnel Control'
$form.Width = 420
$form.Height = 285
$form.StartPosition = 'CenterScreen'
$form.FormBorderStyle = 'FixedDialog'
$form.MaximizeBox = $false

$statusLabel = New-Object System.Windows.Forms.Label
$statusLabel.Left = 16
$statusLabel.Top = 16
$statusLabel.Width = 370
$statusLabel.Height = 20

$urlLabel = New-Object System.Windows.Forms.Label
$urlLabel.Left = 16
$urlLabel.Top = 38
$urlLabel.Width = 370
$urlLabel.Height = 20
$urlLabel.Text = "URL: $($config.ControlUrl)"

$autoLabel = New-Object System.Windows.Forms.Label
$autoLabel.Left = 16
$autoLabel.Top = 60
$autoLabel.Width = 370
$autoLabel.Height = 20

$startButton = New-Object System.Windows.Forms.Button
$startButton.Text = 'Start + Open'
$startButton.Left = 16
$startButton.Top = 95
$startButton.Width = 120

$stopButton = New-Object System.Windows.Forms.Button
$stopButton.Text = 'Stop Tunnel'
$stopButton.Left = 146
$stopButton.Top = 95
$stopButton.Width = 120

$openButton = New-Object System.Windows.Forms.Button
$openButton.Text = 'Open Control'
$openButton.Left = 276
$openButton.Top = 95
$openButton.Width = 120

$enableAutoButton = New-Object System.Windows.Forms.Button
$enableAutoButton.Text = 'Enable Auto Start'
$enableAutoButton.Left = 16
$enableAutoButton.Top = 130
$enableAutoButton.Width = 185

$disableAutoButton = New-Object System.Windows.Forms.Button
$disableAutoButton.Text = 'Disable Auto Start'
$disableAutoButton.Left = 211
$disableAutoButton.Top = 130
$disableAutoButton.Width = 185

$refreshButton = New-Object System.Windows.Forms.Button
$refreshButton.Text = 'Refresh'
$refreshButton.Left = 16
$refreshButton.Top = 165
$refreshButton.Width = 185

$exitButton = New-Object System.Windows.Forms.Button
$exitButton.Text = 'Close'
$exitButton.Left = 211
$exitButton.Top = 165
$exitButton.Width = 185

$outputBox = New-Object System.Windows.Forms.TextBox
$outputBox.Left = 16
$outputBox.Top = 200
$outputBox.Width = 380
$outputBox.Height = 40
$outputBox.ReadOnly = $true
$outputBox.Multiline = $true

function Refresh-Status {
  try {
    $status = Get-Status -Config $config
    $statusLabel.Text = "Tunnel: $($status.TunnelRunning) | Reachable: $($status.DashboardReachable)"
    $autoLabel.Text = "Auto Start: $($status.AutoStartEnabled)"
  }
  catch {
    $statusLabel.Text = 'Tunnel: unknown'
    $autoLabel.Text = 'Auto Start: unknown'
    $outputBox.Text = $_.Exception.Message
  }
}

$startButton.Add_Click({
  try {
    $r = Start-OpenClawTunnel -Config $config
    Open-ControlApp -Config $config
    $outputBox.Text = $r.Message
  }
  catch {
    $outputBox.Text = $_.Exception.Message
  }
  Refresh-Status
})

$stopButton.Add_Click({
  try {
    $r = Stop-OpenClawTunnel -Config $config
    $outputBox.Text = $r.Message
  }
  catch {
    $outputBox.Text = $_.Exception.Message
  }
  Refresh-Status
})

$openButton.Add_Click({
  try {
    Open-ControlApp -Config $config
    $outputBox.Text = 'Control app launch requested.'
  }
  catch {
    $outputBox.Text = $_.Exception.Message
  }
  Refresh-Status
})

$enableAutoButton.Add_Click({
  try {
    Enable-AutoStart -Config $config
    $outputBox.Text = 'Auto start enabled.'
  }
  catch {
    $outputBox.Text = $_.Exception.Message
  }
  Refresh-Status
})

$disableAutoButton.Add_Click({
  try {
    Disable-AutoStart -Config $config
    $outputBox.Text = 'Auto start disabled.'
  }
  catch {
    $outputBox.Text = $_.Exception.Message
  }
  Refresh-Status
})

$refreshButton.Add_Click({ Refresh-Status })
$exitButton.Add_Click({ $form.Close() })

$form.Controls.Add($statusLabel)
$form.Controls.Add($urlLabel)
$form.Controls.Add($autoLabel)
$form.Controls.Add($startButton)
$form.Controls.Add($stopButton)
$form.Controls.Add($openButton)
$form.Controls.Add($enableAutoButton)
$form.Controls.Add($disableAutoButton)
$form.Controls.Add($refreshButton)
$form.Controls.Add($exitButton)
$form.Controls.Add($outputBox)

Refresh-Status
[void]$form.ShowDialog()
