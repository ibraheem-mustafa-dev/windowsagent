# windowsagent-explorer — A tier

File system operations via `/shell` (primary) and Windows File Explorer UIA (for dialogs and drag-and-drop).

**Use `/shell` for all scripted file ops** — faster, returns output, handles paths with spaces. Use UIA only for Save/Open dialogs or when Explorer is the only interface.

## Step 0 — Health check

```powershell
$health = curl.exe -s http://localhost:7862/health | ConvertFrom-Json
if ($health.status -ne "ok") {
    Start-ScheduledTask -TaskName "WindowsAgent Server"
    Start-Sleep 4
}
```

---

## 1. Common file operations via /shell

```powershell
# List files
$body = @{ command = "Get-ChildItem '%USERPROFILE%\projects' -Name" } | ConvertTo-Json -Compress
$result = curl.exe -s -X POST http://localhost:7862/shell -H "Content-Type: application/json" -d $body | ConvertFrom-Json
$result.stdout

# List with details
$body = @{ command = "Get-ChildItem '%USERPROFILE%\projects' | Select-Object Name, Length, LastWriteTime | Format-Table -AutoSize" } | ConvertTo-Json -Compress
$result = curl.exe -s -X POST http://localhost:7862/shell -H "Content-Type: application/json" -d $body | ConvertFrom-Json
$result.stdout

# Create folder
$body = @{ command = "New-Item -ItemType Directory -Force -Path '%USERPROFILE%\projects\new-project'" } | ConvertTo-Json -Compress
curl.exe -s -X POST http://localhost:7862/shell -H "Content-Type: application/json" -d $body | Out-Null

# Copy file
$body = @{ command = "Copy-Item 'C:\Temp\file.txt' '%USERPROFILE%\Desktop\'" } | ConvertTo-Json -Compress
curl.exe -s -X POST http://localhost:7862/shell -H "Content-Type: application/json" -d $body | Out-Null

# Move file
$body = @{ command = "Move-Item 'C:\Temp\file.txt' '%USERPROFILE%\Desktop\file.txt'" } | ConvertTo-Json -Compress
curl.exe -s -X POST http://localhost:7862/shell -H "Content-Type: application/json" -d $body | Out-Null

# Rename
$body = @{ command = "Rename-Item 'C:\Temp\old-name.txt' 'new-name.txt'" } | ConvertTo-Json -Compress
curl.exe -s -X POST http://localhost:7862/shell -H "Content-Type: application/json" -d $body | Out-Null
```

---

## 2. Delete safely (to Recycle Bin)

**Never use `Remove-Item` without confirming with the user.** Always use Recycle Bin:

```powershell
function Remove-ToRecycleBin {
    param([string]$path)

    $body = @{
        command = "(New-Object -ComObject Shell.Application).Namespace(0).ParseName('$path').InvokeVerb('delete')"
        shell   = "pwsh"
    } | ConvertTo-Json -Compress

    $result = curl.exe -s -X POST http://localhost:7862/shell `
        -H "Content-Type: application/json" -d $body | ConvertFrom-Json
    Write-Host "Moved to Recycle Bin: $path"
}

Remove-ToRecycleBin "C:\Temp\old-file.txt"
```

---

## 3. Search for files

```powershell
function Find-Files {
    param([string]$startDir, [string]$pattern, [switch]$recursive)

    $recurse = if ($recursive) { "-Recurse" } else { "" }
    $body = @{
        command = "Get-ChildItem '$startDir' -Filter '$pattern' $recurse | Select-Object FullName | Format-Table -HideTableHeaders"
        shell   = "pwsh"
    } | ConvertTo-Json -Compress

    $result = curl.exe -s -X POST http://localhost:7862/shell `
        -H "Content-Type: application/json" -d $body | ConvertFrom-Json
    return $result.stdout
}

