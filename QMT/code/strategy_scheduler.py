# -*- coding: utf-8 -*-
"""
miniQMT 策略进程管理器
每月第一个周五 18:00 关闭策略，18:30 重启策略
"""
import subprocess
import sys
import os
import time
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler

# ======================== 可配置项 ========================

# 关闭策略：每月第一个周五 18:00
STOP_DAY  = '1-7'        # 每月 1~7 号（第一个周五必在此范围）
STOP_DOW  = 'fri'        # 周五
STOP_HOUR   = 18
STOP_MINUTE = 0

# 启动策略：每月第一个周五 18:30
START_DAY  = '1-7'
START_DOW  = 'fri'
START_HOUR   = 18
START_MINUTE = 30

# 策略脚本路径（相对于本脚本所在目录）
STRATEGY_SCRIPT = "miniqmt_small_cap_0_1.py"

# ======================== 日志 ========================

def log(msg: str):
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{timestamp}] {msg}", flush=True)

# ======================== 进程管理 ========================

g_process = None  # 当前运行的策略子进程


def start_strategy():
    """启动 miniqmt_small_cap_0_1.py"""
    global g_process

    # 检查调度器自己管理的子进程
    if g_process is not None and g_process.poll() is None:
        log("策略进程已在运行中（调度器子进程），跳过启动")
        return

    # 检查是否已有手动启动的进程在运行
    existing_pids = find_strategy_pids()
    if existing_pids:
        log(f"策略进程已在运行中, PID: {existing_pids}，跳过启动")
        return

    script_dir = os.path.dirname(os.path.abspath(__file__))
    script_path = os.path.join(script_dir, STRATEGY_SCRIPT)

    if not os.path.exists(script_path):
        log(f"错误: 找不到策略脚本 {script_path}")
        return

    log(f"正在启动策略脚本: {STRATEGY_SCRIPT}")
    try:
        env = os.environ.copy()
        env['PYTHONIOENCODING'] = 'utf-8'
        # 用 start 打开独立终端，cmd /k 保证策略结束后终端窗口保留
        # start "" 是空标题的 workaround（start 把第一个引号参数当标题）
        # 外层 cmd /c 立即退出，终端独立于调度器进程
        g_process = subprocess.Popen(
            ['cmd', '/c', 'start', '', 'cmd', '/k', sys.executable, script_path],
            cwd=script_dir,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.STDOUT,
            env=env,
        )
        log(f"策略进程已在新终端中启动")
    except Exception as e:
        log(f"启动策略进程失败: {e}")


def find_strategy_pids():
    """查找所有运行 miniqmt_small_cap_0_1.py 的进程 PID 列表"""
    try:
        # 用自定义分隔符输出，避免 Format-List 折行导致命令行被截断
        ps_cmd = (
            'Get-CimInstance Win32_Process -Filter "name=\'python.exe\'" | '
            'ForEach-Object { $_.ProcessId.ToString() + "|||" + $_.CommandLine }'
        )
        result = subprocess.run(
            ['powershell', '-NoProfile', '-Command', ps_cmd],
            capture_output=True, text=True, timeout=15
        )
        pids = []
        for line in result.stdout.strip().split('\n'):
            line = line.strip()
            if '|||' in line and STRATEGY_SCRIPT in line:
                pid_str = line.split('|||')[0]
                try:
                    pids.append(int(pid_str))
                except ValueError:
                    pass
        return pids
    except Exception as e:
        log(f"查找策略进程失败: {e}")
        return []


