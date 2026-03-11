# windowsagent-screenshot — A tier

Capture screenshots and extract text from any window via WindowsAgent. Primary method for reading content from Chrome, Edge, Electron, and WebView2 apps where the UIA tree is empty.

## Step 0 — Health check

```powershell
$health = curl.exe -s http://localhost:7862/health | ConvertFrom-Json
if ($health.status -ne "ok") {
    Start-ScheduledTask -TaskName "WindowsAgent Server"
    Start-Sleep 4
}
```

---

## 1. Screenshot + OCR a window (primary method)

`/observe` always returns both the UIA tree and a screenshot with OCR text:

```powershell
function Get-WindowScreenshot {
    param([string]$windowTitle)

    $body = @{ window = $windowTitle } | ConvertTo-Json -Compress
    $obs = curl.exe -s -X POST http://localhost:7862/observe `
        -H "Content-Type: application/json" --data-binary $body | ConvertFrom-Json

    return @{
        text       = $obs.ocr_results
        screenshot = $obs.screenshot   # base64 PNG
        uia        = $obs.uia_tree
    }
}

# Read text from Chrome/Edge page:
$data = Get-WindowScreenshot "Microsoft Edge"
$data.text

# Read text from Teams:
$data = Get-WindowScreenshot "Microsoft Teams"
$data.text
```

---

## 2. Save screenshot to file

```powershell
function Save-WindowScreenshot {
    param([string]$windowTitle, [string]$outPath = "C:\Temp\screenshot.png")

    $body = @{ window = $windowTitle } | ConvertTo-Json -Compress
    $obs = curl.exe -s -X POST http://localhost:7862/observe `
        -H "Content-Type: application/json" --data-binary $body | ConvertFrom-Json

    if (-not $obs.screenshot) {
        Write-Warning "No screenshot returned. Is the window visible and not minimised?"
        return
    }

    $bytes = [Convert]::FromBase64String($obs.screenshot)
    [IO.File]::WriteAllBytes($outPath, $bytes)
    Write-Host "Saved to $outPath"
    return $outPath
}

Save-WindowScreenshot "Google Chrome" "C:\Temp\chrome-screenshot.png"
Save-WindowScreenshot "Microsoft Teams" "C:\Temp\teams-screenshot.png"
```

---

## 3. Read text from any window (OCR only)

```powershell
function Read-WindowOCR {
    param([string]$windowTitle)

    $body = @{ window = $windowTitle } | ConvertTo-Json -Compress
    $obs = curl.exe -s -X POST http://localhost:7862/observe `
        -H "Content-Type: application/json" --data-binary $body | ConvertFrom-Json
    return $obs.ocr_results
}

Read-WindowOCR "Google Chrome"
Read-WindowOCR "Microsoft Edge"
Read-WindowOCR "WhatsApp"
Read-WindowOCR "Microsoft Teams"
Read-WindowOCR "Microsoft Excel"
```

---

## 4. Full screen capture (simpler method via Print Screen)

```powershell
function Save-FullScreenshot {
    param([string]$outPath = "C:\Temp\fullscreen.png")

    # PrintScreen to clipboard, then save
    $script = @'
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
[System.Windows.Forms.SendKeys]::SendWait("{PRTSC}")
Start-Sleep -Milliseconds 500
$img = [System.Windows.Forms.Clipboard]::GetImage()
if ($img) {
    $img.Save("OUTPATH")
    Write-Output "Saved"
} else {
    Write-Output "No image on clipboard"
}
'@ -replace "OUTPATH", $outPath.Replace("\", "\\")

    $body = @{ command = $script; shell = "pwsh" } | ConvertTo-Json -Compress
    $result = curl.exe -s -X POST http://localhost:7862/shell `
        -H "Content-Type: application/json" -d $body | ConvertFrom-Json

    Write-Host $result.stdout
    return $outPath
}

Save-FullScreenshot "C:\Temp\fullscreen.png"
```

---

## 5. List visible windows (check what's open)

```powershell
$windows = curl.exe -s http://localhost:7862/windows | ConvertFrom-Json
$windows | Select-Object title, app_name, is_visible | Format-Table -AutoSize
```

---

## Use cases by app

| App | Why OCR is needed | What to capture |
|-----|------------------|-----------------|
| Chrome / Edge | Page body not in UIA tree | `"Google Chrome"` / `"Microsoft Edge"` |
| WhatsApp Web | All content is WebView2 | `"WhatsApp"` |
| New Outlook | WebView2 shell | `"Mail"` |
| Microsoft Teams | Message area is WebView2 | `"Microsoft Teams"` |
| n8n (in browser) | JavaScript SPA | browser window title |
| Electron apps | WebView2 equivalent | window title |

---

## Notes

- Window must be visible and not minimised for screenshots to capture content.
- OCR quality depends on screen DPI and font size. Scale up for small text.
- Screenshot base64 is a PNG embedded in the JSON response from `/observe`.
