"""一键日常入口: 邮件+挖掘(同菜单接力) → 奇想日历+朝夕心愿+幻境挑战(同页面接力)
→ 通行证 → 关闭游戏。
幻境默认一键最大次数耗光活跃能量(Drain Energy), 耗完回日历补领新达标的里程碑奖励。

用法:
  python scripts/run_daily.py            # 后台模式: 不抢前台鼠标(WM_ACTIVATE 保活渲染)
  python scripts/run_daily.py --fg       # 前台模式: 保持游戏前台, 定时任务/最稳推荐
  python scripts/run_daily.py --dry-run  # 演练: 幻境不注入体力
  python scripts/run_daily.py --keep-game # 跑完保留游戏进程(调试用)

前置: 游戏已启动(建议窗口化), 本脚本需管理员运行(游戏是 admin, 否则输入被 UIPI 丢弃)。
"""
import argparse
import os
import subprocess
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ok import OK, og

from src.config import config


def click_launcher_start_button():
    """官方启动器(xstarter, 标题「无限暖暖」)右下角的「启动游戏」按钮, 按窗口比例点击
    (游戏本体窗口类是 UnrealWindow, 在此排除; 比例坐标与 DPI 无关)"""
    import win32api
    import win32con
    import win32gui
    target = None

    def enum_handler(hwnd, _):
        nonlocal target
        if win32gui.IsWindowVisible(hwnd) and win32gui.GetWindowText(hwnd) == '无限暖暖' \
                and win32gui.GetClassName(hwnd) != 'UnrealWindow':
            target = hwnd

    try:
        win32gui.EnumWindows(enum_handler, None)
    except Exception:
        return False
    if not target:
        return False
    left, top, right, bottom = win32gui.GetWindowRect(target)
    x = int(left + (right - left) * 0.834)
    y = int(top + (bottom - top) * 0.889)
    win32api.SetCursorPos((x, y))
    time.sleep(0.2)
    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
    time.sleep(0.15)
    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
    return True


def find_official_launcher(exe_path):
    """官方启动器 launcher.exe 在游戏根目录(游戏 exe 上溯 4 级), 直启 exe 无效时兜底"""
    d = os.path.dirname(exe_path)
    for _ in range(4):
        d = os.path.dirname(d)
        cand = os.path.join(d, 'launcher.exe')
        if os.path.exists(cand):
            return cand
    return None


