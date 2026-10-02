import os

from src.device.NikkiInteraction import NikkiInteraction

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
    'wait_until_before_delay': 0,
    'wait_until_check_delay': 0,
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
        'start_exe': False, #不自动拉起游戏, 请先手动启动游戏并进入大世界
        'interaction': [NikkiInteraction, 'Pynput', 'PostMessage', 'Genshin', 'PyDirect'], #NikkiInteraction: 后台保活渲染+定时消息, 见 src/device/NikkiInteraction.py
        'capture_method': ['WGC', 'BitBlt_RenderFull', 'BitBlt'],  # 游戏需窗口化; 全屏下 WGC 首帧会挂
        'check_hdr': False, #当用户开启AutoHDR时候提示用户, 但不禁止使用
        'force_no_hdr': False, #True=当用户开启AutoHDR时候禁止使用
        'require_bg': True, #要求使用后台截图
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
        'default_horizontal_variance': 0.002, #默认x偏移, 查找不传box的时候, 会根据coco坐标, match偏移box内的
        'default_vertical_variance': 0.002, #默认y偏移
        'default_threshold': 0.8, #默认threshold
    },
    'version': version, #版本
    'onetime_tasks': [  # 用户点击触发的任务
        [ "src.tasks.DailyTask", "DailyTask" ],
        [ "src.tasks.CalendarTask", "CalendarTask" ],
        [ "src.tasks.MineTask", "MineTask" ],
        ["ok", "DiagnosisTask"],
    ],
}
