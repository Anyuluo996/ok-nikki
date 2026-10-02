"""实验: admin + PostMessage 能否后台点击 UE5(不抢前台)。

前置: 游戏在大世界。脚本全程不拉前台, 用 PostMessage 点右上角「商城」,
截图验证是否响应。同时验证非前台下 WGC 截图质量。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ok import OK, og

from src.config import config


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

    # 强制换成 PostMessage 交互(不要求前台)
    from ok.device.interaction_methods.post_message import PostMessageInteraction
    pm = PostMessageInteraction(dm.capture_method, dm.hwnd_window)
    dm.interaction = pm
    executor.interaction = pm

    from src.tasks.MyBaseTask import MyBaseTask
    task = MyBaseTask(executor=executor, app=ok.headless_app)
    task.after_init(executor=executor, scene=executor.scene)
    task.post_init()

    hw = dm.hwnd_window
    print(f'EXP fg_before={hw.is_foreground()} (should be False, 游戏不应在前台)', flush=True)

    task.next_frame()
    task.screenshot(name='exp_pm_0_world')
    entry = task.ocr(match=re.compile('商城'), log=True)
    print(f'EXP shop entry: {[b.name for b in entry]}', flush=True)
    if not entry:
        print('EXP RESULT: shop text not found, abort', flush=True)
        return

    # PostMessage 后台点击商城入口(不激活窗口)
    task.click_box(entry[0], after_sleep=3, down_time=0.15)
    task.next_frame()
    task.screenshot(name='exp_pm_1_after_click')

    # 判定是否进入商城(顶部 tab: 星途珍存/候鸟轨迹/循星任务/爱的私藏)
    import re
    in_shop = task.ocr(match=re.compile('星途珍存|候鸟轨迹|循星任务|爱的私藏|购物车'), log=True)
    print(f'EXP in_shop: {[b.name for b in in_shop]}', flush=True)
    if in_shop:
        print('EXP RESULT: PostMessage background click WORKS', flush=True)
        task.send_key('esc', after_sleep=1)
        task.send_key('esc', after_sleep=1)
    else:
        task.next_frame()
        task.screenshot(name='exp_pm_2_fail')
        print('EXP RESULT: PostMessage background click NOT working', flush=True)


if __name__ == '__main__':
    import re
    main()
