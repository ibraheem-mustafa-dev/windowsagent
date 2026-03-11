# windowsagent-outlook — A tier

Read and send emails via IMAP/SMTP and himalaya. Navigate new Outlook (olk.exe) via keyboard shortcuts.

**Architecture:** New Outlook is WebView2. UIA cannot read email content. All email reading and sending goes through IMAP/SMTP or himalaya directly.

## Decision tree

| Task | Method |
|------|--------|
| Read recent emails | `himalaya` (preferred) or IMAP Python |
| Read starred/flagged emails | `himalaya` |
| Send email | SMTP Python or `himalaya` |
| Search inbox | `himalaya` |
| Open Outlook to compose with attachments | UIA keyboard shortcut |
| Navigate to a folder | UIA keyboard shortcut |

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

## 1. Read recent emails (himalaya)

Configure himalaya accounts in `~/.config/himalaya/config.toml` before use.

```powershell
function Get-RecentEmails {
    param([string]$account = "default", [int]$count = 20, [string]$folder = "INBOX")

    $body = @{
        command = "himalaya --account $account envelope list --folder '$folder' --page-size $count"
        shell   = "pwsh"
    } | ConvertTo-Json -Compress

    $result = curl.exe -s -X POST http://localhost:7862/shell `
        -H "Content-Type: application/json" -d $body | ConvertFrom-Json
    return $result.stdout
}

Get-RecentEmails                # default account, 20 latest
Get-RecentEmails "work"         # work account
Get-RecentEmails "personal"     # personal account
```

---

## 2. Read a specific email

```powershell
function Read-Email {
    param([string]$id, [string]$account = "default", [string]$folder = "INBOX")

    $body = @{
        command = "himalaya --account $account message read $id --folder '$folder'"
        shell   = "pwsh"
    } | ConvertTo-Json -Compress

    $result = curl.exe -s -X POST http://localhost:7862/shell `
        -H "Content-Type: application/json" -d $body | ConvertFrom-Json
    return $result.stdout
}

Read-Email 42              # read email ID 42
Read-Email 15 "work"       # email 15 from work account
```

---

## 3. Read starred/flagged emails (action needed)

```powershell
function Get-StarredEmails {
    param([string]$account = "default")

    $body = @{
        command = "himalaya --account $account envelope list --folder INBOX --query 'flag:flagged'"
        shell   = "pwsh"
    } | ConvertTo-Json -Compress

    $result = curl.exe -s -X POST http://localhost:7862/shell `
        -H "Content-Type: application/json" -d $body | ConvertFrom-Json
    return $result.stdout
}

Get-StarredEmails "default"
```

---

## 4. Search emails

```powershell
function Search-Emails {
    param([string]$query, [string]$account = "default")

    $body = @{
        command = "himalaya --account $account envelope list --folder INBOX --query '$query'"
        shell   = "pwsh"
    } | ConvertTo-Json -Compress

    $result = curl.exe -s -X POST http://localhost:7862/shell `
        -H "Content-Type: application/json" -d $body | ConvertFrom-Json
    return $result.stdout
}

Search-Emails "subject:invoice"
Search-Emails "from:colleague@example.com" "work"
Search-Emails "unseen" "default"
```

---

## 5. Send an email (himalaya)

```powershell
function Send-Email {
    param(
        [string]$from    = "default",
        [string]$to,
        [string]$subject,
        [string]$body
    )

    # Write MML to temp file
    $mml = @"
From: your-email@example.com
To: $to
Subject: $subject

$body
"@
    $mml | Out-File -Encoding utf8 "%TEMP%\wa-email.eml" -NoNewline

    $cmd = "himalaya --account $from message send %TEMP%\wa-email.eml"
    $shellBody = @{ command = $cmd; shell = "pwsh" } | ConvertTo-Json -Compress

    $result = curl.exe -s -X POST http://localhost:7862/shell `
        -H "Content-Type: application/json" -d $shellBody | ConvertFrom-Json
    return $result
}
```

---

## 6. Flag an email (mark as needs-response)

```powershell
function Flag-Email {
    param([string]$id, [string]$account = "default")

    $body = @{
        command = "himalaya --account $account flag add $id flagged --folder INBOX"
        shell   = "pwsh"
    } | ConvertTo-Json -Compress

    curl.exe -s -X POST http://localhost:7862/shell -H "Content-Type: application/json" -d $body | Out-Null
}

function Mark-EmailAnswered {
    param([string]$id, [string]$account = "default")

    $body = @{
        command = "himalaya --account $account flag add $id answered --folder INBOX"
        shell   = "pwsh"
    } | ConvertTo-Json -Compress

    curl.exe -s -X POST http://localhost:7862/shell -H "Content-Type: application/json" -d $body | Out-Null
}
```

---

## 7. Open Outlook and compose (UIA — for attachments)

```powershell
# Launch Outlook
$body = @{ command = "olk.exe" } | ConvertTo-Json -Compress
curl.exe -s -X POST http://localhost:7862/spawn -H "Content-Type: application/json" -d $body
Start-Sleep 4

# New email: Ctrl+N
$body = @{ window="Mail"; action="key"; element="Mail"; params=@{keys="ctrl,n"} } | ConvertTo-Json -Compress
curl.exe -s -X POST http://localhost:7862/act -H "Content-Type: application/json" --data-binary $body | Out-Null
Start-Sleep 1

# Observe new compose window to find field names
$body = @{ window = "New Message" } | ConvertTo-Json -Compress
curl.exe -s -X POST http://localhost:7862/observe -H "Content-Type: application/json" --data-binary $body | Out-Null
```

---

## 8. Outlook keyboard shortcuts

| Action | Keys |
|--------|------|
| New email | `ctrl,n` |
| Reply | `ctrl,r` |
| Reply all | `ctrl,shift,r` |
| Forward | `ctrl,f` |
| Send | `ctrl,enter` |
| Delete | `delete` |
| Mark as read | `ctrl,q` |
| Mark as unread | `ctrl,u` |
| Flag/unflag | `insert` |
| Search | `ctrl,e` |
| Go to inbox | `ctrl,shift,i` |

---

## Notes

- himalaya account names must be configured in `~/.config/himalaya/config.toml`.
- If himalaya isn't configured yet, use raw IMAP Python as fallback.
- All email sends must be reviewed and approved by the user before dispatching.
