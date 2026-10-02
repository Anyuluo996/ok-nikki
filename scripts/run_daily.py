"""headless 运行一键日常(手动驱动, 需以管理员运行: 游戏进程是 admin, 否则输入被 UIPI 丢弃)。

用法(管理员 PowerShell):
  .venv\\Scripts\\python.exe scripts\\run_daily.py
"""
import os
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ok import OK, og

from src.config import config


def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    c = dict(config)
    c.pop('gui', None)
    c['use_gui'] = False
    c['onetime_tasks'] = []
    ok = OK(c)
    dm = ok.device_manager
    dm.do_refresh(True)
    if dm.get_preferred_device() is None:
        dm.set_preferred_device()
    dm.do_start()
    executor = ok.task_executor
    executor.start()
    og.app = ok

    from src.tasks.DailyTask import DailyTask
    from src.tasks.CalendarTask import CalendarTask
    tasks = []
    for cls in (DailyTask, CalendarTask):
        t = cls(executor=executor, app=ok.headless_app)
        t.after_init(executor=executor, scene=executor.scene)
        t.post_init()
        tasks.append(t)
    task = tasks[0] # watchdog 引用

    stop = threading.Event()

    def watchdog():
        # 页面切换瞬间窗口 visible 会翻转, pynput 的截图等待可能死锁; 周期性拉回前台解卡
        while not stop.is_set():
            stop.wait(8)
            if stop.is_set():
                break
            try:
                hw = dm.hwnd_window
                if not hw.is_foreground():
                    task.force_foreground()
            except Exception:
                pass

    def run_all():
        for t in tasks:
            if t.config.get('_enabled', True):
                t.run()

    watcher = threading.Thread(target=watchdog, daemon=True)
    watcher.start()
    runner = threading.Thread(target=run_all, daemon=True)
    runner.start()
    runner.join(timeout=600) # 10 分钟总超时
    stop.set()
    print('RUN DAILY DONE', flush=True)
    time.sleep(1)
    os._exit(0) # executor 线程非 daemon, 强退防僵尸


if __name__ == '__main__':
    main()
