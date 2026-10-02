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

    # 页面特征 → 页面名。用于流程状态判定与「回大世界」的逐层退出
    # 注意: 大世界顶栏快捷排也有「奇想日历/商城」等文字, 页面特征不能用这些标题词;
    # 判定顺序即优先级: 朝夕心愿页标题也是「每日灵感」, 必须用「每日4点刷新」先于日历页判定;
    # 日历页右页有「幻境挑战」分区标题, 幻境 hub 特征只能用四个幻境名
    PAGE_SIGS = {
        'mine': re.compile('挖掘队列|选择物资|采集物资|一键收获|再次挖掘'),
        'mail': re.compile('系统邮件|好友邮件|删已读|删除邮件'),
        'zhaoxi': re.compile('每日4点刷新'),
        'shop': re.compile('星途珍存|清空购物车|历史低价'),
        'chat': re.compile('点击输入消息|跳转至好友'),
        'realm': re.compile('心之突破幻境|素材激化幻境|祝福闪光幻境|魔物试炼幻境|快速挑战'),
        'passport': re.compile('悠远颂歌|旅行任务'),
        'calendar': re.compile('阅历挑战|每日灵感'),
    }

    def page_sig(self, boxes=None):
        """当前画面属于哪个页面: 子页特征优先, 其次美鸭梨菜单, 都不中=大世界"""
        if boxes is None:
            boxes = self.ocr(log=False)
        joined = ' '.join(b.name for b in boxes)
        for name, p in self.PAGE_SIGS.items():
            if p.search(joined):
                return name
        if '美鸭梨' in joined:
            return 'menu'
        return 'other'

    def wait_page(self, sig, time_out=6):
        """等待某页面出现"""
        start = time.time()
        while time.time() - start < time_out:
            if self.page_sig() == sig:
                return True
            self.sleep(1)
        return False

    def back_to_world(self, max_esc=6):
        """逐层退出所有子页/菜单/弹窗, 回到大世界。
        弹窗(如试炼奖励确认)不吃 Esc, 优先点「取消/关闭」按钮"""
        for _ in range(max_esc):
            boxes = self.ocr(log=False)
            cancel = next((b for b in boxes if re.fullmatch('取消|关闭', b.name.strip())), None)
            if cancel:
                self.click_box(cancel, down_time=0.15, after_sleep=1.5)
                continue
            if self.page_sig(boxes) == 'other':
                return True
            self.send_key('esc', after_sleep=2)
        return self.page_sig() == 'other'

    def park_cursor(self):
        """真实光标停到窗口右下角边缘: 游戏会跟随光标弹 tooltip/把光标画在画面中央, 挡 OCR"""
        try:
            hwnd_win = og.device_manager.hwnd_window
            rect = win32gui.GetWindowRect(hwnd_win.hwnd)
            win32api.SetCursorPos((rect[2] - 2, rect[3] - 2))
        except Exception:
            pass

    def find_template(self, name, time_out=4):
        """图像识别找模板按钮(比 OCR 精确), 轮询直到超时, 返回 Box 或 None"""
        start = time.time()
        while time.time() - start < time_out:
            try:
                boxes = self.find_feature(name)
            except Exception:
                boxes = []
            if boxes:
                return boxes[0]
            self.sleep(1)
        return None

    def open_whim_calendar(self, attempts=3):
        """打开奇想日历: L 键(后台实测可用)优先, 顶栏图标真实点击兜底"""
        if self.page_sig() == 'calendar':
            return True
        for _ in range(attempts):
            self.send_key('l', after_sleep=3)
            if self.page_sig() == 'calendar':
                return True
            entry = next((b for b in self.ocr(log=False)
                          if '奇想日历' in b.name and b.y + b.height / 2 < 130), None)
            if entry:
                self.real_click(entry.x + entry.width / 2, entry.y - 45)
                if self.page_sig() == 'calendar':
                    return True
            self.close_pause_menu()
        return False

    def real_click(self, x, y, down_time=0.15):
        """真实硬件点击。美鸭梨菜单的网格入口不吃 PostMessage(Enhanced Input 走 RawInput),
        只认 SendInput 级真实输入且要求游戏在前台; 游戏以 admin 运行, 本程序也须 admin。
        注意: 会把游戏拉到前台并接管鼠标, 后台模式请优先 hover_and_enter"""
        hwnd_win = og.device_manager.hwnd_window
        if not hwnd_win.is_foreground():
            self.force_foreground()
            self.sleep(0.8)
        abs_x, abs_y = self.executor.method.get_abs_cords(int(x), int(y))
        win32api.SetCursorPos((int(abs_x), int(abs_y)))
        self.sleep(0.15)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
        time.sleep(down_time)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
        self.sleep(0.3)
        self.park_cursor()
        return True

    def hover_and_enter(self, x, y, key='enter', hover_time=0.8):
        """后台温和激活: 真实光标短暂移到目标(游戏悬停判定跟真实光标) + posted 确认键。
        不抢焦点; 光标点击后还原"""
        hwnd_win = og.device_manager.hwnd_window
        saved = win32api.GetCursorPos()
        abs_x, abs_y = self.executor.method.get_abs_cords(int(x), int(y))
        win32api.SetCursorPos((int(abs_x), int(abs_y)))
        self.sleep(hover_time)
        self.send_key(key, after_sleep=2)
        win32api.SetCursorPos(saved)
        return True

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
            if self.open_pause_menu(attempts=2):
                self.close_pause_menu()
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
        """确保暂停菜单打开。先查再按: 游戏把每条 esc 都当开关, 盲按会开了又关;
        按完等 2s 让菜单动画结束再 OCR 确认"""
        for _ in range(attempts):
            if self.ocr(match=self.MENU_MARKERS, log=True):
                return True
            self.send_key('esc', after_sleep=2)
        return bool(self.ocr(match=self.MENU_MARKERS, log=True))

    def close_pause_menu(self, attempts=3):
        """连按 Esc 直到菜单特征消失, 回到大世界(同样先查再按)"""
        for _ in range(attempts):
            if not self.ocr(match=self.MENU_MARKERS):
                return True
            self.send_key('esc', after_sleep=2)
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
