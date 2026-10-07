"""后台全链验证 v6: 修 v5 三个问题。
  A L 键开奇想日历(J=奇迹之旅) → 校验页面 → 点领取 → confirm → esc 回世界
  B 菜单「美鸭梨挖掘」点标签上方图标热区 → dump 挖掘页 → 领取/继续挖掘
  C 菜单底部信封固定坐标 (0.447,0.930) → 邮件页 → 领取全部
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
        sc = win32api.MapVirtualKey(vk & 0xff, 0)
        gi.post(win32con.WM_KEYDOWN, vk, 0x1e0001 | (sc << 16))
        gi.post(win32con.WM_CHAR, vk, 0x1e0001)
        time.sleep(down_time)
        gi.post(win32con.WM_KEYUP, vk, 0xc01e0001 | (sc << 16))

    gi.click = nikki_click
    gi.send_key = nikki_send_key

    from src.tasks.MyBaseTask import MyBaseTask
    task = MyBaseTask(executor=executor, app=ok.headless_app)
    task.after_init(executor=executor, scene=executor.scene)
    task.post_init()

    hw = dm.hwnd_window

    # Phase 1: 前台确保大世界
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

    # A: 奇想日历 (J=奇迹之旅, L=奇想日历 per Whimbox)
    try:
        arm(180, 'phaseA_calendar')
        opened = False
        for k in ('l', 'j'):
            task.send_key(k, after_sleep=2.5)
            boxes = dump(task, f'pA_key_{k}')
            joined = ' '.join(b.name for b in boxes)
            ok_page = ('奇想日历' in joined) or ('每日' in joined and '阅历' not in joined)
            if ok_page:
                print(f'PHASE-A key {k} opened calendar', flush=True)
                opened = True
                break
            task.send_key('esc', after_sleep=1.5)
        if not opened:
            # 兜底: OCR 顶栏标签点击
            entry = next((b for b in task.ocr(log=False) if '奇想日历' in b.name and b.y < 130), None)
            if entry:
                task.click_box(entry, after_sleep=3)
                boxes = dump(task, 'pA_by_click')
                opened = any(('奇想日历' in b.name or '活跃' in b.name for b in boxes))
                print(f'PHASE-A strip click opened calendar={opened}', flush=True)
        if opened:
            claims = [b for b in task.ocr(log=False) if re.search('一键领取|全部领取|领取|收下', b.name)]
            print(f'PHASE-A claim buttons: {[(b.name, b.x, b.y, b.width, b.height) for b in claims]}', flush=True)
            if claims:
                task.click_box(claims[0], after_sleep=2)
                task.confirm_dialog()
                dump(task, 'pA_after_claim')
            else:
                print('PHASE-A no claim button visible (可能已领完)', flush=True)
            task.send_key('esc', after_sleep=2)
            boxes = dump(task, 'pA_back_world')
            print(f'PHASE-A closed={"黄金乡" in " ".join(b.name for b in boxes) or not any(("奇想日历" in b.name or "活跃" in b.name) for b in boxes)}', flush=True)
        else:
            print('PHASE-A RESULT: calendar NOT opened', flush=True)
    finally:
        disarm()

    # B: 美鸭梨挖掘
    try:
        arm(180, 'phaseB_mine')
        task.open_pause_menu()
        boxes = dump(task, 'pB_menu')
        mine = next((b for b in boxes if '美鸭梨挖掘' in b.name), None)
        if mine:
            # 菜单项是图标热区, 点标签上方图标
            task.click(mine.x + mine.width / 2, mine.y - 40, down_time=0.15, after_sleep=3)
            boxes = dump(task, 'pB_mine_page')
            ui = [b.name for b in boxes if re.search('领取|挖掘|剩余|次数|时间|可', b.name)]
            print(f'PHASE-B mine ui: {json.dumps(ui, ensure_ascii=False)}', flush=True)
            btn = next((b for b in boxes if re.search('继续挖掘|开始挖掘|一键领取|领取', b.name)), None)
            if btn:
                task.click_box(btn, after_sleep=2)
                task.confirm_dialog()
                dump(task, 'pB_mine_after')
            else:
                print('PHASE-B no dig/claim button visible', flush=True)
            task.send_key('esc', after_sleep=1.5)
            task.send_key('esc', after_sleep=1.5)
        else:
            print('PHASE-B RESULT: 美鸭梨挖掘 not found in menu', flush=True)
    finally:
        disarm()

    # C: 邮件 (信封按钮无文字, 用固定坐标; 领取全部坐标来自 DailyTask 实测)
    MAIL_ICON_POS = (0.447, 0.930)
    CLAIM_ALL_POS = (0.292, 0.947)
    try:
        arm(180, 'phaseC_mail')
        task.open_pause_menu()
        dump(task, 'pC_menu')
        task.click(*MAIL_ICON_POS, down_time=0.15, after_sleep=2.5)
        boxes = dump(task, 'pC_mail_page')
        in_mail = any(re.search('领取|系统邮件|好友邮件|删除', b.name) for b in boxes)
        print(f'PHASE-C mail page={in_mail}', flush=True)
        if in_mail:
            claim = next((b for b in boxes if re.search('一键领取|全部领取|领取全部', b.name)), None)
            if claim:
                task.click_box(claim, after_sleep=2)
                task.confirm_dialog()
                dump(task, 'pC_after_claim')
            else:
                print('PHASE-C no claim-all OCR, use fixed pos', flush=True)
                task.click(*CLAIM_ALL_POS, down_time=0.15, after_sleep=2)
                task.confirm_dialog()
                dump(task, 'pC_after_claim')
            task.send_key('esc', after_sleep=1.5)
            task.send_key('esc', after_sleep=1.5)
    finally:
        disarm()

    # 收尾: 关菜单回大世界
    for _ in range(3):
        boxes = dump(task, 'p_final')
        if not any(re.search('美鸭梨', b.name) for b in boxes):
            break
        task.send_key('esc', after_sleep=1.5)
    gi.deactivate()
    dm.interaction = pn
    task.ensure_foreground()
    print('SESSION DONE', flush=True)
    time.sleep(1)
    os._exit(0)


if __name__ == '__main__':
    main()
