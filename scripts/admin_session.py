"""一次提权完成的 UI 探索序列: 等加载 → 大世界截图 → Esc 菜单截图 → OCR dump。
结果: probe_s<n>_*.png / probe_s<n>_ocr.json + 汇总 stdout。
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ok import OK, og

from src.config import config


def log_step(msg):
    line = f'[{__import__("time").strftime("%H:%M:%S")}] {msg}'
    with open('session_progress.log', 'a', encoding='utf-8') as f:
        f.write(line + '\n')
    print(line, flush=True)


def dump(task, executor, tag):
    task.next_frame()
    task.screenshot(name=f'probe_{tag}')
    boxes = task.ocr(log=False)
    data = [{'t': b.name, 'x': b.x, 'y': b.y, 'w': b.width, 'h': b.height} for b in boxes]
    with open(f'probe_{tag}_ocr.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    texts = [d['t'] for d in data]
    print(f'SECTION {tag}: {len(data)} boxes: {texts}', flush=True)
    return data


def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    try:
        run()
    except SystemExit as e:
        log_step(f'SystemExit: {e}')
        raise
    except Exception:
        import traceback
        log_step('EXCEPTION:\n' + traceback.format_exc())
        raise


def run():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    log_step('init OK()')
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
    log_step(f'device ready, interaction={type(dm.interaction).__name__}')
    executor = ok.task_executor
    executor.start()
    og.app = ok

    from src.tasks.MyBaseTask import MyBaseTask
    task = MyBaseTask(executor=executor, app=ok.headless_app)
    task.after_init(executor=executor, scene=executor.scene)
    task.post_init()
    log_step('task ready')

    # s0: 等游戏加载完成(从登录点击后算起, 程序启动时通常已在加载/大世界)
    task.sleep(45)
    log_step('sleep done')
    dump(task, executor, 's0_world')

    # s1: Esc 打开美鸭梨菜单
    task.force_foreground()
    task.send_key('esc', after_sleep=3)
    dump(task, executor, 's1_escmenu')

    # s2: 再截一张(有些菜单有动画, 稳定后再看)
    task.sleep(2)
    dump(task, executor, 's2_escmenu2')

    # s3: 关闭菜单回到大世界
    task.send_key('esc', after_sleep=2)
    task.send_key('esc', after_sleep=2)
    dump(task, executor, 's3_backworld')
    log_step('SESSION DONE')


if __name__ == '__main__':
    main()
