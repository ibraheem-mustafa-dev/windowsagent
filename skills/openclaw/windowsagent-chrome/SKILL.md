# windowsagent-chrome — S tier

Control Google Chrome via WindowsAgent. Open URLs, navigate tabs, read page content, fill forms.

## Core pattern (use this everywhere)

**Always use `ConvertTo-Json` — never write JSON strings by hand. Escaping will break you.**

```powershell
# Act on an element
$body = @{
    window  = "Google Chrome"
    action  = "key"
    element = "Google Chrome"
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

## Step 1 — Discover element names (always do this before acting)

Chrome's UIA tree is shallow. Before clicking/typing, observe to find exact element names:

```powershell
$body = @{ window = "Google Chrome" } | ConvertTo-Json -Compress
$obs = curl.exe -s -X POST http://localhost:7862/observe `
    -H "Content-Type: application/json" --data-binary $body | ConvertFrom-Json

# Read visible text (OCR)
$obs.ocr_results

# Inspect UIA tree for element names
$obs.uia_tree | ConvertTo-Json -Depth 5
```

**Known Chrome UIA element names:**
| Element | UIA Name |
|---------|----------|
| Address bar | `"Address and search bar"` |
| Back button | `"Back"` |
| Forward button | `"Forward"` |
| Reload button | `"Reload"` |
| New tab button | `"New Tab"` |

For page content (buttons, links, inputs) — **always observe first**. Names come from ARIA labels.

---

## 2. Open a URL

```powershell
# Fastest: spawn a new Chrome window with the URL
$url = "https://example.com"
$body = @{ command = "chrome.exe `"$url`"" } | ConvertTo-Json -Compress
curl.exe -s -X POST http://localhost:7862/spawn -H "Content-Type: application/json" -d $body
Start-Sleep 2
```

Navigate in existing Chrome window:

```powershell
function Open-ChromeUrl {
    param([string]$url)

    # Focus address bar
    $body = @{
        window  = "Google Chrome"
        action  = "key"
        element = "Google Chrome"
        params  = @{ keys = "ctrl,l" }
    } | ConvertTo-Json -Compress
    curl.exe -s -X POST http://localhost:7862/act -H "Content-Type: application/json" --data-binary $body | Out-Null
    Start-Sleep 0.3

    # Type URL
    $body = @{
        window  = "Google Chrome"
        action  = "type"
        element = "Address and search bar"
        params  = @{ text = $url }
    } | ConvertTo-Json -Compress
    curl.exe -s -X POST http://localhost:7862/act -H "Content-Type: application/json" --data-binary $body | Out-Null
    Start-Sleep 0.2

    # Navigate
    $body = @{
        window  = "Google Chrome"
        action  = "key"
        element = "Address and search bar"
        params  = @{ keys = "enter" }
    } | ConvertTo-Json -Compress
    curl.exe -s -X POST http://localhost:7862/act -H "Content-Type: application/json" --data-binary $body | Out-Null
    Start-Sleep 2

    Write-Host "Navigated to $url"
}

# Usage:
Open-ChromeUrl "https://example.com"
```

---

## 3. Read page content

UIA won't give you page body text. Use OCR:

```powershell
function Read-ChromePage {
    $body = @{ window = "Google Chrome" } | ConvertTo-Json -Compress
    $obs = curl.exe -s -X POST http://localhost:7862/observe `
        -H "Content-Type: application/json" --data-binary $body | ConvertFrom-Json
    return $obs.ocr_results
}

Read-ChromePage
```

---

## 4. Click a button or link

```powershell
function Click-ChromeElement {
    param([string]$elementName)

    # Observe first to confirm name exists
    $body = @{ window = "Google Chrome" } | ConvertTo-Json -Compress
    $obs = curl.exe -s -X POST http://localhost:7862/observe `
        -H "Content-Type: application/json" --data-binary $body | ConvertFrom-Json

    # Act
    $body = @{
        window  = "Google Chrome"
        action  = "click"
        element = $elementName
    } | ConvertTo-Json -Compress
    $result = curl.exe -s -X POST http://localhost:7862/act `
        -H "Content-Type: application/json" --data-binary $body | ConvertFrom-Json

    if (-not $result.success) {
        Write-Warning "Click failed. Available elements:"
        $obs.uia_tree | ConvertTo-Json | Select-String "Name"
    }
    return $result
}

Click-ChromeElement "Sign in"
```

---

## 5. Fill a form field

```powershell
function Fill-ChromeField {
    param([string]$fieldName, [string]$value)

    # Click to focus
    $body = @{
        window  = "Google Chrome"
        action  = "click"
        element = $fieldName
    } | ConvertTo-Json -Compress
    curl.exe -s -X POST http://localhost:7862/act -H "Content-Type: application/json" --data-binary $body | Out-Null
    Start-Sleep 0.2

    # Select all existing text and replace
    $body = @{
        window  = "Google Chrome"
        action  = "key"
        element = $fieldName
        params  = @{ keys = "ctrl,a" }
    } | ConvertTo-Json -Compress
    curl.exe -s -X POST http://localhost:7862/act -H "Content-Type: application/json" --data-binary $body | Out-Null

    # Type value
    $body = @{
        window  = "Google Chrome"
        action  = "type"
        element = $fieldName
        params  = @{ text = $value }
    } | ConvertTo-Json -Compress
    $result = curl.exe -s -X POST http://localhost:7862/act `
        -H "Content-Type: application/json" --data-binary $body | ConvertFrom-Json

    return $result
}

Fill-ChromeField "Email" "user@example.com"
```

---

## 6. Tab management

```powershell
# New tab
$body = @{ window="Google Chrome"; action="key"; element="Google Chrome"; params=@{keys="ctrl,t"} } | ConvertTo-Json -Compress
curl.exe -s -X POST http://localhost:7862/act -H "Content-Type: application/json" --data-binary $body | Out-Null

# Close tab
$body = @{ window="Google Chrome"; action="key"; element="Google Chrome"; params=@{keys="ctrl,w"} } | ConvertTo-Json -Compress
curl.exe -s -X POST http://localhost:7862/act -H "Content-Type: application/json" --data-binary $body | Out-Null

# Next tab
$body = @{ window="Google Chrome"; action="key"; element="Google Chrome"; params=@{keys="ctrl,tab"} } | ConvertTo-Json -Compress
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
| Reload | `ctrl,r` |
| Hard reload | `ctrl,shift,r` |
| Find on page | `ctrl,f` |
| Back | `alt,Left` |
| Forward | `alt,Right` |
| Next tab | `ctrl,tab` |
| Previous tab | `ctrl,shift,tab` |
| Dev tools | `f12` |
| Bookmark | `ctrl,d` |
| Zoom in/out/reset | `ctrl,+` / `ctrl,-` / `ctrl,0` |

---

## When UIA clicking fails

1. Observe first — confirm the element name exists in the UIA tree
2. If not in UIA tree — use OCR coordinates (Phase 2 feature, not yet available)
3. Fallback — use keyboard-only navigation (`Tab`, `Enter`, arrow keys)
4. Last resort — write a direct API call via `/shell` instead of clicking the UI
