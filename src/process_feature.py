"""模板加载期预处理(feature_processor, 机制同 okww/oknte)。

config.template_matching 里已把 process_feature 挂为 feature_processor:
FeatureSet 加载 COCO 标注切出的模板时回调 process_feature(feature_name, feature),
按特征名对模板做一次性预处理并缓存。匹配时任务侧必须用同一函数喂帧, 例如:

    self.find_feature('WeeklyRemainLabel', frame_processor=binarize_for_matching)
    (MyBaseTask.find_template 已透传 frame_processor/threshold)

适用场景: 浅色文字/图标模板在动态背景或动图 UI 上直接匹配不稳,
模板和帧同时亮度二值化/颜色掩码后可以显著更稳(参考 okww skip_dialog、
illusive_realm_exit 等特征的用法)。
"""
import cv2
import numpy as np

lower_white = np.array([244, 244, 244], dtype=np.uint8)
upper_white = np.array([255, 255, 255], dtype=np.uint8)


def convert_bw(cv_image):
    """白色(244-255)像素掩码转黑白图(命中白色, 三通道)。"""
    match_mask = cv2.inRange(cv_image, lower_white, upper_white)
    return cv2.cvtColor(match_mask, cv2.COLOR_GRAY2BGR)


def binarize_for_matching(image, threshold=244):
    """亮度二值化: >threshold 纯白, 其余纯黑(单通道)。白字模板首选。"""
    gray_image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
    _, binary_image = cv2.threshold(gray_image, threshold, 255, cv2.THRESH_BINARY)
    return binary_image


# 特征名 → 模板预处理。需要时在此登记, 例:
# 'WeeklyRemainLabel': binarize_for_matching,
_PREPROCESSORS = {}


def process_feature(feature_name, feature):
    processor = _PREPROCESSORS.get(feature_name)
    if processor is not None:
        feature.mat = processor(feature.mat)
