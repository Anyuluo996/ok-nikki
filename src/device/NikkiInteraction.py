"""无限暖暖专用交互(后台执行核心)。

实测结论(2026-10-03):
- UE5 失焦停止渲染, 需 WM_ACTIVATE 假激活保活, 否则 WGC 永远等不到帧。
- 游戏丢瞬发点击(真实输入 0.02s 都会丢), posted down/up 必须保留 ≥0.15s 间隔。
- 游戏鼠标 UI 判定跟随真实光标位置, 纯 PostMessage 点击无效,
  必须 SetCursorPos 把真实光标带到目标位(operate 会恢复原位, BlockInput 期间用户无感)。
- 键盘走 WM_KEYDOWN/UP + scancode; 不能发 WM_CHAR —— 会被当成第二次按键(esc 开了又关)。

自 okww/oknte 集成(2026-10-05):
- _input_lock(oknte NTEInteraction 同款): TriggerTask 与一次性任务并发调交互时,
  光标保存/还原和消息序列不会交叉污染。
- 每次输入前 try_activate(okww PostMessage 同款): 长序列中两次 operate 之间
  补发 WM_ACTIVATE, UE5 后台渲染不中断。
- _operating 计数器: MouseResetTask 据此避让, 不在点击序列中间拉回光标。
- send_key_down/up 覆写: 父类 GenshinInteraction 的实现不发 WM_KEYUP、会发 WM_CHAR、
  还调 deactivate 断帧流, 三条都违反上面的实测结论, 必须挡掉(自定义任务长按键用)。
- 拖拽(swipe)/mouse_down+mouse_up 分离调用【未适配】: 父类每段各走一次 operate,
  down 之后光标立即还原, UE 的悬停判定跟不上; 自定义任务请勿使用, 需要时按
  do_click 模式补一次性 operate 包住整个 down→move→up 的覆写再实测。
"""
import threading
import time
from contextlib import contextmanager

import win32api
import win32con
import win32gui

from ok.device.interaction_methods.genshin import GenshinInteraction
from ok.util.logger import Logger

logger = Logger.get_logger(__name__)


class NikkiInteraction(GenshinInteraction):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._input_lock = threading.RLock()
        self._operating = 0

    def do_click(self, x=-1, y=-1, move_back=False, name=None, down_time=0.02, move=True, key="left"):
        with self._input_lock:
            self.try_activate()
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
        with self._input_lock:
            self.try_activate()
            vk = self.get_key_by_str(key)
            sc = win32api.MapVirtualKey(vk & 0xFF, 0)
            self.post(win32con.WM_KEYDOWN, vk, 0x1e0001 | (sc << 16))
            time.sleep(max(down_time, 0.15))
            self.post(win32con.WM_KEYUP, vk, 0xc01e0001 | (sc << 16))

    def send_key_down(self, key):
        """长按键按下。覆写父类: 不发 WM_CHAR(会被当成第二次按键)。"""
        with self._input_lock:
            self.try_activate()
            vk = self.get_key_by_str(key)
            sc = win32api.MapVirtualKey(vk & 0xFF, 0)
            self.post(win32con.WM_KEYDOWN, vk, 0x1e0001 | (sc << 16))

    def send_key_up(self, key):
        """长按键抬起。覆写父类: 父类实现不发 WM_KEYUP 且调 deactivate 断帧流。"""
        with self._input_lock:
            vk = self.get_key_by_str(key)
            sc = win32api.MapVirtualKey(vk & 0xFF, 0)
            self.post(win32con.WM_KEYUP, vk, 0xc01e0001 | (sc << 16))

    def post(self, message, wParam=0, lParam=0):
        # 句柄失效时 win32gui.PostMessage 会抛 error(1400), right_click 等不经
        # operate 的直调路径没有兜底, 这里统一吞掉(与 PostMessageInteraction.post 一致)
        try:
            win32gui.PostMessage(self.hwnd, message, wParam, lParam)
        except Exception as e:
            logger.error(f'post message error {message}: {e}')

    @contextmanager
    def hold_operating(self):
        """供不走 operate() 的真实光标操作(如 MyBaseTask.hover_and_enter)声明
        序列进行中, MouseResetTask 据此避让拉回光标。"""
        self._operating += 1
        try:
            yield
        finally:
            self._operating -= 1

    def operate(self, fun, block=False):
        """后台时保活渲染并短暂接管光标, 结束后恢复; 不发 deactivate 保持帧流。"""
        with self._input_lock:
            self._operating += 1
            bg = not self.hwnd_window.is_foreground()
            blocked = False
            try:
                if bg:
                    if block:
                        self.block_input()
                        blocked = True
                    # GetCursorPos 在安全桌面(UAC)下会抛, 必须在 try 内, 否则
                    # BlockInput 永不解锁、_operating 泄漏
                    self.cursor_position = win32api.GetCursorPos()
                    self.activate()
                return fun()
            except Exception as e:
                logger.error('operate exception', e)
                return None
            finally:
                if bg:
                    if blocked:
                        self.unblock_input()
                    time.sleep(0.02)
                    if self.cursor_position:
                        try:
                            win32api.SetCursorPos(self.cursor_position)
                        except Exception:
                            pass
                self._operating -= 1
