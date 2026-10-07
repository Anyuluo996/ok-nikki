"""后台执行验证 v3: 纯点击流(定时 PostMessage), 不依赖键盘。
Phase1 前台(pynput)确保大世界 → Phase2 切后台+activate 确认世界栏可见
→ Phase3 后台点击顶栏「奇想日历」→ dump 页面+找领取 → 尝试领取 → 关页面
→ Phase4 后台点左上 ESC 按钮开菜单 → 点「美鸭梨挖掘」→ dump 页面 → 关页面。
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


def find_box(task, pattern, y_max=1.0):
    p = re.compile(pattern)
    for b in task.ocr(log=False):
        if p.search(b.name) and b.y + b.height / 2 < y_max * 1080:
            return b
    return None


def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    threading.Thread(target=watchdog, daemon=True).start()

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

    # 定时 PostMessage 点击: move 悬停 → down → 间隔 → up, 不动真实鼠标
    import win32api
    import win32con

    def nikki_click(x=-1, y=-1, move_back=False, name=None, down_time=0.15, move=True, key='left'):
        if x < 0 or y < 0:
            x, y = 960, 540
        pos = win32api.MAKELONG(int(x), int(y))
        gi.post(win32con.WM_MOUSEMOVE, 0, pos)
        time.sleep(0.05)
        gi.post(win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, pos)
        time.sleep(max(down_time, 0.15))
        gi.post(win32con.WM_LBUTTONUP, 0, pos)
        if name:
            print(f'nikki_click {name} ({int(x)},{int(y)})', flush=True)

    def nikki_send_key(key, down_time=0.15, **kwargs):
        vk = gi.get_key_by_str(key)
        gi.post(win32con.WM_KEYDOWN, vk, 0x1e0001)
        time.sleep(down_time)
        gi.post(win32con.WM_KEYUP, vk, 0xc01e0001)

    gi.click = nikki_click
    gi.send_key = nikki_send_key

    from src.tasks.MyBaseTask import MyBaseTask
    task = MyBaseTask(executor=executor, app=ok.headless_app)
    task.after_init(executor=executor, scene=executor.scene)
    task.post_init()

    hw = dm.hwnd_window

    # Phase 1: 前台用 pynput 确保大世界(pynput 真实输入键盘可用)
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
    menu = task.ocr(match=task.MENU_MARKERS)
    print(f'PHASE1 fg menu_open={bool(menu)}', flush=True)
    if menu:
        print('SESSION DONE (menu stuck in fg)', flush=True)
        os._exit(3)

    # Phase 2: 切后台, 换 Genshin(定时点击) + activate
    dm.interaction = gi
    focus_desktop()
    time.sleep(2)
    gi.activate()
    time.sleep(1)
    arm(60, 'phase2_frame')
    boxes = dump(task, 'p2_world')
    disarm()
    topbar = [b.name for b in boxes if b.y + b.height / 2 < 130]
    print(f'PHASE2 fg={hw.is_foreground()} topbar={json.dumps(topbar, ensure_ascii=False)}', flush=True)

    # Phase 3: 后台点击顶栏「奇想日历」
    try:
        arm(150, 'phase3_calendar')
        entry = find_box(task, '奇想日历', y_max=0.12)
        if entry:
            task.click_box(entry, after_sleep=3)
            boxes = dump(task, 'p3_calendar')
            in_cal = any(('奇想日历' in b.name or '每日' in b.name or '活跃' in b.name for b in boxes))
            print(f'PHASE3 calendar page open={in_cal}', flush=True)
            claims = [b for b in task.ocr(log=False) if re.search('一键领取|全部领取|领取|收下', b.name)]
            print(f'PHASE3 claim buttons: {[(b.name, b.x, b.y, b.width, b.height) for b in claims]}', flush=True)
            if claims:
                task.click_box(claims[0], after_sleep=2)
                task.confirm_dialog()
                boxes = dump(task, 'p3_after_claim')
            # 关页面: 找关闭/返回按钮
            close = find_box(task, '返回|关闭|^X$|ESC')
            if close:
                task.click_box(close, after_sleep=2)
            else:
                task.click(0.062, 0.044, after_sleep=2)  # 左上角返回箭头常见位
            boxes = dump(task, 'p3_after_close')
            back_world = any(b.name == '奇想日历' and b.y < 130 for b in boxes)
            print(f'PHASE3 back_to_world={back_world}', flush=True)
        else:
            print('PHASE3 RESULT: topbar 奇想日历 not found', flush=True)
    finally:
        disarm()

    # Phase 4: 后台开菜单 → 美鸭梨挖掘
    try:
        arm(150, 'phase4_mine')
        esc_btn = find_box(task, r'^ESC$', y_max=0.12)
        if not esc_btn:
            print('PHASE4 RESULT: ESC button not found', flush=True)
        else:
            task.click_box(esc_btn, after_sleep=2.5)
            boxes = dump(task, 'p4_menu')
            menu = [b for b in boxes if re.search('美鸭梨', b.name)]
            print(f'PHASE4 menu open={bool(menu)}', flush=True)
            mine = find_box(task, '美鸭梨挖掘')
            if mine:
                task.click_box(mine, after_sleep=3)
                boxes = dump(task, 'p4_mine_page')
                mine_ui = [b.name for b in boxes if re.search('领取|挖掘|剩余|次数|时间', b.name)]
                print(f'PHASE4 mine ui: {json.dumps(mine_ui, ensure_ascii=False)}', flush=True)
                btn = find_box(task, '继续挖掘|开始挖掘|领取')
                if btn:
                    task.click_box(btn, after_sleep=2)
                    task.confirm_dialog()
                    boxes = dump(task, 'p4_mine_after')
                # 关页面回菜单
                close = find_box(task, '返回|关闭|^X$|ESC')
                if close:
                    task.click_box(close, after_sleep=2)
                # 关菜单回世界
                close2 = find_box(task, r'^ESC$', y_max=0.12)
                if close2:
                    task.click_box(close2, after_sleep=2)
                boxes = dump(task, 'p4_final')
                print(f'PHASE4 final world={"奇想日历" in [b.name for b in boxes]}', flush=True)
            else:
                print('PHASE4 RESULT: 美鸭梨挖掘 entry not found in menu', flush=True)
    finally:
        disarm()

    gi.deactivate()
    # 收尾: 回前台用 pynput 清理页面状态
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
