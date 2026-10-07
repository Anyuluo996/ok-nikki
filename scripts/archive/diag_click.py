"""点击链路诊断: 状态打印 + 显式点击 + 截图验证。"""
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
    ex = ok.task_executor
    ex.start()
    from src.tasks.MyBaseTask import MyBaseTask
    task = MyBaseTask(executor=ex, app=ok.headless_app)
    task.after_init(executor=ex, scene=ex.scene)
    task.post_init()
    hw = dm.hwnd_window
    print('DIAG clickable=%s fg=%s hwnd=%s xy=%s,%s win=%sx%s real=%s,%s,%s,%s' % (
        dm.interaction.clickable(), hw.is_foreground(), hw.hwnd, hw.x, hw.y,
        hw.window_width, hw.window_height, hw.real_x_offset, hw.real_y_offset,
        hw.real_width, hw.real_height), flush=True)
    frame = task.next_frame()
    print('DIAG frame=%s' % (frame.shape if frame is not None else None), flush=True)
    task.click(960, 810)
    import time
    time.sleep(8)
    task.screenshot(name='diag_click')
    print('DIAG clicked+shot, clickable now=%s' % task.interaction.clickable(), flush=True)


if __name__ == '__main__':
    main()
