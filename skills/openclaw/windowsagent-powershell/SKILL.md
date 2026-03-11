# windowsagent-powershell

Open, control, and read output from PowerShell and Windows Terminal via WindowsAgent.

**Primary rule:** For running commands and getting output back, always use `/shell` directly — it runs in the user's session and returns stdout/stderr as JSON. Use UIA terminal control only when you need to interact with an already-open interactive session (e.g., a running dev server).

## Prerequisites

```powershell
curl.exe -s http://localhost:7862/health
# If down: Start-ScheduledTask -TaskName "WindowsAgent Server"; Start-Sleep 4
```

---

## 1. Run a command and get output (preferred)

```powershell
$body = '{"command": "Get-ChildItem %USERPROFILE%\\projects -Directory | Select-Object Name"}'
$result = curl.exe -s -X POST http://localhost:7862/shell -H "Content-Type: application/json" -d $body
($result | ConvertFrom-Json).stdout
```

Shell options: `pwsh` (PS7, default), `powershell` (PS5), `cmd`.

```powershell
$body = '{"command": "dir /b %USERPROFILE%\\projects", "shell": "cmd"}'
$result = curl.exe -s -X POST http://localhost:7862/shell -H "Content-Type: application/json" -d $body
($result | ConvertFrom-Json).stdout
```

---

## 2. Open a new PowerShell terminal window

```powershell
# Windows Terminal with PS7
$body = '{"command": "wt.exe pwsh"}'
curl.exe -s -X POST http://localhost:7862/spawn -H "Content-Type: application/json" -d $body

# Windows Terminal in a specific directory
$body = '{"command": "wt.exe -d %USERPROFILE%\\projects\\my-project pwsh"}'
curl.exe -s -X POST http://localhost:7862/spawn -H "Content-Type: application/json" -d $body
```

---

## 3. Open terminal and run a command

```powershell
# Start Windows Terminal, run a command, leave it open
$project = "%USERPROFILE%\projects\my-app"
$cmd = "npm run dev"
$body = "{`"command`": `"wt.exe -d '$project' pwsh -NoExit -Command '$cmd'`"}"
curl.exe -s -X POST http://localhost:7862/spawn -H "Content-Type: application/json" -d $body
```

---

## 4. Send a command to an open PowerShell window

If a terminal is already open and you need to send input (e.g., answer a prompt, restart a dev server):

```powershell
# Write to clipboard
$body = '{"command": "Set-Clipboard -Value \"npm run dev\""}'
curl.exe -s -X POST http://localhost:7862/shell -H "Content-Type: application/json" -d $body
Start-Sleep 0.2

# Paste into terminal (Windows Terminal uses Ctrl+Shift+V)
$body = '{"window": "Windows PowerShell", "action": "key", "element": "Terminal", "params": {"keys": "ctrl,shift,v"}}'
curl.exe -s -X POST http://localhost:7862/act -H "Content-Type: application/json" --data-binary $body
Start-Sleep 0.2

$body = '{"window": "Windows PowerShell", "action": "key", "element": "Terminal", "params": {"keys": "enter"}}'
curl.exe -s -X POST http://localhost:7862/act -H "Content-Type: application/json" --data-binary $body
```

---

## 5. Read terminal output via OCR

When a dev server is running and you want to check its output:

```powershell
$body = '{"window": "Windows PowerShell"}'
$result = curl.exe -s -X POST http://localhost:7862/observe -H "Content-Type: application/json" --data-binary $body
($result | ConvertFrom-Json).ocr_results
```

---

## 6. Run a long-running command (background)

```powershell
# Start a process in background, check if it's running
$body = '{"command": "Start-Process pwsh -ArgumentList \"-NoExit\", \"-Command\", \"npm run dev\" -WorkingDirectory %USERPROFILE%\\projects\\my-app"}'
curl.exe -s -X POST http://localhost:7862/shell -H "Content-Type: application/json" -d $body

# Check if it started
$body = '{"command": "Get-Process node -ErrorAction SilentlyContinue | Select-Object Id, CPU, WorkingSet"}'
$result = curl.exe -s -X POST http://localhost:7862/shell -H "Content-Type: application/json" -d $body
($result | ConvertFrom-Json).stdout
```

---

## 7. Kill a process by name or port

```powershell
# Kill by name
$body = '{"command": "Stop-Process -Name node -Force"}'
curl.exe -s -X POST http://localhost:7862/shell -H "Content-Type: application/json" -d $body

# Kill process on a specific port
$body = '{"command": "$pid = (netstat -ano | Select-String \":3000\").ToString().Split()[-1]; if ($pid) { Stop-Process -Id $pid -Force; \"Killed $pid\" } else { \"Nothing on port 3000\" }"}'
$result = curl.exe -s -X POST http://localhost:7862/shell -H "Content-Type: application/json" -d $body
($result | ConvertFrom-Json).stdout
```

---

## Common One-Liners

```powershell
# Check what's on a port
'{"command": "netstat -ano | Select-String \":7862\""}'

# Check disk space
'{"command": "Get-PSDrive C | Select-Object Used, Free"}'

# Check running services
'{"command": "Get-Service | Where-Object {$_.Status -eq \"Running\"} | Select-Object Name, DisplayName"}'

# Tail a log file
'{"command": "Get-Content C:\\Temp\\app.log -Tail 20"}'

# Check environment variable
'{"command": "$env:ANTHROPIC_API_KEY"}'
```

---

## Notes

- `/shell` runs PowerShell 7 (`pwsh`) by default. Switch to `"shell": "powershell"` for PS5 if a module requires it.
- Default timeout is 30s. Set `"timeout": 120` for long-running commands.
- Never pipe huge output through `/shell` — truncate with `Select-Object -First 100` or write to a file.
- Windows Terminal paste shortcut is `Ctrl+Shift+V` (not `Ctrl+V`).
