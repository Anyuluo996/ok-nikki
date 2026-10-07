"""菜单激活方式微测 v7: 菜单项点击=翻页(疑似 select-not-activate), 测试三种激活方式。
先 posted WM_MOUSEMOVE 悬停到「美鸭梨挖掘」让选择框跟我们的光标走, 再依次试:
  1 Enter 键确认  2 双击  3 长按0.4s  4 space
每次尝试后 dump 判定是否进入挖掘页(特征: 出现 挖掘/剩余/领取 且无 商城 菜单标签)。
成功进入后 dump 全页(校准数据)并尝试 领取/继续挖掘, 最后 esc esc 回世界。
附: 信封(830,1000) 同样方式测邮件。
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

    def move(x, y):
        gi.post(win32con.WM_MOUSEMOVE, 0, win32api.MAKELONG(int(x), int(y)))
        time.sleep(0.1)

    def click(x, y, down_time=0.15):
        pos = win32api.MAKELONG(int(x), int(y))
        gi.post(win32con.WM_MOUSEMOVE, 0, pos)
        time.sleep(0.05)
        gi.post(win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, pos)
        time.sleep(down_time)
        gi.post(win32con.WM_LBUTTONUP, 0, pos)

    def dblclick(x, y):
        click(x, y, down_time=0.08)
        time.sleep(0.08)
        click(x, y, down_time=0.08)

    def key_full(key, down_time=0.12):
        vk = gi.get_key_by_str(key)
        sc = win32api.MapVirtualKey(vk & 0xff, 0)
        gi.post(win32con.WM_KEYDOWN, vk, 0x1e0001 | (sc << 16))
        gi.post(win32con.WM_CHAR, vk, 0x1e0001)
        time.sleep(down_time)
        gi.post(win32con.WM_KEYUP, vk, 0xc01e0001 | (sc << 16))

    from src.tasks.MyBaseTask import MyBaseTask
    task = MyBaseTask(executor=executor, app=ok.headless_app)
    task.after_init(executor=executor, scene=executor.scene)
    task.post_init()

    hw = dm.hwnd_window

    def is_mine_page(boxes):
        joined = ' '.join(b.name for b in boxes)
        return ('挖掘' in joined or '开采' in joined) and ('商城' not in joined)

    def ensure_menu_page1():
        """确保菜单在第一页(有商城标签), 不在就点左箭头"""
        for _ in range(2):
            boxes = task.ocr(log=False)
            if any('商城' in b.name and b.y < 400 for b in boxes):
                return True
            click(87, 513)  # ‹ 翻回
            time.sleep(1.5)
        return False

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

    try:
        arm(240, 'mine_activation')
        task.send_key('esc', after_sleep=2)
        boxes = dump(task, 'p7_menu')
        mine = next((b for b in boxes if '美鸭梨挖掘' in b.name), None)
        print(f'PHASE7 menu open={bool(mine)}', flush=True)

        opened = False
        if mine:
            cx, cy = mine.x + mine.width / 2, mine.y - 40  # 图标中心(标签上方)
            print(f'PHASE7 mine icon target=({cx:.0f},{cy:.0f})', flush=True)
            attempts = [
                ('hover+enter', lambda: (move(cx, cy), key_full('enter'))),
                ('dblclick', lambda: dblclick(cx, cy)),
                ('hold0.4', lambda: click(cx, cy, down_time=0.4)),
                ('hover+space', lambda: (move(cx, cy), key_full('space'))),
            ]
            for name, fn in attempts:
                # 每次尝试前确保菜单在第一页
                if not ensure_menu_page1():
                    print(f'PHASE7 {name}: menu stuck off page1, abort', flush=True)
                    break
                fn()
                time.sleep(2.5)
                boxes = dump(task, f'p7_after_{name.replace("+", "_")}')
                if is_mine_page(boxes):
                    print(f'PHASE7 ACTIVATION={name} WORKS!', flush=True)
                    opened = True
                    break
                if not any('美鸭梨' in b.name for b in boxes):
                    # 可能进入了别的页面, esc 回菜单
                    task.send_key('esc', after_sleep=1.5)

        if opened:
            ui = [b.name for b in task.ocr(log=False) if re.search('领取|挖掘|剩余|次数|时间|可|开始', b.name)]
            print(f'PHASE7 mine ui: {json.dumps(ui, ensure_ascii=False)}', flush=True)
            btn = next((b for b in task.ocr(log=False) if re.search('继续挖掘|开始挖掘|一键领取|领取', b.name)), None)
            if btn:
                click(btn.x + btn.width / 2, btn.y + btn.height / 2)
                time.sleep(2)
                task.confirm_dialog()
                dump(task, 'p7_mine_after')
            else:
                print('PHASE7 no dig/claim button', flush=True)
            task.send_key('esc', after_sleep=1.5)
            task.send_key('esc', after_sleep=1.5)
        else:
            print('PHASE7 RESULT: no activation method worked', flush=True)
            task.send_key('esc', after_sleep=1.5)
    finally:
        disarm()

    # Phase 3: 邮件信封同法(悬停+enter)
    try:
        arm(180, 'mail_activation')
        task.send_key('esc', after_sleep=2)
        if not task.ocr(match=task.MENU_MARKERS):
            print('PHASE-MAIL: menu not open, reopen', flush=True)
            task.send_key('esc', after_sleep=2)
        boxes = dump(task, 'p7_mail_menu')
        move(830, 1000)
        time.sleep(0.3)
        key_full('enter')
        time.sleep(2.5)
        boxes = dump(task, 'p7_mail_page')
        in_mail = any(re.search('领取|系统邮件|好友邮件|删除|附件', b.name) for b in boxes)
        print(f'PHASE-MAIL hover+enter mail page={in_mail}', flush=True)
        if not in_mail:
            dblclick(830, 1000)
            time.sleep(2.5)
            boxes = dump(task, 'p7_mail_page2')
            in_mail = any(re.search('领取|系统邮件|好友邮件|删除|附件', b.name) for b in boxes)
            print(f'PHASE-MAIL dblclick mail page={in_mail}', flush=True)
        if in_mail:
            claim = next((b for b in boxes if re.search('一键领取|全部领取|领取全部', b.name)), None)
            if claim:
                click(claim.x + claim.width / 2, claim.y + claim.height / 2)
                time.sleep(2)
                task.confirm_dialog()
                dump(task, 'p7_mail_after')
            else:
                print('PHASE-MAIL no claim-all (已领完)', flush=True)
            task.send_key('esc', after_sleep=1.5)
            task.send_key('esc', after_sleep=1.5)
    finally:
        disarm()

    # 收尾回大世界
    for _ in range(3):
        boxes = dump(task, 'p7_final')
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
