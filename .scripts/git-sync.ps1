# git-sync.ps1 - 一键提交并推送到 origin/dev
# 由同目录上一级的「自动提交按钮.cmd」调用
# 日志：%TEMP%\ruoyi-git-sync.log

$ErrorActionPreference = "Continue"
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch {}

$repo    = Split-Path -Parent $PSScriptRoot
$logPath = Join-Path $env:TEMP "ruoyi-git-sync.log"
$target  = "dev"

function Log {
    param([string]$Message, [string]$Color = "Gray")
    $line = "{0}  {1}" -f (Get-Date -Format 'HH:mm:ss'), $Message
    try { Add-Content -Path $logPath -Value $line -Encoding UTF8 } catch {}
    Write-Host $line -ForegroundColor $Color
}

function Test-Port {
    param([string]$HostName, [int]$Port, [int]$TimeoutMs = 1500)
    $client = New-Object System.Net.Sockets.TcpClient
    try {
        $iar = $client.BeginConnect($HostName, $Port, $null, $null)
        if (-not $iar.AsyncWaitHandle.WaitOne($TimeoutMs, $false)) { return $false }
        $client.EndConnect($iar)
        return $true
    } catch {
        return $false
    } finally {
        $client.Close()
    }
}

Write-Host ""
Log "===== 自动提交开始 =====" "Cyan"
Log "仓库: $repo"
Log "日志: $logPath"
try { Set-Location $repo } catch { Log "无法进入仓库目录: $repo" "Red"; exit 1 }

# ---------- 0. git 是否可用 ----------
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Log "找不到 git 命令。请确认 git 已安装且所在目录在 PATH 中（本机为 D:\Git\cmd）。" "Red"
    exit 1
}

# ---------- 1. 提交身份 ----------
$userName  = (git config --get user.name)  2>$null
$userMail  = (git config --get user.email) 2>$null
if ([string]::IsNullOrWhiteSpace($userName) -or [string]::IsNullOrWhiteSpace($userMail)) {
    Log "提交身份缺失（user.name / user.email 未配置），正在写入仓库级身份…" "Yellow"
    git config user.name  "user161514"
    git config user.email "1808749866@qq.com"
    $userName = git config --get user.name
    $userMail = git config --get user.email
    Log "已补全身份: $userName <$userMail>" "Yellow"
}

# ---------- 2. 分支检查 ----------
$branch = (git rev-parse --abbrev-ref HEAD) 2>$null
if ($branch -ne $target) {
    Log "当前分支是 '$branch'，本脚本只推送到 '$target'。已跳过。" "Yellow"
    exit 1
}

# ---------- 3. 远端可达性预检（识别 hosts 劫持 / 加速器未运行）----------
$remoteUrl = (git remote get-url origin) 2>$null
$remoteHost = $null
if ($remoteUrl -match '^https?://([^/]+)')      { $remoteHost = $Matches[1] }
elseif ($remoteUrl -match '^[^@]+@([^:]+):')     { $remoteHost = $Matches[1] }
$reachable = $true
if ($remoteHost) {
    try {
        $ips = @([System.Net.Dns]::GetHostAddresses($remoteHost) | ForEach-Object { $_.IPAddressToString })
    } catch {
        $ips = @()
    }
    if ($ips.Count -eq 0) {
        Log "[网络] 无法解析 $remoteHost" "Red"
        $reachable = $false
    } elseif ($ips -contains "127.0.0.1" -or $ips -contains "0.0.0.0") {
        # hosts 被加速器（Steam++ / Watt Toolkit）改写成了本地回环
        $localOk = (Test-Port "127.0.0.1" 443) -or (Test-Port "127.0.0.1" 80)
        if ($localOk) {
            Log "[网络] $remoteHost 被 hosts 指向 127.0.0.1，本机加速器在监听，走加速通道。" "DarkYellow"
        } else {
            Log "[网络] $remoteHost 被 hosts 指向 127.0.0.1，但本机没有任何加速器在监听！" "Red"
            Log "       原因：Steam++ / Watt Toolkit 的「GitHub 加速」写过 hosts，但加速器没启动。" "Red"
            Log "       处理：启动 Steam++ 并开启 GitHub 加速；或在 Steam++ 里关闭加速/清理 hosts。" "Red"
            $reachable = $false
        }
    } else {
        Log "[网络] $remoteHost 正常解析: $($ips -join ', ')" "DarkGray"
    }
}

# ---------- 4. 是否有变更 / 是否有未推送的提交 ----------
$changes = @(git status --porcelain 2>$null)

$upstream = (git rev-parse --abbrev-ref --symbolic-full-name '@{u}' 2>$null)
$ahead = 0
if ($LASTEXITCODE -eq 0 -and $upstream) {
    $raw = (git rev-list --count "$upstream..HEAD" 2>$null)
    if ($raw) { $ahead = [int]$raw }
}
if ($ahead -gt 0) {
    Log "检测到 $ahead 个未推送的本地提交（上次推送没成功）。" "Yellow"
}

if ($changes.Count -eq 0) {
    if ($ahead -eq 0) {
        Log "工作区干净，没有需要提交的改动。" "Green"
        exit 0
    }
    Log "没有新改动，但需要补推 $ahead 个提交。" "Yellow"
}

# ---------- 5. 提交 ----------
if ($changes.Count -gt 0) {
    git add -A 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Log "git add 失败，已中止。" "Red"
        exit 1
    }

    $message = "Auto commit $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
    $commitOut = (git commit -m $message 2>&1 | Out-String).Trim()
    if ($LASTEXITCODE -ne 0) {
        Log "git commit 失败：" "Red"
        foreach ($l in ($commitOut -split "`r?`n")) { if ($l.Trim()) { Log "  $l" "Red" } }
        exit 1
    }
    Log "已提交: $message" "Green"
}

# ---------- 6. 推送（带重试）----------
if (-not $reachable) {
    Log "网络预检未通过，跳过推送。本地提交已保留，修好网络后重新运行本脚本即可补推。" "Red"
    exit 1
}

$pushed = $false
for ($i = 1; $i -le 3; $i++) {
    $pushOut = (git push origin $target 2>&1 | Out-String).Trim()
    if ($LASTEXITCODE -eq 0) {
        $pushed = $true
        foreach ($l in ($pushOut -split "`r?`n")) { if ($l.Trim()) { Log "  $l" "DarkGray" } }
        break
    }
    Log "第 $i/3 次推送失败。" "Yellow"
    if ($i -lt 3) { Start-Sleep -Seconds 3 }
}

if (-not $pushed) {
    Log "推送失败。最后一段报错：" "Red"
    foreach ($l in ($pushOut -split "`r?`n")) { if ($l.Trim()) { Log "  $l" "Red" } }
    Log "排查建议：" "Yellow"
    Log "  1) 确认 Steam++ / Watt Toolkit 正在运行且已开启 GitHub 加速；" "Yellow"
    Log "  2) 若不想走加速器，在 Steam++ 中关闭加速并清理 hosts（hosts 路径：" "Yellow"
    Log "     C:\Windows\System32\drivers\etc\hosts，删掉 GitHub 相关行后 ipconfig /flushdns）；" "Yellow"
    Log "  3) 凭据失效时，在仓库目录手动执行一次 git push origin $target 重新登录。" "Yellow"
    exit 1
}

Log "完成：已提交并推送到 origin/$target。" "Green"
Write-Host ""
