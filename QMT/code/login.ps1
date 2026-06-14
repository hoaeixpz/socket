# auto_login.ps1
Import-Module CredentialManager

$cred = Get-StoredCredential -Target QMT_AutoLogin
if (-not $cred) {
    Write-Warning "Error not found QMT passward"
    exit
}

$password = $cred.GetNetworkCredential().Password

# 1. 启动应用
#Start-Process "C:\QMT\bin.x64\XtItClient.exe"
#Start-Sleep -Seconds 8

# 2. 获取窗口
Add-Type -AssemblyName Microsoft.VisualBasic
Add-Type -AssemblyName System.Windows.Forms

$allWindows = Get-Process | Where-Object { $_.MainWindowHandle -ne 0 }

# 查看进程的窗口信息
#foreach ($proc in $allWindows) {
#    # 获取窗口类名
#    Write-Host "$($proc.ProcessName)"
#}

$qmtProcess = Get-Process -Name "XtItClient" -ErrorAction SilentlyContinue
if (-not $qmtProcess) {
    Write-Host "Error not found QMT"
    exit
}

# 3. 找到登录窗口
foreach ($proc in $qmtProcess) {
    if ($proc.MainWindowHandle -ne 0) {
        # 激活窗口
        Write-Host "activite window"
        [Microsoft.VisualBasic.Interaction]::AppActivate($proc.Id) | Out-Null
        Start-Sleep -Milliseconds 500
    
        # 切换到密码框
        [System.Windows.Forms.SendKeys]::SendWait("{TAB}")
        Start-Sleep -Milliseconds 500
    
        # 输入密码
        [System.Windows.Forms.SendKeys]::SendWait($password)
        Start-Sleep -Milliseconds 500
    
        # 点击登录
        [System.Windows.Forms.SendKeys]::SendWait("{ENTER}")
    
        Write-Host "Success" -ForegroundColor Green
        break
    }
}

    
