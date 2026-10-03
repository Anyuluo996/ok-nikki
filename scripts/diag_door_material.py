"""诊断+重试: 副本门退出方式逐个试, 然后用修复后的导航跑素材激化真实兑换 1 次。
- 门图标(BACKSPACE)不吃真实点击(v7), v6 曾被 posted 点击退出 —— 逐法验证
- 之后 material_flow(1): L→每日幻境行→hub→素材激化卡→前往→W→F→噗灵→材料×1→激化
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


TASK = None


def dump(tag):
    TASK.next_frame()
    TASK.screenshot(name=f'diag_{tag}')
    boxes = TASK.ocr(log=False)
    texts = [b.name for b in boxes]
    print(f'DIAG {tag}: boxes={len(texts)}', flush=True)
    print('DIAG-TEXTS ' + json.dumps(texts, ensure_ascii=False), flush=True)
    return boxes


def back_box(boxes=None):
    boxes = boxes or TASK.ocr(log=False)
    return next((b for b in boxes
                 if b.name.strip().upper() == 'BACKSPACE'
                 and b.x < 220 and b.y < 420), None)


def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    threading.Thread(target=watchdog, daemon=True).start()

    c = dict(config)
    c.pop('gui', None)
    c['use_gui'] = False
    c['onetime_tasks'] = []
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
    from src.tasks.RealmTask import RealmTask

    global TASK
    TASK = MyBaseTask(executor=executor, app=ok.headless_app)
    TASK.after_init(executor=executor, scene=executor.scene)
    TASK.post_init()

    realm = RealmTask(executor=executor, app=ok.headless_app)
    realm.after_init(executor=executor, scene=executor.scene)
    realm.post_init()
    realm.config['Material Exchange Count'] = 1
    realm.config['Escalate Product'] = '噗灵'
    realm.config['Escalate Units'] = 1
    realm.config['Dry Run'] = False

    TASK.ensure_foreground()
    arm(120, 'ensure_in_game')
    TASK.ensure_in_game()
    disarm()
    time.sleep(1)

    # 1) 门退出诊断
    arm(200, 'door_diag')
    try:
        boxes = dump('p0_state')
        back = back_box(boxes)
        if not back:
            print('DIAG: not in dungeon, skip door test', flush=True)
        else:
            ix, iy = int(back.x + back.width / 2), int(max(10, back.y - 22))
            methods = [
                ('posted_icon', lambda: TASK.click(ix, iy, down_time=0.15, after_sleep=2.5)),
                ('posted_icon_low', lambda: TASK.click(ix, iy + 10, down_time=0.15, after_sleep=2.5)),
                ('hover_enter', lambda: TASK.hover_and_enter(ix, iy, key='enter', hover_time=1.0)),
            ]
            for name, fn in methods:
                print(f'DIAG door method: {name} at ({ix},{iy})', flush=True)
                fn()
                time.sleep(2)
                boxes = TASK.ocr(log=False)
                if any(re.search('恭喜获得|退出秘境|确定|确认', b.name) for b in boxes):
                    print(f'DIAG {name}: popup appeared', flush=True)
                    dump('p1_popup')
                    confirm = next((b for b in boxes
                                    if re.fullmatch('确定|确认', b.name.strip())), None)
                    if confirm:
                        TASK.click_box(confirm, down_time=0.15, after_sleep=3)
                    time.sleep(2)
                if not back_box(TASK.ocr(log=False)):
                    print(f'DIAG RESULT: door method "{name}" WORKS', flush=True)
                    break
                print(f'DIAG {name}: still in dungeon', flush=True)
            else:
                print('DIAG RESULT: no door method worked', flush=True)
                dump('p2_stuck')
    finally:
        disarm()

    # 2) 素材激化真实兑换(修复后的导航)
    arm(420, 'material_flow')
    try:
        done = realm.material_flow(1)
        print(f'RESULT material_flow done={done}', flush=True)
        print('RESULT realm infos:', json.dumps(realm.info, ensure_ascii=False, default=str),
              flush=True)
    finally:
        disarm()

    # 3) 收尾回大世界
    arm(120, 'final_back')
    try:
        realm.back_to_world()
        boxes = dump('p3_final')
        print('FINAL in_dungeon=', bool(back_box(boxes)), flush=True)
    finally:
        disarm()

    print('SESSION DONE', flush=True)
    time.sleep(1)
    os._exit(0)


if __name__ == '__main__':
    main()
