# auto_login.ps1
param(
    [string]$username = "your_username",
    [string]$password = "your_password"
)

# 1. 启动应用
Start-Process "C:\Program Files\MyApp\app.exe"
Start-Sleep -Seconds 5

# 2. 获取窗口
Add-Type -AssemblyName Microsoft.VisualBasic
Add-Type -AssemblyName System.Windows.Forms

$allWindows = Get-Process | Where-Object { $_.MainWindowHandle -ne 0 }

# 查看进程的窗口信息
foreach ($proc in $allWindows) {
    # 获取窗口类名
    $className = (Get-WindowClass -Hwnd $proc.MainWindowHandle)
    Write-Host "$($proc.ProcessName) - 类名: $className"
}

# 3. 找到登录窗口
$loginWindow = Get-Process | Where-Object {$_.MainWindowTitle -like "*登录*"}
if ($loginWindow) {
    # 激活窗口
    [Microsoft.VisualBasic.Interaction]::AppActivate($loginWindow.Id)
    Start-Sleep -Milliseconds 500
    
    # 输入用户名
    [System.Windows.Forms.SendKeys]::SendWait($username)
    Start-Sleep -Milliseconds 500
    
    # 切换到密码框
    [System.Windows.Forms.SendKeys]::SendWait("{TAB}")
    Start-Sleep -Milliseconds 500
    
    # 输入密码
    [System.Windows.Forms.SendKeys]::SendWait($password)
    Start-Sleep -Milliseconds 500
    
    # 点击登录
    [System.Windows.Forms.SendKeys]::SendWait("{ENTER}")
    
    Write-Host "✅ 登录成功！" -ForegroundColor Green
} else {
    Write-Host "❌ 未找到登录窗口" -ForegroundColor Red
}