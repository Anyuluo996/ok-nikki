"""实机校准脚本: 截取游戏画面 + OCR 全量 dump, 用于校准 DailyTask 关键字。

用法: .venv/Scripts/python.exe scripts/calibrate.py [name]
输出: screenshots/calib_<name>.png + calib_<name>_ocr.json
"""
import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ok import BaseTask, run_task

from src.config import config


class CalibTask(BaseTask):

    def run(self):
        name = self.name_suffix
        self.next_frame()
        self.screenshot(name=f'calib_{name}')
        boxes = self.ocr(log=True)
        dump = [{'t': b.name, 'x': b.x, 'y': b.y, 'w': b.width, 'h': b.height, 'conf': round(b.confidence, 3)}
                for b in boxes]
        out = f'calib_{name}_ocr.json'
        with open(out, 'w', encoding='utf-8') as f:
            json.dump(dump, f, ensure_ascii=False, indent=1)
        self.log_info(f'calib {name}: {len(dump)} ocr boxes -> {out}')


if __name__ == '__main__':
    # stdout 按 utf-8 输出, 避免中文乱码
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    CalibTask.name_suffix = sys.argv[1] if len(sys.argv) > 1 else 'default'
    run_task(config, task=CalibTask)