Find-Files "%USERPROFILE%\projects" "*.md" -recursive
Find-Files "%USERPROFILE%\Downloads" "invoice*.pdf"
```

---

## 4. Open Explorer at a path (visual)

```powershell
function Open-Explorer {
    param([string]$path)

    $body = @{ command = "explorer.exe '$path'" } | ConvertTo-Json -Compress
    curl.exe -s -X POST http://localhost:7862/spawn -H "Content-Type: application/json" -d $body
    Start-Sleep 1
}

Open-Explorer "%USERPROFILE%\projects"
Open-Explorer "%USERPROFILE%\Downloads"
```

---

## 5. Navigate Explorer to a path (UIA)

```powershell
function Navigate-Explorer {
    param([string]$path)

    # Alt+D focuses address bar
    $body = @{ window="File Explorer"; action="key"; element="File Explorer"; params=@{keys="alt,d"} } | ConvertTo-Json -Compress
    curl.exe -s -X POST http://localhost:7862/act -H "Content-Type: application/json" --data-binary $body | Out-Null
    Start-Sleep 0.3

    # Type path
    $body = @{ window="File Explorer"; action="type"; element="Address Band Root"; params=@{text=$path} } | ConvertTo-Json -Compress
    $r = curl.exe -s -X POST http://localhost:7862/act -H "Content-Type: application/json" --data-binary $body | ConvertFrom-Json

    if (-not $r.success) {
        # Try alternate element name
        $body = @{ window="File Explorer"; action="type"; element="Address"; params=@{text=$path} } | ConvertTo-Json -Compress
        curl.exe -s -X POST http://localhost:7862/act -H "Content-Type: application/json" --data-binary $body | Out-Null
    }
    Start-Sleep 0.2

    $body = @{ window="File Explorer"; action="key"; element="File Explorer"; params=@{keys="enter"} } | ConvertTo-Json -Compress
    curl.exe -s -X POST http://localhost:7862/act -H "Content-Type: application/json" --data-binary $body | Out-Null
    Start-Sleep 0.5
}
```

---

## 6. Interact with Save/Open dialogs

When an app shows a file picker:

```powershell
function Fill-FileDialog {
    param([string]$dialogTitle = "Save As", [string]$filePath)

    # Observe to confirm dialog is open
    $body = @{ window = $dialogTitle } | ConvertTo-Json -Compress
    $obs = curl.exe -s -X POST http://localhost:7862/observe `
        -H "Content-Type: application/json" --data-binary $body | ConvertFrom-Json

    # Type path in filename field
    $body = @{ window=$dialogTitle; action="type"; element="File name:"; params=@{text=$filePath} } | ConvertTo-Json -Compress
    $r = curl.exe -s -X POST http://localhost:7862/act -H "Content-Type: application/json" --data-binary $body | ConvertFrom-Json

    if ($r.success) {
        # Click Save/Open
        $button = if ($dialogTitle -match "Save") { "Save" } else { "Open" }
        $body = @{ window=$dialogTitle; action="click"; element=$button } | ConvertTo-Json -Compress
        curl.exe -s -X POST http://localhost:7862/act -H "Content-Type: application/json" --data-binary $body | Out-Null
    } else {
        Write-Warning "File name field not found. Run observe on '$dialogTitle' to check element names."
        $obs.uia_tree | ConvertTo-Json -Depth 3
    }
}

Fill-FileDialog "Save As" "%USERPROFILE%\Desktop\output.pdf"
```

---

## 7. Explorer keyboard shortcuts

| Action | Keys |
|--------|------|
| Address bar | `alt,d` |
| New folder | `ctrl,shift,n` |
| Rename | `f2` |
| Delete (Recycle) | `delete` |
| Select all | `ctrl,a` |
| Copy | `ctrl,c` |
| Cut | `ctrl,x` |
| Paste | `ctrl,v` |
| Undo | `ctrl,z` |
| Properties | `alt,enter` |
| Up one level | `alt,Up` |
| Search | `ctrl,f` |
