import re
import time

import win32api
import win32con
import win32gui
import win32process

from ok import BaseTask, og


class MyBaseTask(BaseTask):
    """无限暖暖任务基类: 提供前台保活、Esc 菜单导航与 OCR 调试等通用能力"""

    # 认为暂停菜单(美鸭梨)已打开的判定特征。
    # 注意: 只用「美鸭梨」—— 大世界右上角快捷入口排也有「任务/商城」等字, 会误判
    MENU_MARKERS = [
        re.compile('美鸭梨'),
    ]
    LOGIN_TEXT = re.compile('点击进入游戏|击进入|进入游戏|Click to Start|Start Game')
    CONFIRM = re.compile('确定|确认|OK|Confirm')

    def ensure_foreground(self):
        """pynput 交互依赖前台; 游戏以 admin 运行时本程序也必须 admin, 否则输入被 UIPI 丢弃"""
        if not self.force_foreground():
            self.log_error('cannot bring game window to front, abort.', notify=True)
            return False
        return True

    def ensure_in_game(self, time_out=180):
        """从登录页推进到大世界: 点「点击进入游戏」→ 等加载 → 清理弹窗"""
        start = time.time()
        while time.time() - start < time_out:
            login = self.wait_ocr(match=self.LOGIN_TEXT, time_out=3, log=True)
            if login:
                self.log_info('login page detected, clicking to enter game...')
                self.click_box(login[0], after_sleep=2)
                # 加载到主界面需要一段时间, 点击后先等待
                self.sleep(20)
                continue
            # 非登录页: 尝试清理弹窗(月卡/道具过期/网络异常等)
            popup = self.wait_click_ocr(match=self.CONFIRM, time_out=2, log=True)
            if popup:
                self.log_info('popup confirmed.')
                self.sleep(2)
                continue
            # 无登录入口且无弹窗: 用 Esc 菜单能否打开判定是否已在大世界
            self.send_key('esc', after_sleep=1.5)
            if self.ocr(match=self.MENU_MARKERS, log=True):
                self.send_key('esc', after_sleep=1.5) # 关掉菜单
                self.log_info('already in game (open world).')
                return True
        self.log_error('ensure_in_game timeout.', notify=True)
        self.debug_screenshot('ensure_in_game_timeout')
        return False

    def force_foreground(self, attempts=5):
        """强制把游戏窗口带到前台(pynput 交互依赖前台, 需在点击前调用)"""
        hwnd_win = og.device_manager.hwnd_window
        for _ in range(attempts):
            if hwnd_win.is_foreground():
                return True
            try: # AttachThreadInput 绕过 SetForegroundWindow 的前台限制
                fg_hwnd = win32gui.GetForegroundWindow()
                fg_tid = win32process.GetWindowThreadProcessId(fg_hwnd)[0]
                cur_tid = win32api.GetCurrentThreadId()
                fg_tid and win32process.AttachThreadInput(cur_tid, fg_tid, True)
                try:
                    hwnd_win.bring_to_front()
                finally:
                    fg_tid and win32process.AttachThreadInput(cur_tid, fg_tid, False)
            except Exception:
                hwnd_win.bring_to_front()
            self.sleep(0.5)
        return hwnd_win.is_foreground()

    def open_pause_menu(self, attempts=3):
        """连按 Esc 打开暂停菜单, 通过 OCR 特征确认是否打开"""
        for _ in range(attempts):
            self.send_key('esc', after_sleep=1)
            if self.ocr(match=self.MENU_MARKERS, log=True):
                return True
        return False

    def close_pause_menu(self, attempts=3):
        """连按 Esc 直到菜单特征消失, 回到大世界"""
        for _ in range(attempts):
            if not self.ocr(match=self.MENU_MARKERS):
                return True
            self.send_key('esc', after_sleep=1)
        return not self.ocr(match=self.MENU_MARKERS)

    def click_menu_entry(self, entry, time_out=4):
        """在当前菜单页找到入口文字并点击, 返回点击的 Box 或 None"""
        boxes = self.wait_ocr(match=entry, time_out=time_out, log=True)
        if not boxes:
            return None
        self.click_box(boxes[0], after_sleep=1)
        return boxes[0]

    def confirm_dialog(self, time_out=3):
        """领取奖励后可能弹出确认框, 有则点掉, 无则静默超时"""
        return self.wait_click_ocr(match=self.CONFIRM, time_out=time_out, log=True)

    def debug_screenshot(self, name):
        """流程卡住时保存截图, 便于用 debug 模式校准 OCR 关键字"""
        self.screenshot(name=f'nikki_{name}')
