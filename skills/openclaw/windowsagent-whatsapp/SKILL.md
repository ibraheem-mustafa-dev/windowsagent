# windowsagent-whatsapp — A tier

Interact with WhatsApp Web via WindowsAgent. Read messages via OCR, compose messages via clipboard paste.

This skill is for reading what's on screen in WhatsApp Web and for assisted compose when you need to interact with the UI directly.

**Hard rule: Never send a WhatsApp message without the user's explicit confirmation.**

## Core pattern

```powershell
$body = @{
    window  = "WhatsApp"
    action  = "key"
    element = "WhatsApp"
    params  = @{ keys = "ctrl,f" }
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

## 2. Open WhatsApp Web

```powershell
$body = @{ command = "msedge.exe `"https://web.whatsapp.com`"" } | ConvertTo-Json -Compress
curl.exe -s -X POST http://localhost:7862/spawn -H "Content-Type: application/json" -d $body
Start-Sleep 5
# If QR code shows — scan with phone. Multi-device mode must be enabled.
```

---

## 3. Read what's visible (OCR)

```powershell
function Read-WhatsAppScreen {
    $body = @{ window = "WhatsApp" } | ConvertTo-Json -Compress
    $obs = curl.exe -s -X POST http://localhost:7862/observe `
        -H "Content-Type: application/json" --data-binary $body | ConvertFrom-Json
    return $obs.ocr_results
}

Read-WhatsAppScreen
```

Scroll through messages:

```powershell
$body = @{ window="WhatsApp"; action="scroll"; element="WhatsApp"; params=@{direction="up"; amount=5} } | ConvertTo-Json -Compress
curl.exe -s -X POST http://localhost:7862/act -H "Content-Type: application/json" --data-binary $body | Out-Null
Start-Sleep 0.5
Read-WhatsAppScreen
```

---

## 4. Open a chat

```powershell
function Open-WhatsAppChat {
    param([string]$contactName)

    # Ctrl+F = search
    $body = @{ window="WhatsApp"; action="key"; element="WhatsApp"; params=@{keys="ctrl,f"} } | ConvertTo-Json -Compress
    curl.exe -s -X POST http://localhost:7862/act -H "Content-Type: application/json" --data-binary $body | Out-Null
    Start-Sleep 0.5

    # Type contact name
    $body = @{ window="WhatsApp"; action="type"; element="Search or start new chat"; params=@{text=$contactName} } | ConvertTo-Json -Compress
    $r = curl.exe -s -X POST http://localhost:7862/act -H "Content-Type: application/json" --data-binary $body | ConvertFrom-Json

    if (-not $r.success) {
        # Try alternate element name
        $body = @{ window="WhatsApp"; action="type"; element="Search"; params=@{text=$contactName} } | ConvertTo-Json -Compress
        curl.exe -s -X POST http://localhost:7862/act -H "Content-Type: application/json" --data-binary $body | Out-Null
    }
    Start-Sleep 1

    # Enter to open first result
    $body = @{ window="WhatsApp"; action="key"; element="WhatsApp"; params=@{keys="enter"} } | ConvertTo-Json -Compress
    curl.exe -s -X POST http://localhost:7862/act -H "Content-Type: application/json" --data-binary $body | Out-Null
    Start-Sleep 0.5
}

Open-WhatsAppChat "Contact Name"
```

---

## 5. Stage a message for review (does NOT send)

```powershell
function Stage-WhatsAppMessage {
    param([string]$contactName, [string]$message)

    # Open chat
    Open-WhatsAppChat $contactName
    Start-Sleep 0.5

    # Write to clipboard safely (handles quotes, Unicode, newlines)
    $message | Out-File -Encoding utf8 "%TEMP%\wa-msg.txt" -NoNewline
    $body = @{ command = "Get-Content '%TEMP%\wa-msg.txt' -Raw | Set-Clipboard" } | ConvertTo-Json -Compress
    curl.exe -s -X POST http://localhost:7862/shell -H "Content-Type: application/json" -d $body | Out-Null
    Start-Sleep 0.2

    # Click message input
    $body = @{ window="WhatsApp"; action="click"; element="Type a message" } | ConvertTo-Json -Compress
    $r = curl.exe -s -X POST http://localhost:7862/act -H "Content-Type: application/json" --data-binary $body | ConvertFrom-Json

    if (-not $r.success) {
        Write-Warning "Message input not found. Run observe on WhatsApp to check element name."
        return
    }
    Start-Sleep 0.2

    # Paste
    $body = @{ window="WhatsApp"; action="key"; element="Type a message"; params=@{keys="ctrl,v"} } | ConvertTo-Json -Compress
    curl.exe -s -X POST http://localhost:7862/act -H "Content-Type: application/json" --data-binary $body | Out-Null

    Write-Host ""
    Write-Host "MESSAGE STAGED — NOT SENT"
    Write-Host "Chat: $contactName"
    Write-Host "Text: $message"
    Write-Host ""
    Write-Host "Review the message in WhatsApp Web, then press Enter to send."
}

function Send-Staged {
    # Only call this after the user has explicitly approved
    $body = @{ window="WhatsApp"; action="key"; element="Type a message"; params=@{keys="enter"} } | ConvertTo-Json -Compress
    curl.exe -s -X POST http://localhost:7862/act -H "Content-Type: application/json" --data-binary $body | Out-Null
    Write-Host "Sent."
}

# Usage:
Stage-WhatsAppMessage -contactName "Contact Name" -message "On my way, 20 mins"
# User reviews, then calls: Send-Staged
```

---

## Notes

- WhatsApp Web element names vary slightly between versions. If `"Search or start new chat"` fails, run observe and check.
- Arabic/RTL text: use the clipboard paste method — the type action drops RTL characters.
- Multi-device mode must be enabled on phone: Settings > Linked Devices.
