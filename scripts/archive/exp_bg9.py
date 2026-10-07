"""v9: 菜单坐标校准 + 偏移假设验证。
背景: posted 点击疑似有 ~(+120,-30) 偏移(点击挖掘入口→翻到右箭头页)。
Phase A: 后台 esc 开菜单(重试) → 底行 y=1000 逐 x 点击 → dump 页面特征 → 建立 x→页面 映射
Phase B: 美鸭梨挖掘: 对照点击 (945,568) 与偏移补偿位 (825,598), 哪个进入挖掘页
Phase C: 进入挖掘页后按 Whimbox 流程: 一键收获 → 弹窗再次挖掘 → esc×2
Phase D: L 开奇想日历 → 领取 → esc (复验)
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

    def key_full(key, down_time=0.15):
        vk = gi.get_key_by_str(key)
        sc = win32api.MapVirtualKey(vk & 0xff, 0)
        gi.post(win32con.WM_KEYDOWN, vk, 0x1e0001 | (sc << 16))
        gi.post(win32con.WM_CHAR, vk, 0x1e0001)
        time.sleep(down_time)
        gi.post(win32con.WM_KEYUP, vk, 0xc01e0001 | (sc << 16))

    # 关键: 把 task 的点击/按键替换成上面的实现
    gi.click = click
    gi.send_key = key_full

    from src.tasks.MyBaseTask import MyBaseTask
    task = MyBaseTask(executor=executor, app=ok.headless_app)
    task.after_init(executor=executor, scene=executor.scene)
    task.post_init()

    hw = dm.hwnd_window

    SIGS = [
        ('mine', re.compile('一键收获|再次挖掘|挖掘次数|挖掘中|剩余时间')),
        ('mail', re.compile('系统邮件|好友邮件|删已读|删除邮件')),
        ('chat', re.compile('点击输入消息|跳转至好友')),
        ('settings', re.compile('画面|音量|语言|镜头')),
        ('calendar', re.compile('每日灵感|阅历挑战|奇想日历')),
        ('menu1', re.compile('^商城$')),
    ]

    def sig_of(boxes):
        joined = ' '.join(b.name for b in boxes)
        for name, p in SIGS:
            if p.search(joined):
                return name
        if any('美鸭梨' in b.name for b in boxes):
            return 'menu'
        return 'other'

    def ensure_menu(attempts=4):
        """后台确保菜单第一页打开, 返回 bool"""
        for i in range(attempts):
            boxes = task.ocr(log=False)
            if any(re.search('^商城$', b.name) and b.y < 400 for b in boxes):
                return True
            key_full('esc')
            time.sleep(1.8)
        return any(re.search('^商城$', b.name, ) and b.y < 400 for b in task.ocr(log=False))

    def back_to_menu_from_page():
        """从子页面回菜单第一页: esc 若回到世界则再开菜单"""
        for _ in range(4):
            boxes = task.ocr(log=False)
            s = sig_of(boxes)
            if s == 'menu1':
                return True
            key_full('esc')
            time.sleep(1.6)
        return ensure_menu(1)

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
        # Phase A: 底行图标扫描(点击, 非 Enter)
        arm(300, 'phaseA_scan')
        if not ensure_menu():
            print('PHASE-A menu failed to open, abort', flush=True)
            raise SystemExit(1)
        boxes = dump(task, 'p9_menu')
        print(f'PHASE-A menu sig={sig_of(boxes)}', flush=True)
        mapping = {}
        for x in (465, 595, 712, 830, 950, 1073):
            click(x, 1000)
            time.sleep(2.2)
            boxes = dump(task, f'p9_scan_{x}')
            s = sig_of(boxes)
            mapping[x] = s
            print(f'PHASE-A click ({x},1000) → {s}', flush=True)
            if s == 'menu1' or s == 'menu':
                continue
            if not back_to_menu_from_page():
                print(f'PHASE-A recover failed after x={x}', flush=True)
                break
        print(f'PHASE-A MAPPING: {json.dumps(mapping)}', flush=True)

        # Phase B: 美鸭梨挖掘 偏移对照
        arm(240, 'phaseB_mine')
        if ensure_menu():
            for label, tx, ty in (('normal', 945, 568), ('offsetcomp', 825, 598)):
                mine = next((b for b in task.ocr(log=False) if '美鸭梨挖掘' in b.name), None)
                if not mine:
                    print(f'PHASE-B {label}: entry not on page1, skip', flush=True)
                    break
                click(tx, ty)
                time.sleep(2.5)
                boxes = dump(task, f'p9_mine_{label}')
                s = sig_of(boxes)
                print(f'PHASE-B click {label} ({tx},{ty}) → {s}', flush=True)
                if s == 'mine':
                    ui = [b.name for b in boxes if re.search('收获|挖掘|次数|剩余|时间|领取|开始', b.name)]
                    print(f'PHASE-B mine ui: {json.dumps(ui, ensure_ascii=False)}', flush=True)
                    # Whimbox 流程: 一键收获 → 再次挖掘
                    gather = next((b for b in boxes if re.search('一键收获|收获', b.name)), None)
                    if gather:
                        click(gather.x + gather.width / 2, gather.y + gather.height / 2)
                        time.sleep(2)
                        task.confirm_dialog()
                        boxes = dump(task, 'p9_after_gather')
                        again = next((b for b in task.ocr(log=False) if re.search('再次挖掘|继续挖掘|开始挖掘', b.name)), None)
                        if again:
                            click(again.x + again.width / 2, again.y + again.height / 2)
                            time.sleep(2)
                            task.confirm_dialog()
                            dump(task, 'p9_after_dig_again')
                            print('PHASE-B RESULT: gathered + dig again', flush=True)
                        else:
                            print('PHASE-B RESULT: gathered, no dig-again button', flush=True)
                    else:
                        print('PHASE-B RESULT: mine page opened, no gather button (挖掘中或未设置)', flush=True)
                    task.send_key('esc', after_sleep=1.5)
                    task.send_key('esc', after_sleep=1.5)
                    break
                # 未进入挖掘页 → 回菜单重试
                if not back_to_menu_from_page():
                    print('PHASE-B recover failed', flush=True)
                    break
        else:
            print('PHASE-B menu failed', flush=True)

        # Phase C: 奇想日历复验
        arm(150, 'phaseC_calendar')
        key_full('esc')
        time.sleep(1.5)
        key_full('l')
        time.sleep(2.5)
        boxes = dump(task, 'p9_calendar')
        s = sig_of(boxes)
        print(f'PHASE-C after L → {s}', flush=True)
        if s == 'calendar':
            claims = [b for b in boxes if re.search('一键领取|全部领取|领取|收下', b.name)]
            print(f'PHASE-C claims: {[(b.name, b.x, b.y) for b in claims]}', flush=True)
            if claims:
                task.click_box(claims[0], after_sleep=2)
                task.confirm_dialog()
                dump(task, 'p9_after_claim')
            task.send_key('esc', after_sleep=1.5)
            task.send_key('esc', after_sleep=1.5)
    finally:
        disarm()

    # 收尾回大世界
    for _ in range(4):
        boxes = dump(task, 'p9_final')
        if sig_of(boxes) == 'other' and not any(re.search('美鸭梨', b.name) for b in boxes):
            break
        key_full('esc')
        time.sleep(1.5)
    gi.deactivate()
    dm.interaction = pn
    task.ensure_foreground()
    print('SESSION DONE', flush=True)
    time.sleep(1)
    os._exit(0)


if __name__ == '__main__':
    main()