def close_game():
    """跑完关游戏: 强制终止游戏本体和残留启动器(游戏为服务器存档, 无本地进度风险)"""
    for exe in ('X6Game-Win64-Shipping.exe', 'xstarter.exe'):
        try:
            r = subprocess.run(['taskkill', '/IM', exe, '/F'],
                               capture_output=True, text=True)
            print(f'close game: taskkill {exe} rc={r.returncode}', flush=True)
        except Exception as e:
            print(f'close game: {exe} error: {e}', flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--fg', action='store_true', help='前台模式: 保持游戏窗口前台(定时任务推荐)')
    parser.add_argument('--dry-run', action='store_true', help='演练: 幻境不注入体力')
    parser.add_argument('--keep-game', action='store_true', help='跑完后保留游戏进程(调试用)')
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

    # —— 自动拉起游戏: 窗口不在时用记住的完整路径启动 ——
    # 直启 exe 会先弹官方启动器(xstarter), 需代点「启动游戏」; 之后才是真正的游戏窗口
    if not (dm.hwnd_window and dm.hwnd_window.hwnd):
        device = dm.get_preferred_device()
        exe_path = (device or {}).get('full_path') or (device or {}).get('pc_full_path')
        if exe_path and os.path.exists(exe_path):
            print(f'game not running, launching: {exe_path}', flush=True)
            subprocess.Popen([exe_path], cwd=os.path.dirname(exe_path))
            launcher_exe = find_official_launcher(exe_path)
            launcher_started = False
            launch_t0 = time.time()
            clicks = 0
            last_click = 0.0
            deadline = launch_t0 + 600 # 冷启动+启动器+进游戏窗口, 留足余量
            while time.time() < deadline:
                time.sleep(3)
                dm.do_refresh(True)
                if dm.hwnd_window and dm.hwnd_window.hwnd:
                    print(f'game window found after {int(time.time()-launch_t0)}s', flush=True)
                    break
                # 直启 exe 静默失败(新版本不再自动弹启动器)时, 20s 后改拉官方启动器
                if not launcher_started and launcher_exe and time.time() - launch_t0 > 20:
                    print(f'game window still missing, starting official launcher: {launcher_exe}', flush=True)
                    subprocess.Popen([launcher_exe], cwd=os.path.dirname(launcher_exe))
                    launcher_started = True
                # 启动器出现后代点「启动游戏」(最多 3 次, 间隔 15s)
                if clicks < 3 and time.time() - launch_t0 > 12 and time.time() - last_click > 15:
                    if click_launcher_start_button():
                        clicks += 1
                        last_click = time.time()
                        print(f'clicked launcher start button (#{clicks})', flush=True)
            else:
                print('LAUNCH TIMEOUT: game window did not appear in 600s', flush=True)
        else:
            print(f'game not running and exe path unknown: {exe_path}', flush=True)

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

    def step(name, fn, retries=3):
        """跑一个步骤: 失败退回大世界重试; 多次仍失败则存截图并中止后续步骤(不静默跳过)"""
        for attempt in range(1, retries + 1):
            try:
                if fn():
                    return True
            except Exception as e:
                print(f'{name}: attempt {attempt} error: {e}', flush=True)
            print(f'{name}: attempt {attempt} failed, back to world and retry.', flush=True)
            try:
                base.back_to_world()
            except Exception:
                pass
        base.debug_screenshot(f'nikki_{name}_stuck')
        print(f'{name}: stuck after {retries} attempts, screenshot saved, stop.', flush=True)
        return False

    # —— 步骤 1: 菜单组(邮件+挖掘)。入口同在美鸭梨菜单, 开一次菜单做完再回世界 ——
    # 冷启动时游戏可能还停在登录页, 必须先推进到大世界再开菜单
    # 挖掘网格入口只认真实点击, 强制允许抢前台(用户配置里存了 False 也覆盖)
    mine_overrides = {'Allow Foreground Steal': True}

    def menu_chain():
        if not (base.ensure_in_game() and base.open_pause_menu()):
            return False
        ok_mail = build(DailyTask).claim_mail_flow(leave_menu_open=True)
        ok_mine = build(MineTask, **mine_overrides).mine_flow()
        base.close_pause_menu()
        return ok_mail or ok_mine

    # —— 步骤 2: 日历组(日历领取+朝夕心愿→幻境耗体力→回日历补领里程碑) ——
    # 幻境一键最大次数耗光活跃能量(40/次), dry-run 只演练不注入
    realm_overrides = {'Drain Energy': True, 'Challenge Count': 99}
    if args.dry_run:
        realm_overrides['Dry Run'] = True

    def calendar_realm_chain():
        if not base.ensure_in_game():
            return False
        cal = build(CalendarTask)
        if not cal.calendar_flow():
            return False
        build(RealmTask, **realm_overrides).realm_flow()
        # 耗完体力后朝夕活跃度里程碑/日历奖励会有新达标档位, 重跑一次日历领取
        if not build(CalendarTask).calendar_flow():
            return False
        return base.back_to_world()

    # —— 步骤 3: 通行证(J 打开奇迹之旅领奖励, 需在大世界) ——
    from src.tasks.PassportTask import PassportTask

    def passport_chain():
        if not base.ensure_in_game():
            return False
        build(PassportTask).run()
        return True

    if step('daily_menu', menu_chain):
        if step('calendar_realm', calendar_realm_chain):
            step('passport', passport_chain)
        else:
            print('daily chain: abort after calendar_realm stuck.', flush=True)
    else:
        print('daily chain: abort after daily_menu stuck.', flush=True)

    stop.set()
    try:
        dm.interaction.deactivate()
    except Exception:
        pass
    if not args.keep_game:
        close_game()
    print('RUN DAILY DONE', flush=True)
    time.sleep(1)
    os._exit(0) # executor 线程非 daemon, 强退防僵尸


if __name__ == '__main__':
    main()
