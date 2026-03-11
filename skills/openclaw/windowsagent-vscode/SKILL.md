# windowsagent-vscode — S tier

Control VS Code via WindowsAgent. Open projects, switch files, run terminal, launch Claude Code.

## Core pattern

```powershell
$body = @{
    window  = "Visual Studio Code"
    action  = "key"
    element = "workbench"
    params  = @{ keys = "ctrl,p" }
} | ConvertTo-Json -Compress

$result = curl.exe -s -X POST http://localhost:7862/act `
    -H "Content-Type: application/json" --data-binary $body | ConvertFrom-Json

if (-not $result.success) { Write-Warning "Act failed: $($result.error)" }
```

**Note on Ctrl+\` (toggle terminal):** The backtick is PowerShell's escape character. Use `"ctrl,oem_3"` or send the key as a raw keycode — or use `/shell` directly instead (preferred).

---

## Step 0 — Health check

```powershell
$health = curl.exe -s http://localhost:7862/health | ConvertFrom-Json
if ($health.status -ne "ok") {
    Start-ScheduledTask -TaskName "WindowsAgent Server"
    Start-Sleep 4
}
```

---

## Step 1 — Discover element names

```powershell
$body = @{ window = "Visual Studio Code" } | ConvertTo-Json -Compress
$obs = curl.exe -s -X POST http://localhost:7862/observe `
    -H "Content-Type: application/json" --data-binary $body | ConvertFrom-Json
$obs.uia_tree | ConvertTo-Json -Depth 4
```

**Known VS Code UIA element names (verified):**
| Area | UIA Name |
|------|----------|
| Editor area | `"editor content"` or file name |
| Explorer sidebar | `"Explorer"` |
| Search sidebar | `"Search"` |
| Quick Open input | `"input"` (when open) |
| Terminal | `"Terminal"` |
| Status bar | `"workbench.parts.statusbar"` |

---

## 2. Open VS Code in a project

```powershell
$project = "%USERPROFILE%\projects\my-project"
$body = @{ command = "code `"$project`"" } | ConvertTo-Json -Compress
curl.exe -s -X POST http://localhost:7862/spawn -H "Content-Type: application/json" -d $body
Start-Sleep 3
```

VS Code should open with the project folder. Window title becomes `my-project - Visual Studio Code`.

---

## 3. Open a file (Quick Open — Ctrl+P)

```powershell
function Open-VSCodeFile {
    param([string]$filename)

    # Open Quick Open palette
    $body = @{ window="Visual Studio Code"; action="key"; element="workbench"; params=@{keys="ctrl,p"} } | ConvertTo-Json -Compress
    curl.exe -s -X POST http://localhost:7862/act -H "Content-Type: application/json" --data-binary $body | Out-Null
    Start-Sleep 0.4

    # Type filename
    $body = @{ window="Visual Studio Code"; action="type"; element="input"; params=@{text=$filename} } | ConvertTo-Json -Compress
    curl.exe -s -X POST http://localhost:7862/act -H "Content-Type: application/json" --data-binary $body | Out-Null
    Start-Sleep 0.5

    # Select first result
    $body = @{ window="Visual Studio Code"; action="key"; element="input"; params=@{keys="enter"} } | ConvertTo-Json -Compress
    curl.exe -s -X POST http://localhost:7862/act -H "Content-Type: application/json" --data-binary $body | Out-Null
}

Open-VSCodeFile "server.py"
```

---

## 4. Run a terminal command (via /shell — preferred)

For running commands and getting output back, skip VS Code UI entirely:

```powershell
function Invoke-ProjectCommand {
    param([string]$project, [string]$command, [int]$timeout = 60)

    $body = @{
        command = "cd `"$project`"; $command"
        shell   = "pwsh"
        cwd     = $project
        timeout = $timeout
    } | ConvertTo-Json -Compress

    $result = curl.exe -s -X POST http://localhost:7862/shell `
        -H "Content-Type: application/json" -d $body | ConvertFrom-Json

    Write-Host $result.stdout
    if ($result.stderr) { Write-Warning $result.stderr }
    return $result
}

