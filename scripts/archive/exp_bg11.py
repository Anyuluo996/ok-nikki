"""后台全链终验 v11: 生产版 NikkiInteraction(config 挂载)。
链路: 前台 ensure 大世界 → 切后台 → activate 保活
  → esc 菜单(先查再按) → 点击「美鸭梨挖掘」(光标跳转+定时posted) → 一键收获 → 再次挖掘
  → 菜单 → 信封(0.447,0.930) → 邮件 → 领取全部
  → L 奇想日历 → 领取 → esc 回世界
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

    # 1) 前台确保大世界(此时用 Nikki 交互: posted 键盘 + 光标跳转点击)
    task.ensure_foreground()
    arm(200, 'ensure_in_game')
    task.ensure_in_game()
    task.close_pause_menu()
    disarm()
    print(f'PHASE1 menu_open={bool(task.ocr(match=task.MENU_MARKERS))}', flush=True)

    # 2) 切后台
    focus_desktop()
    time.sleep(2)
    dm.interaction.activate()
    time.sleep(1)
    arm(60, 'bg_frame')
    boxes = dump(task, 'p11_bg_world')
    disarm()
    print(f'PHASE2 fg={hw.is_foreground()} boxes={len(boxes)}', flush=True)

    # 3) 美鸭梨挖掘
    try:
        arm(240, 'mine')
        if not task.open_pause_menu():
            print('PHASE3 menu FAILED', flush=True)
            raise SystemExit(1)
        boxes = dump(task, 'p11_menu')
        mine = next((b for b in boxes if '美鸭梨挖掘' in b.name), None)
        if not mine:
            print('PHASE3 entry missing', flush=True)
            raise SystemExit(1)
        # 点图标热区(标签上方)
        task.click(mine.x + mine.width / 2, mine.y - 45, down_time=0.15, after_sleep=2.5)
        boxes = dump(task, 'p11_mine_page')
        in_mine = any(re.search('一键收获|再次挖掘|挖掘次数|挖掘中|剩余时间|挖掘目标', b.name) for b in boxes)
        print(f'PHASE3 mine page={in_mine}', flush=True)
        if in_mine:
            gather = next((b for b in boxes if re.search('一键收获', b.name)), None)
            if gather:
                task.click_box(gather, down_time=0.15, after_sleep=2)
                task.confirm_dialog()
                boxes = dump(task, 'p11_after_gather')
                again = next((b for b in task.ocr(log=False) if re.search('再次挖掘|继续挖掘|开始挖掘', b.name)), None)
                if again:
                    task.click_box(again, down_time=0.15, after_sleep=2)
                    task.confirm_dialog()
                    dump(task, 'p11_after_again')
                    print('PHASE3 RESULT: gather + dig again OK', flush=True)
                else:
                    print('PHASE3 RESULT: gathered, no dig-again popup', flush=True)
            else:
                digging = next((b for b in boxes if re.search(r'\d+/\d+', b.name)), None)
                print(f'PHASE3 RESULT: no gather button (digging={digging.name if digging else "?"})', flush=True)
        task.close_pause_menu()
    finally:
        disarm()

    # 4) 邮件
    try:
        arm(240, 'mail')
        if task.open_pause_menu():
            task.click(*task.MAIL_ICON_POS if hasattr(task, 'MAIL_ICON_POS') else (0.447, 0.930),
                       down_time=0.15, after_sleep=2.5)
            boxes = dump(task, 'p11_mail_page')
            in_mail = any(re.search('领取|系统邮件|好友邮件|删已读|删除邮件|附件', b.name) for b in boxes)
            print(f'PHASE4 mail page={in_mail}', flush=True)
            if in_mail:
                claim = next((b for b in boxes if re.search('一键领取|全部领取|领取全部', b.name)), None)
                if claim:
                    task.click_box(claim, down_time=0.15, after_sleep=2)
                    task.confirm_dialog()
                    dump(task, 'p11_after_claim')
                    print('PHASE4 RESULT: mail claimed', flush=True)
                else:
                    print('PHASE4 RESULT: no claim-all (已领完)', flush=True)
                task.close_pause_menu()
        else:
            print('PHASE4 menu FAILED', flush=True)
    finally:
        disarm()

    # 5) 奇想日历
    try:
        arm(150, 'calendar')
        task.send_key('l', after_sleep=2.5)
        boxes = dump(task, 'p11_calendar')
        in_cal = any(('奇想日历' in b.name or '每日灵感' in b.name or '阅历' in b.name) for b in boxes)
        print(f'PHASE5 calendar={in_cal}', flush=True)
        if in_cal:
            claims = [b for b in boxes if re.search('一键领取|全部领取|领取|收下', b.name)]
            print(f'PHASE5 claims: {[(b.name, b.x, b.y) for b in claims]}', flush=True)
            if claims:
                task.click_box(claims[0], down_time=0.15, after_sleep=2)
                task.confirm_dialog()
                dump(task, 'p11_after_claim')
            task.send_key('esc', after_sleep=2)
            task.send_key('esc', after_sleep=2)
    finally:
        disarm()

    # 收尾: 回大世界 + 停止保活
    for _ in range(3):
        if not task.ocr(match=task.MENU_MARKERS):
            break
        task.close_pause_menu()
        break
    dm.interaction.deactivate()
    print('SESSION DONE', flush=True)
    time.sleep(1)
    os._exit(0)


if __name__ == '__main__':
    main()
