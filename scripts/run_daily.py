"""一键日常入口: 邮件+挖掘(同菜单接力) → 奇想日历+朝夕心愿+幻境挑战(同页面接力)。

用法:
  python scripts/run_daily.py            # 后台模式: 不抢前台鼠标(WM_ACTIVATE 保活渲染)
  python scripts/run_daily.py --fg       # 前台模式: 保持游戏前台, 定时任务/最稳推荐
  python scripts/run_daily.py --dry-run  # 演练: 幻境不注入体力

前置: 游戏已启动(建议窗口化), 本脚本需管理员运行(游戏是 admin, 否则输入被 UIPI 丢弃)。
"""
import argparse
import os
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ok import OK, og

from src.config import config


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--fg', action='store_true', help='前台模式: 保持游戏窗口前台(定时任务推荐)')
    parser.add_argument('--dry-run', action='store_true', help='演练: 幻境不注入体力')
    args = parser.parse_args()

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

    from src.tasks.MyBaseTask import MyBaseTask
    base = MyBaseTask(executor=executor, app=ok.headless_app)
    base.after_init(executor=executor, scene=executor.scene)
    base.post_init()

    stop = threading.Event()

    def watchdog():
        if args.fg:
            # 前台模式: 周期性把游戏拉回前台(页面切换瞬间 visible 翻转可能丢焦点)
            while not stop.is_set():
                stop.wait(8)
                try:
                    if not dm.hwnd_window.is_foreground():
                        base.force_foreground()
                except Exception:
                    pass
        else:
            # 后台模式: 最小化时 WGC 拿不到帧, 恢复窗口但不抢前台
            import win32con
            import win32gui
            while not stop.is_set():
                stop.wait(8)
                try:
                    hwnd = dm.hwnd_window.hwnd
                    if win32gui.IsIconic(hwnd):
                        win32gui.ShowWindow(hwnd, win32con.SW_SHOWNOACTIVATE)
                except Exception:
                    pass

    threading.Thread(target=watchdog, daemon=True).start()

    # 后台模式: WM_ACTIVATE 假激活, 让 UE5 失焦也继续渲染(否则 WGC 永远等不到帧)
    if not args.fg:
        try:
            dm.interaction.activate()
        except Exception:
            pass

    from src.tasks.MineTask import MineTask
    from src.tasks.DailyTask import DailyTask
    from src.tasks.CalendarTask import CalendarTask
    from src.tasks.RealmTask import RealmTask

    def build(cls, **config_overrides):
        task = cls(executor=executor, app=ok.headless_app)
        task.after_init(executor=executor, scene=executor.scene)
        task.post_init()
        for k, v in config_overrides.items():
            task.config[k] = v
        return task

    def run_one(cls, retries=2, **config_overrides):
        """带重试跑任务: 每次尝试失败后回大世界再战"""
        for attempt in range(1, retries + 1):
            try:
                task = build(cls, **config_overrides)
                task.run()
                if base.back_to_world():
                    return True
                print(f'{cls.__name__}: attempt {attempt} stuck off-world, retrying', flush=True)
            except Exception as e:
                print(f'RUN ERROR {cls.__name__} attempt {attempt}: {e}', flush=True)
                try:
                    base.back_to_world()
                except Exception:
                    pass
        return False

    # —— 菜单组: 邮件和挖掘入口同在美鸭梨菜单, 开一次菜单做完再回世界 ——
    chain_done = False
    try:
        if base.open_pause_menu():
            ok_mail = build(DailyTask).claim_mail_flow(leave_menu_open=True)
            ok_mine = build(MineTask).mine_flow()
            base.close_pause_menu()
            chain_done = ok_mail or ok_mine
    except Exception as e:
        print(f'menu chain error: {e}', flush=True)
        try:
            base.back_to_world()
        except Exception:
            pass
    if not chain_done:
        run_one(DailyTask, **{'Claim Shop Free Pack': False}) # 商城暂不跑(用户要求)
        run_one(MineTask)

    # —— 日历组: 朝夕心愿和幻境挑战入口同在奇想日历页, 开一次日历做完再回世界 ——
    cal_done = False
    realm_overrides = {'Dry Run': True} if args.dry_run else {}
    try:
        cal = build(CalendarTask)
        if cal.calendar_flow():
            build(RealmTask, **realm_overrides).realm_flow()
            cal_done = True
            base.back_to_world()
    except Exception as e:
        print(f'calendar chain error: {e}', flush=True)
        try:
            base.back_to_world()
        except Exception:
            pass
    if not cal_done:
        run_one(CalendarTask)
        run_one(RealmTask, **realm_overrides)

    stop.set()
    try:
        dm.interaction.deactivate()
    except Exception:
        pass
    print('RUN DAILY DONE', flush=True)
    time.sleep(1)
    os._exit(0) # executor 线程非 daemon, 强退防僵尸


if __name__ == '__main__':
    main()
