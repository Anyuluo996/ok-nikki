"""v10: 前台 posted 点击偏移测定(决定性)。
游戏保持前台(不做 focus_desktop), 全部用 posted 输入:
  A esc 开菜单(前台 posted 可靠性)
  B 点击 美鸭梨挖掘 标签中心 (945,568) → 挖掘页 or 翻页?
  C 若翻页 → 点击补偿位 (825,598) → 挖掘页?
  D 若进挖掘页: dump 校准 + 一键收获/再次挖掘流程
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
        # 无 WM_CHAR: CHAR 会被游戏当成第二次按键(esc 开了又被关)
        vk = gi.get_key_by_str(key)
        sc = win32api.MapVirtualKey(vk & 0xff, 0)
        gi.post(win32con.WM_KEYDOWN, vk, 0x1e0001 | (sc << 16))
        time.sleep(down_time)
        gi.post(win32con.WM_KEYUP, vk, 0xc01e0001 | (sc << 16))

    gi.click = click
    gi.send_key = key_full

    from src.tasks.MyBaseTask import MyBaseTask
    task = MyBaseTask(executor=executor, app=ok.headless_app)
    task.after_init(executor=executor, scene=executor.scene)
    task.post_init()

    # Phase 1: 前台确保大世界(保持前台, 不切走)
    task.ensure_foreground()
    arm(200, 'ensure_in_game')
    task.ensure_in_game()
    task.close_pause_menu()
    disarm()
    print(f'PHASE1 menu_open={bool(task.ocr(match=task.MENU_MARKERS))}', flush=True)

    SIG_MINE = re.compile('一键收获|再次挖掘|挖掘次数|挖掘中|剩余时间')

    try:
        # A: esc 开菜单(先查再按, 按后等2s)
        arm(120, 'open_menu')
        opened = task.open_pause_menu(attempts=4)
        if not opened:
            print('PHASE-A menu FAILED (fg posted esc)', flush=True)
            dump(task, 'p10_menu_fail')
            raise SystemExit(1)
        print('PHASE-A menu opened', flush=True)
        boxes = dump(task, 'p10_menu')
        mine = next((b for b in boxes if '美鸭梨挖掘' in b.name), None)
        print(f'PHASE-A entry present={bool(mine)}', flush=True)

        # B: 点标签中心
        arm(120, 'click_normal')
        if mine:
            lx, ly = mine.x + mine.width / 2, mine.y + mine.height / 2
            click(lx, ly)
            time.sleep(2.5)
            boxes = dump(task, 'p10_click_normal')
            if SIG_MINE.search(' '.join(b.name for b in boxes)):
                print(f'PHASE-B RESULT: normal click ({lx:.0f},{ly:.0f}) → MINE PAGE (no offset!)', flush=True)
            elif any('美鸭梨' in b.name for b in boxes):
                print(f'PHASE-B RESULT: normal click → still menu (paged?)', flush=True)
                # C: 补偿位
                click(lx - 120, ly + 30)
                time.sleep(2.5)
                boxes = dump(task, 'p10_click_comp')
                if SIG_MINE.search(' '.join(b.name for b in boxes)):
                    print(f'PHASE-C RESULT: compensated click ({lx-120:.0f},{ly+30:.0f}) → MINE PAGE (OFFSET ~(+120,-30) CONFIRMED)', flush=True)
                elif any('美鸭梨' in b.name for b in boxes):
                    print('PHASE-C RESULT: still menu', flush=True)
                else:
                    print('PHASE-C RESULT: other page', flush=True)
            else:
                print('PHASE-B RESULT: other page', flush=True)

        # D: 若在挖掘页, 走 Whimbox 流程
        boxes = task.ocr(log=False)
        if SIG_MINE.search(' '.join(b.name for b in boxes)):
            ui = [b.name for b in boxes if re.search('收获|挖掘|次数|剩余|时间|领取|开始', b.name)]
            print(f'PHASE-D mine ui: {json.dumps(ui, ensure_ascii=False)}', flush=True)
            gather = next((b for b in boxes if re.search('一键收获', b.name)), None)
            if gather:
                click(gather.x + gather.width / 2, gather.y + gather.height / 2)
                time.sleep(2)
                task.confirm_dialog()
                boxes = dump(task, 'p10_after_gather')
                again = next((b for b in task.ocr(log=False) if re.search('再次挖掘|继续挖掘|开始挖掘', b.name)), None)
                if again:
                    click(again.x + again.width / 2, again.y + again.height / 2)
                    time.sleep(2)
                    task.confirm_dialog()
                    dump(task, 'p10_after_again')
                    print('PHASE-D RESULT: gather + dig-again done', flush=True)
                else:
                    print('PHASE-D RESULT: gathered, no dig-again visible', flush=True)
            else:
                print('PHASE-D RESULT: no gather button (挖掘中/未设置目标)', flush=True)
    finally:
        disarm()

    # 收尾
    for _ in range(4):
        if not task.ocr(match=task.MENU_MARKERS):
            break
        key_full('esc')
        time.sleep(1.5)
    print('SESSION DONE', flush=True)
    time.sleep(1)
    os._exit(0)


if __name__ == '__main__':
    main()
