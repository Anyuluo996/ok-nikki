import math

import win32api

from ok import TriggerTask, Logger

logger = Logger.get_logger(__name__)


class MouseResetTask(TriggerTask):
    """后台运行时游戏可能拖走物理光标(UE 引擎视角/中央复位), 持续检测并在
    光标被拉向窗口中心时还原到用户原位。移植自 okww 同名任务。

    判定条件(三者同时满足才拉回, 避免误伤用户的正常移动):
    - 游戏窗口在后台(不可见)
    - 光标离上次采样点超过 200px(不是用户自己在慢慢动)
    - 光标落在窗口中心 50px 半径内(UE 拖光标的典型落点)
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.default_config = {'_enabled': True}
        self.trigger_interval = 10
        self.name = "Mouse Reset"
        self.description = "Pull the mouse back if the game drags it away while running in background."
        self.mouse_pos = None

    def enable(self):
        super().enable()
        self.run()

    def run(self):
        if not self.enabled or self.is_browser():
            return
        logger.debug('schedule mouse reset')
        self.post_mouse_reset(0.01)

    def post_mouse_reset(self, delay):
        if self.enabled:
            self.handler.post(self.mouse_reset, delay, remove_existing=True)

    def mouse_reset(self):
        if not self.enabled or self.is_browser():
            return
        try:
            interaction = self.executor.interaction
            # 仅在带 _operating 避让的交互后端(NikkiInteraction)下生效:
            # Genshin 等后端也会把光标带到点击位但没有避让标记, 拉回会打断点击
            if not hasattr(interaction, '_operating'):
                return
            # 点击序列进行中(游戏此刻需要真实光标在目标位), 避让不拉回
            if interaction._operating:
                self.post_mouse_reset(0.05)
                return
            current_position = win32api.GetCursorPos()
            if self.mouse_pos and self.hwnd and self.hwnd.exists and not self.hwnd.visible \
                    and interaction and interaction.capture:
                center_pos = interaction.capture.get_abs_cords(self.width_of_screen(0.5),
                                                               self.height_of_screen(0.5))
                close_to_center = math.sqrt(
                    (current_position[0] - center_pos[0]) ** 2
                    + (current_position[1] - center_pos[1]) ** 2
                ) < 50
                distance = math.sqrt(
                    (current_position[0] - self.mouse_pos[0]) ** 2
                    + (current_position[1] - self.mouse_pos[1]) ** 2
                )
                if distance > 200 and close_to_center:
                    logger.info(f'move mouse back {self.mouse_pos}')
                    win32api.SetCursorPos(self.mouse_pos)
                    self.post_mouse_reset(1)
                    return
            self.mouse_pos = current_position
            self.post_mouse_reset(0.01)
        except Exception as e:
            logger.error('mouse_reset exception', e)
