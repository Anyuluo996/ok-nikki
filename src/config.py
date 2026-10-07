import os

from src.device.NikkiInteraction import NikkiInteraction
from src.process_feature import process_feature

version = "dev"
#不需要修改version, Github Action打包会自动修改

app_profile = os.environ.get("PYAPPIFY_APP_PROFILE", "")
gui_config = {
    'type': 'web' if app_profile.casefold() == 'web' else 'qt',
    'window_size': {
        'width': 1200,
        'height': 800,
        'min_width': 600,
        'min_height': 450,
    },
}
if gui_config['type'] == 'web':
    gui_config['launch_mode'] = 'pywebview'

config = {
    'custom_tasks': True, # 允许在界面中创建和编辑自定义任务
    'debug': False,  # 可选, 默认 False, main_debug.py 会置为 True
    'gui': gui_config,
    'config_folder': 'configs', #最好不要修改
    'gui_icon': 'icons/icon.png', #窗口图标
    'wait_until_settle_time': 0, #调用 wait_until时候, 在第一次满足条件的时候, 会等待再次检测, 以避免某些滑动动画没到预定位置就在动画路径中被检测到
    'ocr': { #OCR 引擎, onnxocr + OpenVINO CPU/NPU
        'lib': 'onnxocr',
        'auto_simplify': True, #自动繁体转简体
        'params': {
            'use_openvino': True,
        }
    },
    'windows': {  # 无限暖暖 Windows 客户端
        'exe': ['X6Game-Win64-Shipping.exe'], #游戏主进程(启动器是 InfinityNikki Launcher.exe)
        'hwnd_class': 'UnrealWindow', #UE5 窗口类名, 配合 exe 名精确匹配
        'start_exe': True, #自动拉起游戏: 窗口不在时用 devices.json 里记住的 full_path 启动
        'interaction': [NikkiInteraction, 'Pynput', 'PostMessage', 'Genshin', 'PyDirect'], #NikkiInteraction: 后台保活渲染+定时消息, 见 src/device/NikkiInteraction.py
        'capture_method': ['WGC', 'BitBlt_RenderFull', 'BitBlt'],  # 游戏需窗口化; 全屏下 WGC 首帧会挂
    },
    'start_timeout': 120,  # default 60
    'supported_resolution': {
        'ratio': '16:9', #支持的游戏分辨率
        'min_size': (1280, 720), #支持的最低游戏分辨率
        'resize_to': [(2560, 1440), (1920, 1080), (1600, 900), (1280, 720)], #可选, 如果非16:9自动缩放为 resize_to
    },
    'links': {}, #关于页显示的链接, 建好仓库/交流群后可补上
    'screenshots_folder': "screenshots", #截图存放目录, 每次重新启动会清空目录
    'gui_title': 'ok-nikki',  #窗口名
    'template_matching': { # 可选, 如使用OpenCV的模板匹配
        'coco_feature_json': os.path.join('assets', 'coco_annotations.json'), #coco格式标记, 需要png图片, 在debug模式运行后, 会对进行切图仅保留被标记部分以减少图片大小
        'feature_processor': process_feature, #模板加载期预处理钩子(src/process_feature.py), 按特征名做二值化等
        'default_horizontal_variance': 0.002, #默认x偏移, 查找不传box的时候, 会根据coco坐标, match偏移box内的
        'default_vertical_variance': 0.002, #默认y偏移
        'default_threshold': 0.8, #默认threshold
    },
    'version': version, #版本
    'onetime_tasks': [  # 用户点击触发的任务
        [ "src.tasks.DailyTask", "DailyTask" ],
        [ "src.tasks.CalendarTask", "CalendarTask" ],
        [ "src.tasks.RealmTask", "RealmTask" ],
        [ "src.tasks.PassportTask", "PassportTask" ],
        [ "src.tasks.MineTask", "MineTask" ],
        ["ok", "DiagnosisTask"],
    ],
    'trigger_tasks': [ # 后台常驻触发任务
        ["src.tasks.MouseResetTask", "MouseResetTask"], #游戏拖走光标时拉回原位(okww 移植)
    ],
}
