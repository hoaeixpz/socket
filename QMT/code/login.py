import subprocess
import time
import pyautogui

# 启动 QMT 客户端（异步）
process = subprocess.Popen(
    r"C:\QMT\bin.x64\XtItClient.exe",   # 使用 raw string 避免反斜杠转义
    shell=False                          # 通常不需要 shell，直接启动 exe
)

pyautogui.FAILSAFE = False
time.sleep(5)
for i in range(2):
	time.sleep(5)
	print("alt+tab")
	pyautogui.hotkey('alt','tab')

subprocess.run(['powershell.exe', '-File', 'login.ps1'], capture_output=False,text=True,check=True)