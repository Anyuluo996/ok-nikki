"""一次性: 从实测截图裁剪 UI 按钮模板, 生成 assets/imgs/*.png + assets/coco_annotations.json。
坐标按 1920x1080 截图手工量取, 新模板往 CROPS 里加后重跑本脚本。
"""
import json
import os

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'screenshots', '02-05-19.430_nikki_ensure_in_game_timeout_original.png')
CAL = os.path.join(ROOT, 'screenshots', '01-47-07.616_nikki_calendar_no_claim_original.png')

# name -> (source, (x1, y1, x2, y2))  1920x1080
CROPS = {
    # 心之突破幻境页 + 试炼奖励弹窗
    'InjectEnergyButton': (SRC, (975, 678, 1265, 737)),     # 金色「注入活跃能量」按钮
    'CancelButton': (SRC, (655, 678, 945, 737)),           # 弹窗「取消」按钮
    'QuickChallengeButton': (SRC, (1070, 950, 1340, 1020)), # 右下「快速挑战」
    'ChallengeButton': (SRC, (1390, 950, 1660, 1020)),      # 右下「挑战」
    'WeeklyRemainLabel': (SRC, (1300, 888, 1565, 950)),     # 「本周剩余奖励次数:」静态标签
    'WeeklyPageTitle': (SRC, (95, 22, 330, 85)),            # 页面标题「心之突破幻境」
    # 奇想日历页
    'CalendarRealmCrystal': (CAL, (1035, 150, 1245, 335)),  # 幻境挑战卡的水晶图标(静态, 数字会变)
    'CalendarZhaoxiCard': (CAL, (215, 165, 855, 600)),      # 左页「朝夕心愿」卡
}

def main():
    images, annotations, categories = [], [], []
    for i, (name, (src, (x1, y1, x2, y2))) in enumerate(CROPS.items(), start=1):
        img = Image.open(src)
        crop = img.crop((x1, y1, x2, y2))
        w, h = crop.size
        fname = f'imgs/{name}.png'
        out = os.path.join(ROOT, 'assets', fname)
        os.makedirs(os.path.dirname(out), exist_ok=True)
        crop.save(out)
        images.append({'id': i, 'file_name': fname, 'width': w, 'height': h})
        categories.append({'id': i, 'name': name, 'supercategory': ''})
        annotations.append({'id': i, 'image_id': i, 'category_id': i,
                            'bbox': [0, 0, w, h], 'area': w * h, 'iscrowd': 0})
        print(f'{name}: {w}x{h}')
    data = {'images': images, 'annotations': annotations, 'categories': categories}
    with open(os.path.join(ROOT, 'assets', 'coco_annotations.json'), 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    print('wrote assets/coco_annotations.json')

if __name__ == '__main__':
    main()
