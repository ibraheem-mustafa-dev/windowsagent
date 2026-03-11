# windowsagent-edge — S tier

Control Microsoft Edge via WindowsAgent. Navigate URLs, manage tabs, read page content, fill forms.

Edge and Chrome have identical UIA structures. All patterns here mirror `windowsagent-chrome` — the only difference is the window title and the binary name.

## Core pattern

**Always use `ConvertTo-Json` — never write JSON strings by hand.**

```powershell
$body = @{
    window  = "Microsoft Edge"
    action  = "key"
    element = "Microsoft Edge"
    params  = @{ keys = "ctrl,l" }
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
$body = @{ window = "Microsoft Edge" } | ConvertTo-Json -Compress
$obs = curl.exe -s -X POST http://localhost:7862/observe `
    -H "Content-Type: application/json" --data-binary $body | ConvertFrom-Json

$obs.ocr_results        # visible page text
$obs.uia_tree | ConvertTo-Json -Depth 4  # element names
```

**Known Edge UIA element names:**
| Element | UIA Name |
|---------|----------|
| Address bar | `"Address and search bar"` |
| Back | `"Back"` |
| Forward | `"Forward"` |
| Reload | `"Reload"` |
| New Tab | `"New Tab"` |
| Settings | `"Settings and more"` |

---

## 2. Open a URL

```powershell
# Spawn Edge with URL
$url = "https://example.com"
$body = @{ command = "msedge.exe `"$url`"" } | ConvertTo-Json -Compress
curl.exe -s -X POST http://localhost:7862/spawn -H "Content-Type: application/json" -d $body
Start-Sleep 3
```

Navigate in existing Edge window:

```powershell
function Open-EdgeUrl {
    param([string]$url)

    $body = @{ window="Microsoft Edge"; action="key"; element="Microsoft Edge"; params=@{keys="ctrl,l"} } | ConvertTo-Json -Compress
    curl.exe -s -X POST http://localhost:7862/act -H "Content-Type: application/json" --data-binary $body | Out-Null
    Start-Sleep 0.3

    $body = @{ window="Microsoft Edge"; action="type"; element="Address and search bar"; params=@{text=$url} } | ConvertTo-Json -Compress
    curl.exe -s -X POST http://localhost:7862/act -H "Content-Type: application/json" --data-binary $body | Out-Null
    Start-Sleep 0.2

    $body = @{ window="Microsoft Edge"; action="key"; element="Address and search bar"; params=@{keys="enter"} } | ConvertTo-Json -Compress
    curl.exe -s -X POST http://localhost:7862/act -H "Content-Type: application/json" --data-binary $body | Out-Null
    Start-Sleep 2
}

Open-EdgeUrl "https://example.com"
```

---

## 3. Read page content

```powershell
$body = @{ window = "Microsoft Edge" } | ConvertTo-Json -Compress
$obs = curl.exe -s -X POST http://localhost:7862/observe `
    -H "Content-Type: application/json" --data-binary $body | ConvertFrom-Json
$obs.ocr_results
```

---

## 4. Click a button or link

```powershell
function Click-EdgeElement {
    param([string]$elementName)

    $body = @{
        window  = "Microsoft Edge"
        action  = "click"
        element = $elementName
    } | ConvertTo-Json -Compress

    $result = curl.exe -s -X POST http://localhost:7862/act `
        -H "Content-Type: application/json" --data-binary $body | ConvertFrom-Json

    if (-not $result.success) { Write-Warning "Click failed on '$elementName': $($result.error)" }
    return $result
}
```

---

## 5. Fill a form field

```powershell
function Fill-EdgeField {
    param([string]$fieldName, [string]$value)

    $body = @{ window="Microsoft Edge"; action="click"; element=$fieldName } | ConvertTo-Json -Compress
    curl.exe -s -X POST http://localhost:7862/act -H "Content-Type: application/json" --data-binary $body | Out-Null
    Start-Sleep 0.2

    $body = @{ window="Microsoft Edge"; action="key"; element=$fieldName; params=@{keys="ctrl,a"} } | ConvertTo-Json -Compress
    curl.exe -s -X POST http://localhost:7862/act -H "Content-Type: application/json" --data-binary $body | Out-Null

    $body = @{ window="Microsoft Edge"; action="type"; element=$fieldName; params=@{text=$value} } | ConvertTo-Json -Compress
    $result = curl.exe -s -X POST http://localhost:7862/act `
        -H "Content-Type: application/json" --data-binary $body | ConvertFrom-Json

    return $result
}

Fill-EdgeField "Email or phone" "user@example.com"
```

---

## 6. Tab management

```powershell
$shortcuts = @{
    "New tab"         = "ctrl,t"
    "Close tab"       = "ctrl,w"
    "Reopen tab"      = "ctrl,shift,t"
    "Next tab"        = "ctrl,tab"
    "Previous tab"    = "ctrl,shift,tab"
    "Reload"          = "ctrl,r"
    "Hard reload"     = "ctrl,shift,r"
}

# Use any shortcut:
$key = "ctrl,t"
$body = @{ window="Microsoft Edge"; action="key"; element="Microsoft Edge"; params=@{keys=$key} } | ConvertTo-Json -Compress
curl.exe -s -X POST http://localhost:7862/act -H "Content-Type: application/json" --data-binary $body | Out-Null
```

---

## 7. Keyboard shortcuts reference

| Action | Keys |
|--------|------|
| Address bar | `ctrl,l` |
| New tab | `ctrl,t` |
| Close tab | `ctrl,w` |
| Reopen closed tab | `ctrl,shift,t` |
| Next tab | `ctrl,tab` |
| Reload | `ctrl,r` |
| Hard reload | `ctrl,shift,r` |
| Find on page | `ctrl,f` |
| Back | `alt,Left` |
| Forward | `alt,Right` |
| Dev tools | `f12` |
| Reading view | `f9` |
| Sidebar toggle | `ctrl,shift,e` |
| Zoom in/out/reset | `ctrl,+` / `ctrl,-` / `ctrl,0` |

---

## Edge Sidebar warning

Edge Sidebar (Copilot panel) can shift element positions. If actions are hitting the wrong area:

```powershell
# Close sidebar first
$body = @{ window="Microsoft Edge"; action="key"; element="Microsoft Edge"; params=@{keys="ctrl,shift,e"} } | ConvertTo-Json -Compress
curl.exe -s -X POST http://localhost:7862/act -H "Content-Type: application/json" --data-binary $body | Out-Null
```
