# windowsagent-teams — A tier

Control Microsoft Teams via WindowsAgent. Navigate channels, read messages via OCR, send messages, manage calls.

**Note:** New Teams (2023+) is a WebView2/Electron hybrid. The navigation sidebar has good UIA support. Message content is WebView2 — use OCR to read it. Sending uses clipboard paste.

## Core pattern

```powershell
$body = @{
    window  = "Microsoft Teams"
    action  = "key"
    element = "Microsoft Teams"
    params  = @{ keys = "ctrl,k" }
} | ConvertTo-Json -Compress

$result = curl.exe -s -X POST http://localhost:7862/act `
    -H "Content-Type: application/json" --data-binary $body | ConvertFrom-Json

if (-not $result.success) { Write-Warning "Act failed: $($result.error)" }
```

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
$body = @{ window = "Microsoft Teams" } | ConvertTo-Json -Compress
$obs = curl.exe -s -X POST http://localhost:7862/observe `
    -H "Content-Type: application/json" --data-binary $body | ConvertFrom-Json
$obs.uia_tree | ConvertTo-Json -Depth 4
$obs.ocr_results
```

---

## 2. Open Teams

```powershell
$body = @{ command = "ms-teams.exe" } | ConvertTo-Json -Compress
curl.exe -s -X POST http://localhost:7862/spawn -H "Content-Type: application/json" -d $body
Start-Sleep 5
```

---

## 3. Navigate to a channel or person (Ctrl+K)

`Ctrl+K` is the universal jump command — the most reliable entry point:

```powershell
function Open-TeamsChat {
    param([string]$name)

    # Ctrl+K — open Go To
    $body = @{ window="Microsoft Teams"; action="key"; element="Microsoft Teams"; params=@{keys="ctrl,k"} } | ConvertTo-Json -Compress
    curl.exe -s -X POST http://localhost:7862/act -H "Content-Type: application/json" --data-binary $body | Out-Null
    Start-Sleep 0.5

    # Type name (observe to get input element name if this fails)
    $body = @{ window="Microsoft Teams"; action="type"; element="Find a channel, name, or file"; params=@{text=$name} } | ConvertTo-Json -Compress
    $r = curl.exe -s -X POST http://localhost:7862/act -H "Content-Type: application/json" --data-binary $body | ConvertFrom-Json

    if (-not $r.success) {
        # Element name may differ — observe and retry
        Write-Warning "Type failed. Observe Teams to find the correct input element name."
        return
    }
    Start-Sleep 0.8

    # Select first result
    $body = @{ window="Microsoft Teams"; action="key"; element="Find a channel, name, or file"; params=@{keys="enter"} } | ConvertTo-Json -Compress
    curl.exe -s -X POST http://localhost:7862/act -H "Content-Type: application/json" --data-binary $body | Out-Null
    Start-Sleep 1
}

Open-TeamsChat "General"
Open-TeamsChat "John Smith"  # direct message
```

---

## 4. Read current messages (OCR)

```powershell
function Read-TeamsMessages {
    $body = @{ window = "Microsoft Teams" } | ConvertTo-Json -Compress
    $obs = curl.exe -s -X POST http://localhost:7862/observe `
        -H "Content-Type: application/json" --data-binary $body | ConvertFrom-Json
    return $obs.ocr_results
}

Read-TeamsMessages
```

To see older messages, scroll up first:

```powershell
$body = @{ window="Microsoft Teams"; action="scroll"; element="Microsoft Teams"; params=@{direction="up"; amount=5} } | ConvertTo-Json -Compress
curl.exe -s -X POST http://localhost:7862/act -H "Content-Type: application/json" --data-binary $body | Out-Null
Start-Sleep 0.5
Read-TeamsMessages
```

---

## 5. Send a message

**Always confirm with the user before sending. Never auto-send.**

```powershell
function Send-TeamsMessage {
    param([string]$chat, [string]$message)

    # Navigate to chat
    Open-TeamsChat $chat
    Start-Sleep 1

    # Write to clipboard (safe method)
    $message | Out-File -Encoding utf8 "%TEMP%\wa-teams-msg.txt" -NoNewline
    $body = @{ command = "Get-Content '%TEMP%\wa-teams-msg.txt' -Raw | Set-Clipboard" } | ConvertTo-Json -Compress
    curl.exe -s -X POST http://localhost:7862/shell -H "Content-Type: application/json" -d $body | Out-Null
    Start-Sleep 0.2

    # Click message compose box
    $body = @{ window="Microsoft Teams"; action="click"; element="Type a new message" } | ConvertTo-Json -Compress
    $r = curl.exe -s -X POST http://localhost:7862/act -H "Content-Type: application/json" --data-binary $body | ConvertFrom-Json

    if (-not $r.success) {
        Write-Warning "Could not find compose box. Observe Teams to get correct element name."
        return
    }
    Start-Sleep 0.2

    # Paste
    $body = @{ window="Microsoft Teams"; action="key"; element="Type a new message"; params=@{keys="ctrl,v"} } | ConvertTo-Json -Compress
    curl.exe -s -X POST http://localhost:7862/act -H "Content-Type: application/json" --data-binary $body | Out-Null

    Write-Host "Message ready in compose box for '$chat'. Review and press Enter to send."
}

# Usage — message is staged, NOT sent automatically:
Send-TeamsMessage -chat "General" -message "Just pushed the fix"
```

---

## 6. In-call controls

```powershell
function Set-TeamsMute {
    param([bool]$muted)
    # Ctrl+Shift+M toggles mute
    $body = @{ window="Microsoft Teams"; action="key"; element="Microsoft Teams"; params=@{keys="ctrl,shift,m"} } | ConvertTo-Json -Compress
    curl.exe -s -X POST http://localhost:7862/act -H "Content-Type: application/json" --data-binary $body | Out-Null
}

function Set-TeamsCamera {
    # Ctrl+Shift+O toggles camera
    $body = @{ window="Microsoft Teams"; action="key"; element="Microsoft Teams"; params=@{keys="ctrl,shift,o"} } | ConvertTo-Json -Compress
    curl.exe -s -X POST http://localhost:7862/act -H "Content-Type: application/json" --data-binary $body | Out-Null
}

function Leave-TeamsCall {
    $body = @{ window="Microsoft Teams"; action="key"; element="Microsoft Teams"; params=@{keys="ctrl,shift,h"} } | ConvertTo-Json -Compress
    curl.exe -s -X POST http://localhost:7862/act -H "Content-Type: application/json" --data-binary $body | Out-Null
}
```

---

## 7. Keyboard shortcuts reference

| Action | Keys |
|--------|------|
| Go to / search | `ctrl,k` |
| New chat | `ctrl,n` |
| Activity | `ctrl,1` |
| Chat | `ctrl,2` |
| Teams | `ctrl,3` |
| Calendar | `ctrl,4` |
| Toggle mute | `ctrl,shift,m` |
| Toggle camera | `ctrl,shift,o` |
| Raise hand | `ctrl,shift,k` |
| End call | `ctrl,shift,h` |
| Accept call | `ctrl,shift,a` |
| Decline call | `ctrl,shift,d` |

---

## Notes

- `Ctrl+K` is the most reliable navigation. If element names differ between Teams versions, Ctrl+K still works.
- The compose box element name may vary. If `"Type a new message"` fails, run `observe` to find the current name.
- For calendar/meeting data, consider using a dedicated calendar API — faster and more structured than navigating the Teams UI.
- Teams notifications appear as Windows toasts — WindowsAgent can dismiss them via UIA if they block work.
