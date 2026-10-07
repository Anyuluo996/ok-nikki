import re

from qfluentwidgets import FluentIcon

from src.tasks.MyBaseTask import MyBaseTask


class MineTask(MyBaseTask):
    """美鸭梨挖掘: 进入挖掘页, 有成品则「一键收获」并「再次挖掘」形成循环;
    队列全新为空(从未设置挖掘目标)时提示手动设置一次, 之后即可每日自动循环"""

    GATHER = re.compile('一\\s*键\\s*收\\s*获')
    DIG_AGAIN = re.compile('再次挖掘|继续挖掘|开始挖掘|挖\\s*掘')
    DIGGING_TIMER = re.compile(r'\d{2}:\d{2}:\d{2}')
    NEED_SETUP = re.compile('选择物资|挖掘队列（0/|挖掘队列\\(0/')
    # 右侧「一键收获」金色按钮: 艺术字 OCR 不稳, 按标定坐标兜底(1080p (1789,797))
    HARVEST_POS = (0.932, 0.738)
    # 底部「挖掘」按钮: 收获后无「再次挖掘」弹窗时直接点它续挖(1080p (1197,953))
    DIG_BUTTON_POS = (0.623, 0.882)
    # 菜单第一页网格里「美鸭梨挖掘」图标中心(1080p 标定 (941,503))。
    # 标签是艺术字, OCR 时灵时不灵, 找不到文字时按坐标 hover+Enter 兜底
    MINE_ICON_POS = (0.490, 0.466)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = "Meiyali Dig"
        self.description = "Claim finished Meiyali dig rewards and start digging again."
        self.icon = FluentIcon.SHOPPING_CART
        self.default_config.update({
            'Dig Again After Harvest': True,
            'Allow Foreground Steal': True,
        })
        self.config_description.update({
            'Dig Again After Harvest': 'Start the same dig again right after harvesting.',
            'Allow Foreground Steal': 'Allow bringing the game to front for a real click when the background method fails.',
        })

    def run(self, **kwargs):
        self.info_clear()
        if not self.ensure_in_game():
            self.log_error('MineTask: not in game.', notify=True)
            return
        if not self.mine_flow():
            self.back_to_world()
            return
        self.back_to_world()
        self.log_info('MineTask finished.', notify=True)

    def mine_flow(self):
        """挖掘接力: 从菜单(或大世界自行开菜单)进入挖掘页, 收获后退回菜单不回世界。
        邮件和挖掘入口同在美鸭梨菜单, 供 run_daily 与邮件接力省一次进出"""
        if not self.open_mine_page():
            self.log_error('MineTask: cannot open the dig page, retries exhausted.', notify=True)
            self.debug_screenshot('mine_page_not_open')
            self.close_pause_menu()
            return False
        self.harvest()
        # 挖掘页 -> 菜单(接力: 邮件/挖掘同界面)
        self.send_key('esc', after_sleep=2)
        if not self.ocr(match=self.MENU_MARKERS):
            self.close_pause_menu()
        return True

    def open_mine_page(self, attempts=3):
        """打开挖掘页。网格入口不吃 PostMessage 点击:
        1) 悬停+Enter(纯后台, 光标短暂移过去再还原); 2) 真实点击(默认允许抢前台)"""
        for _ in range(attempts):
            if self.page_sig() == 'mine':
                return True
            if not self.open_pause_menu():
                return False
            entry = next((b for b in self.ocr(log=False) if '美鸭梨挖掘' in b.name), None)
            if entry:
                # 热区在图标上(文字上方 ~55px), 点文字无效
                cx, cy = entry.x + entry.width / 2, entry.y - self.px(55)
            else:
                # OCR 漏识别艺术字标签时, 按标定图标位置兜底
                cx, cy = self.MINE_ICON_POS[0] * self.width, self.MINE_ICON_POS[1] * self.height
            if self.hover_and_enter(cx, cy):
                if self.wait_page('mine', 4):
                    return True
            if self.config.get('Allow Foreground Steal'):
                self.real_click(cx, cy)
                if self.wait_page('mine', 5):
                    return True
            # 可能翻页了, 回第一页再来
            self.close_pause_menu()
        return self.page_sig() == 'mine'

    def harvest(self):
        """一键收获 → 继续挖掘: 收获弹窗「再次挖掘」优先, 没弹窗就点底部「挖掘」按钮"""
        self.park_cursor()
        self.sleep(0.5)
        gather = self.wait_ocr(match=self.GATHER, time_out=3, log=True)
        if gather:
            self.click_box(gather[0], down_time=0.15, after_sleep=1.5)
        else:
            # 「一键收获」艺术字识别不到, 按标定坐标点金色按钮
            self.click(*self.HARVEST_POS, down_time=0.15, after_sleep=1.5)
        self.confirm_dialog()
        self.close_reward_page(3)
        if not self.config.get('Dig Again After Harvest'):
            self.info_set(self.tr('Dig'), self.tr('Harvested'))
            self.log_info('MineTask: harvested (no re-dig).', notify=True)
            return
        again = self.wait_ocr(match=self.DIG_AGAIN, time_out=3, log=True)
        if again:
            self.click_box(again[0], down_time=0.15, after_sleep=2)
            self.confirm_dialog()
        elif not self.ocr(match=self.DIGGING_TIMER):
            # 没有「再次挖掘」弹窗且队列也不在倒计时: 点底部「挖掘」按钮续挖
            self.click(*self.DIG_BUTTON_POS, down_time=0.15, after_sleep=2)
            self.confirm_dialog()
            if self.ocr(match=self.NEED_SETUP):
                self.info_set(self.tr('Dig'), self.tr('Need Manual Setup'))
                self.log_error('MineTask: no dig target set, please set it manually once.', notify=True)
                return
        if self.ocr(match=self.DIGGING_TIMER):
            self.info_set(self.tr('Dig'), self.tr('Harvested & Restarted'))
            self.log_info('MineTask: harvested and digging again.', notify=True)
        else:
            self.info_set(self.tr('Dig'), self.tr('Harvested'))
            self.log_info('MineTask: harvested.', notify=True)
