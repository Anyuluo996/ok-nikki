"""信封点击实验: 试不同点击方式(长按/双击)直到进入邮件页, 每步截图。"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ok import OK, og

from src.config import config


def dump(task, tag):
    task.next_frame()
    task.screenshot(name=f'exp_{tag}')
    boxes = task.ocr(log=False)
    texts = [b.name for b in boxes]
    print(f'EXP {tag}: {texts}', flush=True)
    return texts


def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
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
    task = MyBaseTask(executor=executor, app=ok.headless_app)
    task.after_init(executor=executor, scene=executor.scene)
    task.post_init()

    task.ensure_foreground()
    # 打开美鸭梨菜单
    task.send_key('esc', after_sleep=2)
    if not task.ocr(match=task.MENU_MARKERS, log=True):
        task.send_key('esc', after_sleep=2)
    dump(task, 'menu')

    # 实验1: 长按点击信封
    task.click(0.447, 0.930, down_time=0.15, after_sleep=2.5)
    texts = dump(task, 'click_long')
    if any('领取' in t or '邮件' in t for t in texts):
        print('EXP RESULT: long click works', flush=True)
        return

    # 实验2: 双击
    task.click_relative(0.447, 0.930, after_sleep=0.1)
    task.click_relative(0.447, 0.930, after_sleep=2.5)
    texts = dump(task, 'click_double')
    if any('领取' in t or '邮件' in t for t in texts):
        print('EXP RESULT: double click works', flush=True)
        return

    # 实验3: 回菜单再长按一次(如果实验2进入了别的页面)
    task.send_key('esc', after_sleep=2)
    task.send_key('esc', after_sleep=1)
    task.send_key('esc', after_sleep=2)
    if not task.ocr(match=task.MENU_MARKERS, log=True):
        task.send_key('esc', after_sleep=2)
    task.click_relative(0.447, 0.930, after_sleep=0.05)
    task.click_relative(0.447, 0.930, after_sleep=0.05)
    task.click_relative(0.447, 0.930, after_sleep=2.5)
    texts = dump(task, 'click_triple')
    print('EXP RESULT: triple click state', flush=True)


if __name__ == '__main__':
    main()
