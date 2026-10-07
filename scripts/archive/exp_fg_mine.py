"""前台挖掘流程打通(FG + pynput 真实点击): 
菜单 → 点「美鸭梨挖掘」图标 → dump 页面(校准) → 一键收获 → 再次挖掘 → esc×2。
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


MINE_SIG = re.compile('一键收获|再次挖掘|挖掘次数|挖掘中|剩余时间|挖掘目标')


def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    threading.Thread(target=watchdog, daemon=True).start()

    c = dict(config)
    c.pop('gui', None)
    c['use_gui'] = False
    c['onetime_tasks'] = []
    c['windows'] = dict(config['windows'])
    c['windows']['interaction'] = ['Pynput', 'PostMessage', 'PyDirect']  # 前台真实输入
    ok = OK(c)
    dm = ok.device_manager
    dm.do_refresh(True)
    if dm.get_preferred_device() is None:
        dm.set_preferred_device()
    dm.do_start()
    executor = ok.task_executor
    executor.start()
    og.app = ok

    from src.tasks.MyBaseTask import MyBaseTask
    task = MyBaseTask(executor=executor, app=ok.headless_app)
    task.after_init(executor=executor, scene=executor.scene)
    task.post_init()

    # 前台 + 大世界
    task.ensure_foreground()
    arm(200, 'ensure_in_game')
    task.ensure_in_game()
    disarm()
    print(f'PHASE1 menu_open={bool(task.ocr(match=task.MENU_MARKERS))}', flush=True)

    try:
        arm(240, 'mine')
        if not task.open_pause_menu():
            print('PHASE2 menu FAILED', flush=True)
            raise SystemExit(1)
        boxes = dump(task, 'fg_menu')
        mine = next((b for b in boxes if '美鸭梨挖掘' in b.name), None)
        if not mine:
            print('PHASE2 entry missing', flush=True)
            raise SystemExit(1)
        cx, cy = mine.x + mine.width / 2, mine.y - 55
        print(f'PHASE2 box=({mine.x},{mine.y},{mine.width},{mine.height}) click=({cx:.0f},{cy:.0f})', flush=True)
        task.click(cx, cy, down_time=0.15, after_sleep=2.5)
        boxes = dump(task, 'fg_mine_page')
        in_mine = bool(MINE_SIG.search(' '.join(b.name for b in boxes)))
        print(f'PHASE2 mine page={in_mine}', flush=True)
        if in_mine:
            ui = [b.name for b in boxes if re.search('收获|挖掘|次数|剩余|时间|目标|开始|领取', b.name)]
            print(f'PHASE2 mine ui: {json.dumps(ui, ensure_ascii=False)}', flush=True)
            gather = next((b for b in boxes if re.search('一键收获', b.name)), None)
            if gather:
                task.click_box(gather, down_time=0.15, after_sleep=2)
                task.confirm_dialog()
                boxes = dump(task, 'fg_after_gather')
                again = next((b for b in boxes if re.search('再次挖掘|继续挖掘|开始挖掘', b.name)), None)
                if again:
                    task.click_box(again, down_time=0.15, after_sleep=2)
                    task.confirm_dialog()
                    dump(task, 'fg_after_again')
                    print('PHASE3 RESULT: gather + dig-again OK', flush=True)
                else:
                    print('PHASE3 RESULT: gathered, no dig-again popup', flush=True)
            else:
                digging = next((b for b in boxes if re.search(r'\d+/\d+', b.name)), None)
                print(f'PHASE3 RESULT: no gather button (digging={digging.name if digging else "?"})', flush=True)
        task.close_pause_menu()
    finally:
        disarm()

    print('SESSION DONE', flush=True)
    time.sleep(1)
    os._exit(0)


if __name__ == '__main__':
    main()
