"""后台验证 v8: open_pause_menu 重试 + hover/Enter 激活菜单项 + 信封位置扫描。
Phase A: 菜单 → 悬停「美鸭梨挖掘」→ Enter → 挖掘页 → dump 校准 → 领取/继续挖掘 → esc×2
Phase B: 菜单 → 底行图标逐个 hover+Enter (465,595,712,950,1073) → 找邮件页 → 领取全部
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
        time.sleep(0.15)

    def click(x, y, down_time=0.15):
        pos = win32api.MAKELONG(int(x), int(y))
        gi.post(win32con.WM_MOUSEMOVE, 0, pos)
        time.sleep(0.05)
        gi.post(win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, pos)
        time.sleep(down_time)
        gi.post(win32con.WM_LBUTTONUP, 0, pos)

    def key_full(key, down_time=0.12):
        vk = gi.get_key_by_str(key)
        sc = win32api.MapVirtualKey(vk & 0xff, 0)
        gi.post(win32con.WM_KEYDOWN, vk, 0x1e0001 | (sc << 16))
        gi.post(win32con.WM_CHAR, vk, 0x1e0001)
        time.sleep(down_time)
        gi.post(win32con.WM_KEYUP, vk, 0xc01e0001 | (sc << 16))

    def hover_activate(x, y):
        """悬停选中 + Enter 确认(菜单交互模型)"""
        move(960, 300)  # 先离开, 保证 move 事件序列干净
        move(x, y)
        time.sleep(0.3)
        key_full('enter')

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

    MAIL_SIG = re.compile('领取|系统邮件|好友邮件|删已读|删除邮件|附件|Mail')
    CHAT_SIG = re.compile('点击输入消息|在线|好友申请')

    def page_signature(boxes):
        joined = ' '.join(b.name for b in boxes)
        if re.search(CHAT_SIG, joined):
            return 'chat'
        if re.search(MAIL_SIG, joined):
            return 'mail'
        if any('商城' in b.name and b.y < 400 for b in boxes):
            return 'menu1'
        if '美鸭梨' in joined:
            return 'menu'
        return 'other'

    try:
        # Phase A: 美鸭梨挖掘
        arm(240, 'phaseA_mine')
        task.open_pause_menu()
        boxes = dump(task, 'p8_menu')
        sig = page_signature(boxes)
        print(f'PHASE-A menu={sig}', flush=True)
        if sig == 'menu1':
            mine = next((b for b in boxes if '美鸭梨挖掘' in b.name), None)
            if mine:
                hover_activate(mine.x + mine.width / 2, mine.y - 55)
                time.sleep(2.5)
                boxes = dump(task, 'p8_mine_page')
                sig = page_signature(boxes)
                print(f'PHASE-A after activate sig={sig}', flush=True)
                if sig in ('other',):
                    ui = [b.name for b in boxes if re.search('领取|挖掘|剩余|次数|时间|可|开始|结束', b.name)]
                    print(f'PHASE-A mine ui: {json.dumps(ui, ensure_ascii=False)}', flush=True)
                    btn = next((b for b in boxes if re.search('继续挖掘|开始挖掘|一键领取|领取', b.name)), None)
                    if btn:
                        click(btn.x + btn.width / 2, btn.y + btn.height / 2)
                        time.sleep(2)
                        task.confirm_dialog()
                        dump(task, 'p8_mine_after')
                    else:
                        print('PHASE-A no dig/claim button on page', flush=True)
                task.send_key('esc', after_sleep=1.5)
                task.send_key('esc', after_sleep=1.5)
        else:
            print('PHASE-A menu not on page1, skip', flush=True)

        # Phase B: 信封扫描
        arm(240, 'phaseB_mail')
        task.open_pause_menu()
        dump(task, 'p8_mail_menu')
        found = None
        for x in (712, 950, 1073, 595, 465, 858):
            hover_activate(x, 1000)
            time.sleep(2.2)
            boxes = dump(task, f'p8_scan_{x}')
            sig = page_signature(boxes)
            print(f'PHASE-B scan x={x} → {sig}', flush=True)
            if sig == 'mail':
                found = x
                break
            # 关掉误开的页面回到菜单
            for _ in range(2):
                boxes = task.ocr(log=False)
                if page_signature(boxes) == 'menu1':
                    break
                task.send_key('esc', after_sleep=1.5)
        if found:
            print(f'PHASE-B mail button x={found}', flush=True)
            # 重新进邮件页做领取
            task.open_pause_menu()
            hover_activate(found, 1000)
            time.sleep(2.5)
            boxes = dump(task, 'p8_mail_page')
            if page_signature(boxes) == 'mail':
                claim = next((b for b in boxes if re.search('一键领取|全部领取|领取全部', b.name)), None)
                if claim:
                    click(claim.x + claim.width / 2, claim.y + claim.height / 2)
                    time.sleep(2)
                    task.confirm_dialog()
                    dump(task, 'p8_mail_after')
                else:
                    print('PHASE-B no claim-all (已领完)', flush=True)
                task.send_key('esc', after_sleep=1.5)
                task.send_key('esc', after_sleep=1.5)
        else:
            print('PHASE-B RESULT: mail button not found in scan', flush=True)
    finally:
        disarm()

    # 收尾回大世界
    for _ in range(4):
        boxes = dump(task, 'p8_final')
        sig = page_signature(boxes)
        if sig in ('other', 'chat') and '美鸭梨' not in sig:
            # 世界视图无法直接判定, 用菜单标记判断
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
