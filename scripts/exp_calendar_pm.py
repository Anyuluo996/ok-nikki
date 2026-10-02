"""合并实验: A) admin+PostMessage 后台点击可行性; B) 奇想日历每日任务页面探索与领取。
前置: 游戏在大世界。
"""
import os
import sys
import re

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ok import OK, og

from src.config import config


def dump(task, tag):
    task.next_frame()
    task.screenshot(name=f'exp_{tag}')
    boxes = task.ocr(log=False)
    texts = [b.name for b in boxes]
    print(f'EXP {tag}: {len(texts)} boxes', flush=True)
    print('EXP-TEXTS ' + json.dumps(texts, ensure_ascii=False), flush=True)
    return texts


import json


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

    # ---------- Part A: Genshin 交互(WM_ACTIVATE 保活渲染) + PostMessage 后台点击 ----------
    from ok.device.interaction_methods.genshin import GenshinInteraction
    gi = GenshinInteraction(dm.capture_method, dm.hwnd_window)
    dm.interaction = gi
    executor.interaction = gi
    gi.activate() # 让游戏以为在前台, 保持后台渲染
    print('PART-A activated', flush=True)

    hw = dm.hwnd_window
    print(f'PART-A fg_before={hw.is_foreground()}', flush=True)
    task.next_frame()
    task.screenshot(name='exp_pm_0')
    entry = task.ocr(match=re.compile('商城'), log=True)
    if entry:
        print(f'PART-A clicking shop via PostMessage at {[ (b.x, b.y) for b in entry ]}', flush=True)
        task.click_box(entry[0], after_sleep=3, down_time=0.15)
        texts = dump(task, 'pm_after_click')
        in_shop = any(('星途珍存' in t or '候鸟轨迹' in t or '循星任务' in t or '购物车' in t) for t in texts)
        print(f'PART-A RESULT: {"WORKS" if in_shop else "NOT WORKING"}', flush=True)
        task.send_key('esc', after_sleep=1.5)
        task.send_key('esc', after_sleep=1.5)
    else:
        print('PART-A RESULT: shop entry not found, skip', flush=True)

    gi.deactivate() # 停止保活
    # 恢复 pynput 交互
    from ok.device.interaction_methods.pynput import PynputInteraction
    pn = PynputInteraction(dm.capture_method, dm.hwnd_window)
    dm.interaction = pn
    executor.interaction = pn

    # ---------- Part B: 奇想日历 ----------
    task.ensure_foreground()
    task.ensure_in_game()
    cal = task.wait_ocr(match=re.compile('奇想日历'), time_out=5, log=True)
    if not cal:
        print('PART-B RESULT: calendar entry not found', flush=True)
        task.debug_screenshot('calendar_no_entry')
        return
    task.click_box(cal[0], down_time=0.15, after_sleep=3)
    texts = dump(task, 'calendar_page')

    # 尝试找领取按钮(每日任务奖励/一键领取/领取)
    claim = task.ocr(match=re.compile('一键领取|领取|收下|Claim'), log=True)
    print(f'PART-B claim buttons: {[ (b.name, b.x, b.y) for b in claim ]}', flush=True)
    if claim:
        task.click_box(claim[0], down_time=0.15, after_sleep=2)
        task.confirm_dialog()
        texts2 = dump(task, 'calendar_after_claim')
        print('PART-B RESULT: claimed', flush=True)
    else:
        print('PART-B RESULT: no claim button visible, need calibration', flush=True)
    task.send_key('esc', after_sleep=1.5)
    task.send_key('esc', after_sleep=1.5)
    print('SESSION DONE', flush=True)


if __name__ == '__main__':
    main()
