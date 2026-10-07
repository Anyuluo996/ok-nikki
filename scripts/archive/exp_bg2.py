"""后台执行验证 v2: 定时(带间隔)PostMessage 点击/按键 + WM_ACTIVATE 保活。
Phase1 前台关菜单确认大世界 → Phase2 切后台+activate, 看失焦是否自动弹菜单
→ Phase3 后台定时 esc 能否关菜单 → Phase4 后台定时点击商城, 验证页面打开。
"""
import json
import os
import re
import sys
import time
import threading

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ok import OK, og

from src.config import config

WATCH = {'deadline': 0.0, 'name': ''}


def watchdog():
    while True:
        time.sleep(5)
        if WATCH['deadline'] and time.time() > WATCH['deadline']:
            print(f'WATCHDOG timeout: {WATCH["name"]}', flush=True)
            os._exit(2)


def arm(seconds, name):
    WATCH['deadline'] = time.time() + seconds
    WATCH['name'] = name


def disarm():
    WATCH['deadline'] = 0.0


def focus_desktop():
    import win32api
    import win32con
    import win32gui
    import win32process
    win32api.keybd_event(win32con.VK_MENU, 0, 0, 0)
    win32api.keybd_event(win32con.VK_MENU, 0, win32con.KEYEVENTF_KEYUP, 0)
    fg = win32gui.GetForegroundWindow()
    fg_tid = win32process.GetWindowThreadProcessId(fg)[0] if fg else 0
    cur_tid = win32api.GetCurrentThreadId()
    fg_tid and win32process.AttachThreadInput(cur_tid, fg_tid, True)
    try:
        for cls in ('Progman', 'Shell_TrayWnd'):
            hwnd = win32gui.FindWindow(cls, None)
            if not hwnd:
                continue
            try:
                win32gui.SetForegroundWindow(hwnd)
            except Exception as e:
                print(f'focus {cls} failed: {e}', flush=True)
                continue
            if win32gui.GetForegroundWindow() == hwnd:
                break
    finally:
        fg_tid and win32process.AttachThreadInput(cur_tid, fg_tid, False)


def dump(task, tag):
    task.next_frame()
    task.screenshot(name=f'exp_{tag}')
    boxes = task.ocr(log=False)
    texts = [b.name for b in boxes]
    print(f'EXP {tag}: {len(texts)} boxes', flush=True)
    print('EXP-TEXTS ' + json.dumps(texts, ensure_ascii=False), flush=True)
    return texts


def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    threading.Thread(target=watchdog, daemon=True).start()

    import win32api
    import win32con

    c = dict(config)
    c.pop('gui', None)
    c['use_gui'] = False
    c['onetime_tasks'] = []
    c['windows'] = dict(config['windows'])
    c['windows']['interaction'] = ['Genshin', 'Pynput', 'PostMessage', 'PyDirect']
    ok = OK(c)
    dm = ok.device_manager
    dm.do_refresh(True)
    if dm.get_preferred_device() is None:
        dm.set_preferred_device()
    dm.do_start()
    executor = ok.task_executor
    executor.start()
    og.app = ok

    from ok.device.interaction_methods.genshin import GenshinInteraction
    assert isinstance(dm.interaction, GenshinInteraction), f'interaction is {type(dm.interaction)}'
    gi = dm.interaction
    print('PART-0 interaction = GenshinInteraction', flush=True)

    from src.tasks.MyBaseTask import MyBaseTask
    task = MyBaseTask(executor=executor, app=ok.headless_app)
    task.after_init(executor=executor, scene=executor.scene)
    task.post_init()

    hw = dm.hwnd_window

    def timed_click(x, y, down_time=0.15):
        """定时 PostMessage 点击: move 悬停 → down → 间隔 → up"""
        pos = win32api.MAKELONG(int(x), int(y))
        gi.post(win32con.WM_MOUSEMOVE, 0, pos)
        time.sleep(0.05)
        gi.post(win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, pos)
        time.sleep(down_time)
        gi.post(win32con.WM_LBUTTONUP, 0, pos)

    def timed_key(key, down_time=0.15):
        vk = gi.get_key_by_str(key)
        gi.post(win32con.WM_KEYDOWN, vk, 0x1e0001)
        time.sleep(down_time)
        gi.post(win32con.WM_KEYUP, vk, 0xc01e0001)

    def find_text(texts, pattern):
        p = re.compile(pattern)
        for b in task.ocr(log=False):
            if p.search(b.name):
                return b
        return None

    # Phase 1: 前台关菜单, 确认大世界
    task.ensure_foreground()
    arm(200, 'ensure_in_game')
    task.ensure_in_game()
    task.close_pause_menu()
    disarm()
    menu = task.ocr(match=task.MENU_MARKERS)
    print(f'PHASE1 fg menu_open={bool(menu)}', flush=True)

    # Phase 2: 切后台 + activate
    focus_desktop()
    time.sleep(2)
    gi.activate()
    time.sleep(1)
    arm(60, 'phase2_frame')
    texts = dump(task, 'p2_bg')
    disarm()
    menu = task.ocr(match=task.MENU_MARKERS)
    print(f'PHASE2 fg={hw.is_foreground()} menu_auto_open={bool(menu)}', flush=True)

    # Phase 3: 后台定时 esc 关菜单
    if menu:
        for i in range(3):
            timed_key('esc')
            time.sleep(1.5)
            if not task.ocr(match=task.MENU_MARKERS):
                print(f'PHASE3 RESULT: ESC WORKS (try {i+1})', flush=True)
                break
        else:
            print('PHASE3 RESULT: ESC NOT WORKING', flush=True)
    else:
        print('PHASE3 RESULT: no menu to close (skip)', flush=True)

    # Phase 4: 后台定时点击商城
    try:
        arm(90, 'phase4_shop')
        entry = find_text(texts, '商城')
        if not entry:
            entry = task.ocr(match=re.compile('商城'), log=True)
            entry = entry[0] if entry else None
        if entry:
            print(f'PHASE4 timed click shop at ({entry.x},{entry.y})', flush=True)
            timed_click(entry.x + entry.width / 2, entry.y + entry.height / 2)
            time.sleep(3)
            texts = dump(task, 'p4_after_click')
            in_shop = any((k in t for t in texts for k in ('星途珍存', '候鸟轨迹', '循星任务', '清空购物车', '历史低价', '兑换中心', '领取')))
            print(f'PHASE4 RESULT: {"SHOP OPEN (click WORKS)" if in_shop else "NOT WORKING"}', flush=True)
            if in_shop:
                for _ in range(4):
                    timed_key('esc')
                    time.sleep(1.2)
                    if task.ocr(match=task.MENU_MARKERS) or not any(
                            (k in t for t in task.ocr(log=False) for k in ('星途珍存', '兑换'))):
                        break
        else:
            print('PHASE4 RESULT: shop entry not found', flush=True)
    finally:
        disarm()

    gi.deactivate()
    task.ensure_foreground()
    print('SESSION DONE', flush=True)
    time.sleep(1)
    os._exit(0)


if __name__ == '__main__':
    main()
