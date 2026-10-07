"""v13: 挖掘入口激活最后一招 — 真实光标悬停(光晕跟随) + posted Enter/Space 确认。
备选: WM_LBUTTONDBLCLK 直发。
成功后走完整挖掘流程(一键收获→再次挖掘), 再复验邮件+日历, 全链收尾。
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


PAGE_SIGS = {
    'mine': re.compile('一键收获|再次挖掘|挖掘次数|挖掘中|剩余时间|挖掘目标'),
    'mail': re.compile('系统邮件|好友邮件|删已读|删除邮件'),
    'chat': re.compile('点击输入消息|跳转至好友'),
    'calendar': re.compile('每日灵感|阅历挑战'),
    'shop': re.compile('星途珍存|清空购物车|历史低价'),
}


def page_sig(boxes):
    joined = ' '.join(b.name for b in boxes)
    for name, p in PAGE_SIGS.items():
        if p.search(joined):
            return name
    if '美鸭梨' in joined:
        return 'menu'
    return 'other'


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
    from src.device.NikkiInteraction import NikkiInteraction
    c['windows'] = dict(config['windows'])
    c['windows']['interaction'] = [NikkiInteraction, 'Pynput', 'PostMessage', 'PyDirect']
    ok = OK(c)
    dm = ok.device_manager
    dm.do_refresh(True)
    if dm.get_preferred_device() is None:
        dm.set_preferred_device()
    dm.do_start()
    executor = ok.task_executor
    executor.start()
    og.app = ok

    assert isinstance(dm.interaction, NikkiInteraction), f'interaction is {type(dm.interaction)}'
    print('PART-0 interaction = NikkiInteraction', flush=True)

    from src.tasks.MyBaseTask import MyBaseTask
    task = MyBaseTask(executor=executor, app=ok.headless_app)
    task.after_init(executor=executor, scene=executor.scene)
    task.post_init()

    hw = dm.hwnd_window
    gi = dm.interaction

    def hover_only(x, y):
        """真实光标移到目标(光晕跟随), 不点击"""
        abs_x, abs_y = gi.capture.get_abs_cords(int(x), int(y))
        win32api.SetCursorPos((abs_x, abs_y))
        time.sleep(0.6)

    def exit_to_world(max_esc=5):
        for _ in range(max_esc):
            task.send_key('esc', after_sleep=2)
            if page_sig(task.ocr(log=False)) == 'other':
                return True
        return page_sig(task.ocr(log=False)) == 'other'

    # 1) 前台确保大世界
    task.ensure_foreground()
    arm(200, 'ensure_in_game')
    task.ensure_in_game()
    disarm()
    print(f'PHASE1 sig={page_sig(task.ocr(log=False))}', flush=True)

    # 2) 切后台
    focus_desktop()
    time.sleep(2)
    gi.activate()
    time.sleep(1)
    arm(60, 'bg_frame')
    boxes = dump(task, 'p13_bg_world')
    disarm()
    print(f'PHASE2 fg={hw.is_foreground()} sig={page_sig(boxes)}', flush=True)

    # 3) 挖掘: 悬停+Enter
    try:
        arm(300, 'mine')
        if not task.open_pause_menu():
            print('PHASE3 menu FAILED', flush=True)
            raise SystemExit(1)
        boxes = dump(task, 'p13_menu')
        mine = next((b for b in boxes if '美鸭梨挖掘' in b.name), None)
        if not mine:
            print('PHASE3 entry missing', flush=True)
            raise SystemExit(1)
        cx = mine.x + mine.width / 2
        cy = mine.y - 55  # 图标中心
        print(f'PHASE3 mine box=({mine.x},{mine.y},{mine.width},{mine.height}) hover=({cx:.0f},{cy:.0f})', flush=True)

        sig = 'menu'
        for act in ('enter', 'space', 'dblclk'):
            hover_only(cx, cy)
            if act == 'enter':
                task.send_key('enter', after_sleep=2.5)
            elif act == 'space':
                task.send_key('space', after_sleep=2.5)
            else:
                pos = win32api.MAKELONG(int(cx), int(cy))
                gi.post(win32con.WM_MOUSEMOVE, 0, pos)
                gi.post(win32con.WM_LBUTTONDBLCLK, win32con.MK_LBUTTON, pos)
                time.sleep(0.15)
                gi.post(win32con.WM_LBUTTONUP, 0, pos)
                time.sleep(2.5)
            boxes = task.ocr(log=False)
            sig = page_sig(boxes)
            print(f'PHASE3 act={act} → {sig}', flush=True)
            if sig == 'mine':
                break
            if sig == 'other':
                # 进了别的弹窗, esc 回菜单
                task.send_key('esc', after_sleep=2)

        if sig == 'mine':
            ui = [b.name for b in boxes if re.search('收获|挖掘|次数|剩余|时间|目标', b.name)]
            print(f'PHASE3 mine ui: {json.dumps(ui, ensure_ascii=False)}', flush=True)
            gather = next((b for b in boxes if re.search('一键收获', b.name)), None)
            if gather:
                task.click_box(gather, down_time=0.15, after_sleep=2)
                task.confirm_dialog()
                boxes = dump(task, 'p13_after_gather')
                again = next((b for b in boxes if re.search('再次挖掘|继续挖掘|开始挖掘', b.name)), None)
                if again:
                    task.click_box(again, down_time=0.15, after_sleep=2)
                    task.confirm_dialog()
                    dump(task, 'p13_after_again')
                    print('PHASE3 RESULT: gather + dig-again OK', flush=True)
                else:
                    print('PHASE3 RESULT: gathered, no dig-again popup', flush=True)
            else:
                digging = next((b for b in boxes if re.search(r'\d+/\d+', b.name)), None)
                print(f'PHASE3 RESULT: no gather (digging={digging.name if digging else "?"})', flush=True)
        else:
            print('PHASE3 RESULT: mine never opened', flush=True)
        exit_to_world()
    finally:
        disarm()

    # 4) 邮件复验
    try:
        arm(180, 'mail')
        if task.open_pause_menu():
            task.click(0.447, 0.930, down_time=0.15, after_sleep=2.5)
            boxes = dump(task, 'p13_mail_page')
            if page_sig(boxes) == 'mail':
                claim = next((b for b in boxes if re.search('一键领取|全部领取|领取全部', b.name)), None)
                if claim:
                    task.click_box(claim, down_time=0.15, after_sleep=2)
                    task.confirm_dialog()
                    print('PHASE4 RESULT: mail claimed', flush=True)
                else:
                    print('PHASE4 RESULT: no claim-all (已领完)', flush=True)
            else:
                print(f'PHASE4 sig={page_sig(boxes)}', flush=True)
        exit_to_world()
    finally:
        disarm()

    # 5) 日历复验
    try:
        arm(120, 'calendar')
        task.send_key('l', after_sleep=2.5)
        boxes = dump(task, 'p13_calendar')
        sig = page_sig(boxes)
        print(f'PHASE5 sig={sig}', flush=True)
        if sig == 'calendar':
            claims = [b for b in boxes if re.search('一键领取|全部领取|领取|收下', b.name)]
            print(f'PHASE5 claims: {[(b.name, b.x, b.y) for b in claims]}', flush=True)
            if claims:
                task.click_box(claims[0], down_time=0.15, after_sleep=2)
                task.confirm_dialog()
        exit_to_world()
    finally:
        disarm()

    # 光标还原到屏幕角落外? 不, 还原到菜单外安全区由用户接管; deactivate 停保活
    gi.deactivate()
    print('SESSION DONE', flush=True)
    time.sleep(1)
    os._exit(0)


if __name__ == '__main__':
    main()
