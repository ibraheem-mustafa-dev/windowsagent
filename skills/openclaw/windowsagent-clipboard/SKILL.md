# windowsagent-clipboard — S tier

Read and write the Windows clipboard via WindowsAgent's `/shell` endpoint. The most reliable way to get text in and out of any app — use it whenever `type` drops characters or fails.

## Step 0 — Health check

```powershell
$health = curl.exe -s http://localhost:7862/health | ConvertFrom-Json
if ($health.status -ne "ok") {
    Start-ScheduledTask -TaskName "WindowsAgent Server"
    Start-Sleep 4
}
```

---

## 1. Read clipboard

```powershell
$body = @{ command = "Get-Clipboard" } | ConvertTo-Json -Compress
$result = curl.exe -s -X POST http://localhost:7862/shell `
    -H "Content-Type: application/json" -d $body | ConvertFrom-Json
$result.stdout.Trim()
```

---

## 2. Write text to clipboard (safe — handles all special chars)

The safe pattern writes content to a temp file first, then loads it. This avoids all quoting and escaping issues:

```powershell
function Set-WAClipboard {
    param([string]$text)

    # Write to temp file first — avoids quote/newline escaping in the command string
    $text | Out-File -Encoding utf8 -FilePath "%TEMP%\wa-clipboard.txt" -NoNewline

    $body = @{
        command = "Get-Content '%TEMP%\wa-clipboard.txt' -Raw | Set-Clipboard"
    } | ConvertTo-Json -Compress

    $result = curl.exe -s -X POST http://localhost:7862/shell `
        -H "Content-Type: application/json" -d $body | ConvertFrom-Json

    if ($result.returncode -ne 0) {
        Write-Warning "Clipboard write failed: $($result.stderr)"
    }
}

# Usage — handles quotes, newlines, special chars, Unicode:
Set-WAClipboard "Hello — with 'quotes' and newlines"
Set-WAClipboard @"
Dear Colleague,

Thank you for your message.
Best regards
"@
```

---

## 3. Paste clipboard into a window element

```powershell
function Invoke-WAPaste {
    param([string]$window, [string]$element)

    # Focus element
    $body = @{ window=$window; action="click"; element=$element } | ConvertTo-Json -Compress
    curl.exe -s -X POST http://localhost:7862/act -H "Content-Type: application/json" --data-binary $body | Out-Null
    Start-Sleep 0.2

    # Paste
    $body = @{ window=$window; action="key"; element=$element; params=@{keys="ctrl,v"} } | ConvertTo-Json -Compress
    $result = curl.exe -s -X POST http://localhost:7862/act `
        -H "Content-Type: application/json" --data-binary $body | ConvertFrom-Json

    if (-not $result.success) { Write-Warning "Paste failed: $($result.error)" }
    return $result
}

# Usage:
Invoke-WAPaste -window "Notepad" -element "Text Editor"
Invoke-WAPaste -window "Microsoft Edge" -element "Type a message"  # WhatsApp Web
```

---

## 4. Full write-and-paste workflow (one call)

```powershell
function Write-AndPaste {
    param([string]$window, [string]$element, [string]$text)

    Set-WAClipboard $text
    Start-Sleep 0.2
    Invoke-WAPaste -window $window -element $element
}

# Examples:
Write-AndPaste -window "Notepad" -element "Text Editor" -text "Long text with 'quotes' and special chars"
Write-AndPaste -window "Microsoft Teams" -element "Type a new message" -text "On my way, 5 mins"
Write-AndPaste -window "WhatsApp" -element "Type a message" -text "Thank you"
```

---

## 5. Extract text from an app via copy

```powershell
function Get-AppText {
    param([string]$window, [string]$element)

    # Select all and copy
    $body = @{ window=$window; action="key"; element=$element; params=@{keys="ctrl,a"} } | ConvertTo-Json -Compress
    curl.exe -s -X POST http://localhost:7862/act -H "Content-Type: application/json" --data-binary $body | Out-Null
    Start-Sleep 0.1

    $body = @{ window=$window; action="key"; element=$element; params=@{keys="ctrl,c"} } | ConvertTo-Json -Compress
    curl.exe -s -X POST http://localhost:7862/act -H "Content-Type: application/json" --data-binary $body | Out-Null
    Start-Sleep 0.2

    # Read clipboard
    $body = @{ command = "Get-Clipboard" } | ConvertTo-Json -Compress
    $result = curl.exe -s -X POST http://localhost:7862/shell `
        -H "Content-Type: application/json" -d $body | ConvertFrom-Json
    return $result.stdout
}

# Get all text from Notepad:
Get-AppText -window "Notepad" -element "Text Editor"
```

---

## 6. Windows Terminal paste (different shortcut)

Windows Terminal uses `Ctrl+Shift+V` not `Ctrl+V`:

```powershell
function Invoke-TerminalPaste {
    param([string]$window = "Windows PowerShell")

    $body = @{ window=$window; action="key"; element="Terminal"; params=@{keys="ctrl,shift,v"} } | ConvertTo-Json -Compress
    curl.exe -s -X POST http://localhost:7862/act -H "Content-Type: application/json" --data-binary $body | Out-Null
}
```

---

## When to use clipboard vs `type`

| Scenario | Use |
|----------|-----|
| Short ASCII text, simple app | `type` action |
| Long text (>50 chars) | Clipboard paste |
| Text with quotes, special chars | Clipboard paste |
| WinUI3 apps (new Notepad, modern Office) | Clipboard paste |
| Electron/WebView2 apps | Clipboard paste |
| Copy something from an app | Clipboard read |
| Text with newlines | Clipboard paste |
| Non-Latin characters (Arabic, emoji) | Clipboard paste |
