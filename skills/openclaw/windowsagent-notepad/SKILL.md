# windowsagent-notepad — S tier

Control Windows Notepad via WindowsAgent. Open, type, read, save, and clear text. WindowsAgent's primary test target — the most reliable app profile.

**Key element:** The main text area is called `"Text Editor"` (Document control type in UIA).

## Core pattern

```powershell
$body = @{
    window  = "Notepad"
    action  = "type"
    element = "Text Editor"
    params  = @{ text = "Hello, World!" }
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

## 1. Open Notepad

```powershell
$body = @{ command = "notepad.exe" } | ConvertTo-Json -Compress
curl.exe -s -X POST http://localhost:7862/spawn -H "Content-Type: application/json" -d $body
Start-Sleep 1
```

Open a specific file:

```powershell
$body = @{ command = "notepad.exe 'C:\Temp\notes.txt'" } | ConvertTo-Json -Compress
curl.exe -s -X POST http://localhost:7862/spawn -H "Content-Type: application/json" -d $body
Start-Sleep 1
```

---

## 2. Type text

For short ASCII text, use `type` directly:

```powershell
$body = @{
    window  = "Notepad"
    action  = "type"
    element = "Text Editor"
    params  = @{ text = "Hello, World!" }
} | ConvertTo-Json -Compress
curl.exe -s -X POST http://localhost:7862/act -H "Content-Type: application/json" --data-binary $body | Out-Null
```

For long text, special characters, or Unicode — use clipboard paste (more reliable in WinUI3 Notepad):

```powershell
function Write-ToNotepad {
    param([string]$text)

    $text | Out-File -Encoding utf8 -FilePath "%TEMP%\wa-notepad.txt" -NoNewline
    $body = @{ command = "Get-Content '%TEMP%\wa-notepad.txt' -Raw | Set-Clipboard" } | ConvertTo-Json -Compress
    curl.exe -s -X POST http://localhost:7862/shell -H "Content-Type: application/json" -d $body | Out-Null
    Start-Sleep 0.2

    # Click to focus
    $body = @{ window="Notepad"; action="click"; element="Text Editor" } | ConvertTo-Json -Compress
    curl.exe -s -X POST http://localhost:7862/act -H "Content-Type: application/json" --data-binary $body | Out-Null
    Start-Sleep 0.1

    # Paste
    $body = @{ window="Notepad"; action="key"; element="Text Editor"; params=@{keys="ctrl,v"} } | ConvertTo-Json -Compress
    curl.exe -s -X POST http://localhost:7862/act -H "Content-Type: application/json" --data-binary $body | Out-Null
}

Write-ToNotepad "Long text with 'quotes', special chars, and Unicode: ñ, ü, 日本語"
```

---

## 3. Read text from Notepad

```powershell
function Read-Notepad {
    # Select all and copy
    $body = @{ window="Notepad"; action="key"; element="Text Editor"; params=@{keys="ctrl,a"} } | ConvertTo-Json -Compress
    curl.exe -s -X POST http://localhost:7862/act -H "Content-Type: application/json" --data-binary $body | Out-Null
    Start-Sleep 0.1

    $body = @{ window="Notepad"; action="key"; element="Text Editor"; params=@{keys="ctrl,c"} } | ConvertTo-Json -Compress
    curl.exe -s -X POST http://localhost:7862/act -H "Content-Type: application/json" --data-binary $body | Out-Null
    Start-Sleep 0.2

    # Read clipboard
    $body = @{ command = "Get-Clipboard" } | ConvertTo-Json -Compress
    $result = curl.exe -s -X POST http://localhost:7862/shell `
        -H "Content-Type: application/json" -d $body | ConvertFrom-Json
    return $result.stdout
}

$text = Read-Notepad
Write-Host $text
```

Alternative — use OCR (no clipboard side-effects):

```powershell
$body = @{ window = "Notepad" } | ConvertTo-Json -Compress
$obs = curl.exe -s -X POST http://localhost:7862/observe `
    -H "Content-Type: application/json" --data-binary $body | ConvertFrom-Json
$obs.ocr_results
```

---

## 4. Save the file (Ctrl+S)

```powershell
# Save (if file already has a name)
$body = @{ window="Notepad"; action="key"; element="Text Editor"; params=@{keys="ctrl,s"} } | ConvertTo-Json -Compress
curl.exe -s -X POST http://localhost:7862/act -H "Content-Type: application/json" --data-binary $body | Out-Null
```

Save As (new file):

```powershell
# Ctrl+Shift+S triggers Save As dialog
$body = @{ window="Notepad"; action="key"; element="Text Editor"; params=@{keys="ctrl,shift,s"} } | ConvertTo-Json -Compress
curl.exe -s -X POST http://localhost:7862/act -H "Content-Type: application/json" --data-binary $body | Out-Null
Start-Sleep 1

# Type filename in Save As dialog
$body = @{ window="Save As"; action="type"; element="File name:"; params=@{text="C:\Temp\output.txt"} } | ConvertTo-Json -Compress
curl.exe -s -X POST http://localhost:7862/act -H "Content-Type: application/json" --data-binary $body | Out-Null
Start-Sleep 0.2

# Click Save
$body = @{ window="Save As"; action="click"; element="Save" } | ConvertTo-Json -Compress
curl.exe -s -X POST http://localhost:7862/act -H "Content-Type: application/json" --data-binary $body | Out-Null
```

---

## 5. Clear all text

```powershell
function Clear-Notepad {
    # Select all, then delete
    $body = @{ window="Notepad"; action="key"; element="Text Editor"; params=@{keys="ctrl,a"} } | ConvertTo-Json -Compress
    curl.exe -s -X POST http://localhost:7862/act -H "Content-Type: application/json" --data-binary $body | Out-Null
    Start-Sleep 0.1

    $body = @{ window="Notepad"; action="key"; element="Text Editor"; params=@{keys="delete"} } | ConvertTo-Json -Compress
    curl.exe -s -X POST http://localhost:7862/act -H "Content-Type: application/json" --data-binary $body | Out-Null
}

Clear-Notepad
```

---

## 6. Keyboard shortcuts reference

| Action | Keys |
|--------|------|
| Save | `ctrl,s` |
| Save As | `ctrl,shift,s` |
| Open | `ctrl,o` |
| New window | `ctrl,n` |
| New tab | `ctrl,t` |
| Select all | `ctrl,a` |
| Undo | `ctrl,z` |
| Redo | `ctrl,y` |
| Find | `ctrl,f` |
| Find and replace | `ctrl,h` |
| Go to line | `ctrl,g` |
| Zoom in/out | `ctrl,+` / `ctrl,-` |
| Reset zoom | `ctrl,0` |
| Word wrap toggle | `alt,z` |

---

## Notes

- WinUI3 Notepad (Windows 11) has tabs — use `ctrl,t` for new tab, `ctrl,w` to close.
- The `type` action can drop the letter 'f' in WinUI3 Notepad. Use clipboard paste for reliable input.
- `"Text Editor"` is the consistent UIA element name across both legacy and WinUI3 Notepad.
- Notepad is WindowsAgent's primary test target — if it works in Notepad, it works everywhere.
