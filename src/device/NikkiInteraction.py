"""无限暖暖专用交互(后台执行核心)。

实测结论(2026-10-03):
- UE5 失焦停止渲染, 需 WM_ACTIVATE 假激活保活, 否则 WGC 永远等不到帧。
- 游戏丢瞬发点击(真实输入 0.02s 都会丢), posted down/up 必须保留 ≥0.15s 间隔。
- 游戏鼠标 UI 判定跟随真实光标位置, 纯 PostMessage 点击无效,
  必须 SetCursorPos 把真实光标带到目标位(operate 会恢复原位, BlockInput 期间用户无感)。
- 键盘走 WM_KEYDOWN/UP + scancode; 不能发 WM_CHAR —— 会被当成第二次按键(esc 开了又关)。
"""
import time

import win32api
import win32con

from ok.device.interaction_methods.genshin import GenshinInteraction
from ok.util.logger import Logger

logger = Logger.get_logger(__name__)


class NikkiInteraction(GenshinInteraction):

    def do_click(self, x=-1, y=-1, move_back=False, name=None, down_time=0.02, move=True, key="left"):
        x, y = int(round(x)), int(round(y))
        if x < 0 or y < 0:
            x, y = round(self.capture.width * 0.5), round(self.capture.height * 0.5)
        abs_x, abs_y = self.capture.get_abs_cords(x, y)
        click_pos = win32api.MAKELONG(x, y)
        if key == "right":
            btn_down, btn_up, mk = win32con.WM_RBUTTONDOWN, win32con.WM_RBUTTONUP, win32con.MK_RBUTTON
        elif key == "middle":
            btn_down, btn_up, mk = win32con.WM_MBUTTONDOWN, win32con.WM_MBUTTONUP, win32con.MK_MBUTTON
        else:
            btn_down, btn_up, mk = win32con.WM_LBUTTONDOWN, win32con.WM_LBUTTONUP, win32con.MK_LBUTTON
        win32api.SetCursorPos((int(abs_x), int(abs_y)))
        time.sleep(0.05)
        self.post(btn_down, mk, click_pos)
        time.sleep(max(down_time, 0.15))
        self.post(btn_up, 0, click_pos)

    def do_send_key(self, key, down_time=0.02):
        vk = self.get_key_by_str(key)
        sc = win32api.MapVirtualKey(vk & 0xFF, 0)
        self.post(win32con.WM_KEYDOWN, vk, 0x1e0001 | (sc << 16))
        time.sleep(max(down_time, 0.15))
        self.post(win32con.WM_KEYUP, vk, 0xc01e0001 | (sc << 16))

    def operate(self, fun, block=False):
        """后台时保活渲染并短暂接管光标, 结束后恢复; 不发 deactivate 保持帧流。"""
        bg = not self.hwnd_window.is_foreground()
        if bg:
            if block:
                self.block_input()
            self.cursor_position = win32api.GetCursorPos()
            self.activate()
        try:
            return fun()
        except Exception as e:
            logger.error('operate exception', e)
            return None
        finally:
            if bg:
                if block:
                    self.unblock_input()
                time.sleep(0.02)
                win32api.SetCursorPos(self.cursor_position)
