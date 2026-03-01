# OpenClaw Tunnel Control (Windows + WSL)

Tiny local control app for OpenClaw secure loopback access.

## What it does
- Start/stop SSH tunnel: `127.0.0.1:18789` (Windows) -> `127.0.0.1:18789` (WSL)
- Launch OpenClaw Control web app
- Enable/disable auto-start (Scheduled Task)

## Files
- `OpenClawTunnelApp.ps1` - small GUI app
- `OpenClawTunnelCli.ps1` - CLI actions
- `OpenClawTunnel.psm1` - shared logic
- `Launch-OpenClawTunnelApp.cmd` - double-click launcher
- `config.json` - generated on first run

## Quick start
1. Double-click `Launch-OpenClawTunnelApp.cmd`
2. Click **Start + Open**

## CLI
```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\openclaw-tunnel-control\OpenClawTunnelCli.ps1 -Action Status
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\openclaw-tunnel-control\OpenClawTunnelCli.ps1 -Action Start
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\openclaw-tunnel-control\OpenClawTunnelCli.ps1 -Action Open
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\openclaw-tunnel-control\OpenClawTunnelCli.ps1 -Action Stop
```

## Auto start
Use GUI buttons **Enable Auto Start** / **Disable Auto Start**, or:
```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\openclaw-tunnel-control\OpenClawTunnelCli.ps1 -Action EnableAutoStart
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\openclaw-tunnel-control\OpenClawTunnelCli.ps1 -Action DisableAutoStart
```

## Notes
- Keeps OpenClaw in loopback mode (not LAN-exposed).
- Tunnel target IP is resolved from WSL each time Start is clicked.
- If installed web app is not picked up, the URL opens in browser.
