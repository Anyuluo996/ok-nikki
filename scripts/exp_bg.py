"""后台执行验证: GenshinInteraction(WM_ACTIVATE 保活渲染 + BlockInput) + PostMessage 后台点击。
Part A: 前台确保在大世界 → 主动切焦点到桌面 → 后台截图(next_frame) → 后台点商城 → OCR 验证。
Part B: 后台打开奇想日历, dump 页面文字用于校准 CalendarTask。
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
    """把焦点切到桌面/任务栏, 让游戏进入后台"""
    import win32api
    import win32con
    import win32gui
    import win32process
    # ALT 心跳: 伪造一次用户输入解锁 SetForegroundWindow 的前台限制
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

    c = dict(config)
    c.pop('gui', None)
    c['use_gui'] = False
    c['onetime_tasks'] = []
    c['windows'] = dict(config['windows'])
    c['windows']['interaction'] = ['Genshin', 'Pynput', 'PostMessage', 'PyDirect']  # 实验覆盖: Genshin 优先
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
    # 1) 前台确保在大世界
    task.ensure_foreground()
    arm(200, 'ensure_in_game')
    task.ensure_in_game()
    disarm()
    print('PART-1 in game (foreground)', flush=True)

    # 2) 主动切走焦点 → 游戏进后台
    focus_desktop()
    time.sleep(2)
    print(f'PART-2 fg={hw.is_foreground()}', flush=True)

    # 3) 后台保活渲染 → 截图
    t0 = time.time()
    gi.activate()
    frame_ok = True
    try:
        arm(60, 'next_frame_bg')
        task.next_frame()
        task.screenshot(name='exp_bg_0')
        disarm()
    except Exception as e:
        disarm()
        frame_ok = False
        print(f'PART-3 frame exception: {e}', flush=True)
    print(f'PART-3 frame after activate in {time.time()-t0:.1f}s ok={frame_ok}', flush=True)
    texts = task.ocr(log=False)
    print(f'EXP bg0: {len(texts)} boxes', flush=True)

    # 4) 后台点击商城
    shop_ok = False
    try:
        arm(60, 'shop_click')
        entry = task.ocr(match=re.compile('商城'), log=True)
        if entry:
            print(f'PART-4 bg click shop {[(b.x, b.y) for b in entry]}', flush=True)
            task.click_box(entry[0], after_sleep=3, down_time=0.15)
            texts = dump(task, 'bg_after_click')
            shop_ok = any(('星途珍存' in t or '候鸟轨迹' in t or '循星任务' in t or '清空购物车' in t or '历史低价' in t or '兑换' in t) for t in texts)
            print(f'PART-4 RESULT: {"WORKS" if shop_ok else "NOT WORKING"}', flush=True)
            task.send_key('esc', after_sleep=1.5)
            task.send_key('esc', after_sleep=1.5)
            dump(task, 'bg_after_esc')
        else:
            print('PART-4 RESULT: shop entry not found (ocr)', flush=True)
    finally:
        disarm()

    # 5) Part B: 后台打开奇想日历
    try:
        arm(90, 'calendar')
        cal = task.ocr(match=re.compile('奇想日历'), log=True)
        if cal:
            task.click_box(cal[0], down_time=0.15, after_sleep=3)
        else:
            print('PART-B calendar entry not on screen, try key L', flush=True)
            task.send_key('l', after_sleep=3)
        texts = dump(task, 'calendar_page')
        in_cal = any(('奇想日历' in t or '每日' in t or '本周' in t) for t in texts)
        print(f'PART-B page detected: {in_cal}', flush=True)
        claim = task.ocr(match=re.compile('一键领取|领取|收下|Claim'), log=True)
        print(f'PART-B claim buttons: {[(b.name, b.x, b.y) for b in claim]}', flush=True)
        if claim:
            task.click_box(claim[0], down_time=0.15, after_sleep=2)
            task.confirm_dialog()
            dump(task, 'calendar_after_claim')
            print('PART-B RESULT: claim clicked', flush=True)
        task.send_key('esc', after_sleep=1.5)
        task.send_key('esc', after_sleep=1.5)
    finally:
        disarm()

    gi.deactivate()
    task.ensure_foreground()
    print('SESSION DONE', flush=True)
    time.sleep(1)
    os._exit(0)


if __name__ == '__main__':
    main()