# Examples:
Invoke-ProjectCommand "%USERPROFILE%\projects\my-project" "git status"
Invoke-ProjectCommand "%USERPROFILE%\projects\my-app" "npm run build" -timeout 120
```

---

## 5. Open terminal inside VS Code (UIA)

When you need to interact with a running process in the VS Code terminal specifically:

```powershell
# Ctrl+Shift+` = new terminal (use oem_3 to avoid backtick escaping)
$body = @{ window="Visual Studio Code"; action="key"; element="workbench"; params=@{keys="ctrl,shift,oem_3"} } | ConvertTo-Json -Compress
curl.exe -s -X POST http://localhost:7862/act -H "Content-Type: application/json" --data-binary $body | Out-Null
Start-Sleep 0.8

# Type and run a command
$command = "npm run dev"
$body = @{ window="Visual Studio Code"; action="type"; element="Terminal"; params=@{text=$command} } | ConvertTo-Json -Compress
curl.exe -s -X POST http://localhost:7862/act -H "Content-Type: application/json" --data-binary $body | Out-Null

$body = @{ window="Visual Studio Code"; action="key"; element="Terminal"; params=@{keys="enter"} } | ConvertTo-Json -Compress
curl.exe -s -X POST http://localhost:7862/act -H "Content-Type: application/json" --data-binary $body | Out-Null
```

---

## 6. Run a one-shot Claude Code task in a project

```powershell
function Invoke-ClaudeCode {
    param([string]$project, [string]$prompt, [int]$timeout = 120)

    $escaped = $prompt -replace '"', '\"'
    $body = @{
        command = "cd `"$project`"; claude --print --permission-mode bypassPermissions `"$escaped`""
        shell   = "pwsh"
        cwd     = $project
        timeout = $timeout
    } | ConvertTo-Json -Compress

    $result = curl.exe -s -X POST http://localhost:7862/shell `
        -H "Content-Type: application/json" -d $body | ConvertFrom-Json

    return $result.stdout
}

# Examples:
Invoke-ClaudeCode "%USERPROFILE%\projects\my-project" "Review server.py for bugs"
Invoke-ClaudeCode "%USERPROFILE%\projects\my-app" "What does the payment flow do?" -timeout 60
```

---

## 7. Command Palette (Ctrl+Shift+P)

```powershell
function Invoke-VSCodeCommand {
    param([string]$commandName)

    $body = @{ window="Visual Studio Code"; action="key"; element="workbench"; params=@{keys="ctrl,shift,p"} } | ConvertTo-Json -Compress
    curl.exe -s -X POST http://localhost:7862/act -H "Content-Type: application/json" --data-binary $body | Out-Null
    Start-Sleep 0.4

    $body = @{ window="Visual Studio Code"; action="type"; element="input"; params=@{text=$commandName} } | ConvertTo-Json -Compress
    curl.exe -s -X POST http://localhost:7862/act -H "Content-Type: application/json" --data-binary $body | Out-Null
    Start-Sleep 0.4

    $body = @{ window="Visual Studio Code"; action="key"; element="input"; params=@{keys="enter"} } | ConvertTo-Json -Compress
    curl.exe -s -X POST http://localhost:7862/act -H "Content-Type: application/json" --data-binary $body | Out-Null
}

Invoke-VSCodeCommand "Git: Stage All Changes"
Invoke-VSCodeCommand "Format Document"
Invoke-VSCodeCommand "Toggle Word Wrap"
```

---

## 8. Keyboard shortcuts reference

| Action | Keys |
|--------|------|
| Quick Open (file) | `ctrl,p` |
| Command Palette | `ctrl,shift,p` |
| New terminal | `ctrl,shift,oem_3` |
| Toggle sidebar | `ctrl,b` |
| Go to line | `ctrl,g` |
| Find in file | `ctrl,f` |
| Find in project | `ctrl,shift,f` |
| Save | `ctrl,s` |
| Save all | `ctrl,k ctrl,s` |
| Format document | `shift,alt,f` |
| Close tab | `ctrl,w` |
| Split editor | `ctrl,backslash` |
| Zen mode | `ctrl,k z` |
| Toggle minimap | via Command Palette |

---

## When VS Code UIA fails

1. Use `/shell` + `Invoke-ProjectCommand` for terminal commands — always works
2. Use Claude Code `--print` for code analysis — always works
3. UIA element missing? — run `observe` and check `uia_tree` for current names
4. VS Code may rename elements between versions — re-verify after updates
