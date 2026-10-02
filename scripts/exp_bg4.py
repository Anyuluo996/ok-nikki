"""后台执行验证 v4: 键盘序列深测 + 顶栏图标定位点击。
Phase1 前台确保大世界 → Phase2 后台:
  A posted esc 完整序列(KEYDOWN+CHAR+KEYUP)能否开菜单
  B WM_SYSKEYDOWN esc 能否开菜单
  C 点 ESC 小鸡图标(60,45)能否开菜单
  D posted j 完整序列能否打开奇想日历
  E 固定坐标点奇想日历图标(1550,55) → dump 日历页+领取按钮
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
    return boxes


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
    gi = dm.interaction
    assert isinstance(gi, GenshinInteraction), f'interaction is {type(dm.interaction)}'

    def click(x, y, down_time=0.15):
        pos = win32api.MAKELONG(int(x), int(y))
        gi.post(win32con.WM_MOUSEMOVE, 0, pos)
        time.sleep(0.05)
        gi.post(win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, pos)
        time.sleep(down_time)
        gi.post(win32con.WM_LBUTTONUP, 0, pos)

    def key_full(key, down_time=0.15):
        """WM_KEYDOWN + WM_CHAR + KEYUP 完整序列"""
        vk = gi.get_key_by_str(key)
        sc = win32api.MapVirtualKey(vk, 0)
        gi.post(win32con.WM_KEYDOWN, vk, 0x1e0001 | (sc << 16))
        gi.post(win32con.WM_CHAR, vk, 0x1e0001)
        time.sleep(down_time)
        gi.post(win32con.WM_KEYUP, vk, 0xc01e0001 | (sc << 16))

    def key_sys(key, down_time=0.15):
        """WM_SYSKEYDOWN/UP 序列(esc=菜单键)"""
        vk = gi.get_key_by_str(key)
        sc = win32api.MapVirtualKey(vk, 0)
        lp = 0x1e0001 | (sc << 16)
        gi.post(win32con.WM_SYSKEYDOWN, vk, lp)
        time.sleep(down_time)
        gi.post(win32con.WM_SYSKEYUP, vk, lp | 0xc0000000)

    from src.tasks.MyBaseTask import MyBaseTask
    task = MyBaseTask(executor=executor, app=ok.headless_app)
    task.after_init(executor=executor, scene=executor.scene)
    task.post_init()

    hw = dm.hwnd_window

    # Phase 1: 前台 pynput 确保大世界
    from ok.device.interaction_methods.pynput import PynputInteraction
    try:
        pn = PynputInteraction(dm.capture_method, hw)
    except TypeError:
        pn = PynputInteraction(dm.capture_method)
    dm.interaction = pn
    task.ensure_foreground()
    arm(200, 'ensure_in_game')
    task.ensure_in_game()
    task.close_pause_menu()
    disarm()
    print(f'PHASE1 fg menu_open={bool(task.ocr(match=task.MENU_MARKERS))}', flush=True)

    # Phase 2: 后台
    dm.interaction = gi
    focus_desktop()
    time.sleep(2)
    gi.activate()
    time.sleep(1)
    arm(60, 'phase2')
    dump(task, 'p2_world')
    disarm()

    # A: posted esc 完整序列开菜单
    arm(45, 'testA_esc_full')
    key_full('esc')
    time.sleep(2)
    boxes = dump(task, 'pA_after_esc')
    menu = any(re.search('美鸭梨', b.name) for b in boxes)
    print(f'TEST-A esc full-seq menu_open={menu}', flush=True)

    # B: SYSKEYDOWN esc
    if not menu:
        key_sys('esc')
        time.sleep(2)
        boxes = dump(task, 'pB_after_sysesc')
        menu = any(re.search('美鸭梨', b.name) for b in boxes)
        print(f'TEST-B esc sys-seq menu_open={menu}', flush=True)

    # C: 点小鸡图标
    if not menu:
        click(60, 45)
        time.sleep(2)
        boxes = dump(task, 'pC_after_icon')
        menu = any(re.search('美鸭梨', b.name) for b in boxes)
        print(f'TEST-C esc icon click menu_open={menu}', flush=True)

    # 关菜单(点击菜单空隙已知可关) 回世界
    if menu:
        click(178, 312)
        time.sleep(2)
        boxes = dump(task, 'p_menu_closed')
        print(f'MENU-CLOSE click gap → menu_closed={not any(re.search("美鸭梨", b.name) for b in boxes)}', flush=True)

    # D: posted j 完整序列开奇想日历
    arm(45, 'testD_key_j')
    key_full('j')
    time.sleep(2.5)
    boxes = dump(task, 'pD_after_j')
    cal = any(('奇想日历' in b.name or '每日' in b.name or '活跃' in b.name) for b in boxes)
    print(f'TEST-D key j calendar_open={cal}', flush=True)
    if cal:
        click(960, 1040)  # 关不掉就点空白, 下一轮再校准关闭方式
        key_full('esc')
        time.sleep(2)

    # E: 固定坐标点奇想日历图标
    arm(90, 'testE_cal_icon')
    click(1550, 55)
    time.sleep(3)
    boxes = dump(task, 'pE_calendar')
    cal = any(('奇想日历' in b.name or '每日' in b.name or '活跃' in b.name or '任务' in b.name) for b in boxes)
    print(f'TEST-E icon click calendar_open={cal}', flush=True)
    claims = [b for b in boxes if re.search('一键领取|全部领取|领取|收下', b.name)]
    print(f'TEST-E claim buttons: {[(b.name, b.x, b.y, b.width, b.height) for b in claims]}', flush=True)
    if claims:
        task.executor.interaction.click(claims[0].x + claims[0].width / 2, claims[0].y + claims[0].height / 2)
        time.sleep(2)
        dump(task, 'pE_after_claim')

    gi.deactivate()
    dm.interaction = pn
    task.ensure_foreground()
    for _ in range(3):
        if not task.ocr(match=task.MENU_MARKERS):
            break
        task.send_key('esc', after_sleep=1.2)
    print('SESSION DONE', flush=True)
    time.sleep(1)
    os._exit(0)


if __name__ == '__main__':
    main()
