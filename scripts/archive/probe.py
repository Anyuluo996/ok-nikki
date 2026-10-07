"""实机探针(手动驱动版): 绕过 headless 调度器的 pause/wait 机制。

用法同前:
  python scripts/probe.py click_text=点击进入游戏 [wait=8] [name=p1]
  python scripts/probe.py click=0.5,0.1 [wait=8] [name=p2]
  python scripts/probe.py esc [wait=8] [name=p3]
  python scripts/probe.py none [wait=8] [name=p4]
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ok import OK, og

from src.config import config


def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    args = [a for a in sys.argv[1:]] or ['none']
    action = args[0]
    kv = dict(a.split('=', 1) for a in args if '=' in a)
    wait_s = float(kv.get('wait', 8))
    name = kv.get('name', 'probe')

    headless_config = dict(config)
    headless_config.pop('gui', None)
    headless_config['use_gui'] = False
    headless_config['onetime_tasks'] = []  # 不让调度器领任务, 手动驱动
    ok = OK(headless_config)
    dm = ok.device_manager
    dm.do_refresh(True)  # 扫描设备, 填充 device_dict
    if dm.get_preferred_device() is None:
        dm.set_preferred_device()  # 未保存过设备时, 取第一个 connected 设备
    dm.do_start()  # 创建 capture + interaction(手动驱动时必须显式调)
    executor = ok.task_executor
    executor.start()  # paused=False + 空转线程
    og.app = ok  # task.tr 等需要

    from src.tasks.MyBaseTask import MyBaseTask
    task = MyBaseTask(executor=executor, app=ok.headless_app)
    task.after_init(executor=executor, scene=executor.scene)
    task.post_init()
    if not task.force_foreground():
        print("PROBE ERROR: cannot bring game to front", flush=True)
        return

    print(f'PROBE step1 action={action} wait={wait_s} name={name}', flush=True)
    print(f'PROBE paused={executor.paused} interaction={type(executor.interaction).__name__ if executor.interaction else None}', flush=True)
    if action == 'esc':
        task.send_key('esc', after_sleep=wait_s)
    elif action.startswith('click_text='):
        text = action.split('=', 1)[1]
        boxes = task.wait_ocr(match=text, time_out=15, log=True)
        if not boxes:
            print(f'PROBE text not found: {text}', flush=True)
            task.screenshot(name=f'probe_{name}_notfound')
            return
        task.click_box(boxes[0], after_sleep=wait_s)
    elif action.startswith('click='):
        x, y = (float(v) for v in action.split('=', 1)[1].split(','))
        task.click_relative(x, y, after_sleep=wait_s)
    else:
        for i in range(int(wait_s * 2)):
            if executor.paused:
                print(f'PROBE WARNING paused=True at t={i / 2}', flush=True)
            task.sleep(0.5)

    print('PROBE step3 action done, capture', flush=True)
    task.next_frame()
    print('PROBE step4 frame got, ocr', flush=True)
    boxes = task.ocr(log=False)
    print(f'PROBE step5 ocr done {len(boxes)}', flush=True)
    dump = [{'t': b.name, 'x': b.x, 'y': b.y, 'w': b.width, 'h': b.height} for b in boxes]
    with open(f'probe_{name}_ocr.json', 'w', encoding='utf-8') as f:
        json.dump(dump, f, ensure_ascii=False, indent=1)
    task.screenshot(name=f'probe_{name}')
    print(f'PROBE done: {len(boxes)} boxes', flush=True)


if __name__ == '__main__':
    main()