def stop_strategy():
    """关闭 miniqmt_small_cap_0_1.py 进程并验证是否已杀死

    只终止 python.exe 策略进程，保留 cmd 终端窗口以便回看输出日志。
    """
    global g_process

    # 查找并终止所有策略 python 进程（不用 /t，避免波及 cmd 父进程导致终端关闭）
    pids = find_strategy_pids()
    if pids:
        log(f"发现 {len(pids)} 个策略进程: {pids}")
        for pid in pids:
            subprocess.run(
                ['taskkill', '/f', '/pid', str(pid)],
                capture_output=True, text=True, timeout=10
            )
            log(f"已终止 PID {pid}")

    # 即便 g_process（cmd.exe）还活着，策略 python 进程已杀，标记为 None
    # 终端窗口会因为 cmd /k 保留下来，供用户查看历史输出
    g_process = None

    # 验证：每 5 秒检查一次，最多查 3 次，确认进程已消失
    log("验证关闭结果...")
    for i in range(3):
        time.sleep(5)
        remain = find_strategy_pids()
        now = datetime.now().strftime('%H:%M:%S')
        if remain:
            log(f"  [{now}] 第{i+1}次检查: 仍有残留进程 {remain}")
        else:
            log(f"  [{now}] 第{i+1}次检查: 无残留进程，关闭成功")
            return

    # 3 次仍有残留，强制再杀一轮
    remain = find_strategy_pids()
    if remain:
        log(f"仍有残留进程 {remain}，再次强制终止")
        for pid in remain:
            subprocess.run(
                ['taskkill', '/f', '/pid', str(pid)],
                capture_output=True, text=True, timeout=10
            )
        time.sleep(2)
        remain = find_strategy_pids()
        if remain:
            log(f"关闭失败! 残留进程: {remain}")
        else:
            log("二次强制终止后已无残留")


# ======================== 定时任务 ========================

def start_job():
    log("========== 定时启动策略 ==========")
    start_strategy()


def stop_job():
    log("========== 定时关闭策略 ==========")
    stop_strategy()


def first_friday_match():
    """检查今天是否是每月的第一个周五"""
    now = datetime.now()
    day = now.day
    dow = now.weekday()  # 0=周一, 4=周五
    return dow == 4 and 1 <= day <= 7


def watchdog_job():
    """看门狗：检查策略进程是否意外退出，如退出则重启"""
    global g_process

    # 只在重启窗口内（关闭后 30 分钟）才自动重启
    if not first_friday_match():
        return
    now = datetime.now()
    now_minutes = now.hour * 60 + now.minute
    stop_minutes = STOP_HOUR * 60 + STOP_MINUTE
    start_minutes = START_HOUR * 60 + START_MINUTE
    if not (stop_minutes <= now_minutes <= start_minutes):
        return

    if not find_strategy_pids():
        log("看门狗: 策略进程意外退出")
        log("看门狗: 正在重启策略进程...")
        start_strategy()


# ======================== 主入口 ========================

scheduler = BackgroundScheduler()


def main():
    log("策略进程管理器启动")

    # 注册定时任务：每月第一个周五
    scheduler.add_job(start_job, 'cron',
                      day=START_DAY, day_of_week=START_DOW,
                      hour=START_HOUR, minute=START_MINUTE)
    scheduler.add_job(stop_job, 'cron',
                      day=STOP_DAY, day_of_week=STOP_DOW,
                      hour=STOP_HOUR, minute=STOP_MINUTE)
    # scheduler.add_job(watchdog_job, 'cron', minute='*/5')

    scheduler.start()
    log("定时任务已注册:")
    log(f"  关闭策略: 每月第一个周五 {STOP_HOUR:02d}:{STOP_MINUTE:02d}")
    log(f"  启动策略: 每月第一个周五 {START_HOUR:02d}:{START_MINUTE:02d}")

    try:
        while True:
            time.sleep(3600)  # 每小时打印一次心跳，保持主线程存活
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            status = "运行中" if find_strategy_pids() else "未运行"
            log(f"心跳 — 策略状态: {status} — {now}")
    except (KeyboardInterrupt, SystemExit):
        log("收到退出信号")
    finally:
        log("正在清理...")
        stop_strategy()
        scheduler.shutdown(wait=False)
        log("管理器已退出")


if __name__ == "__main__":
    main()
