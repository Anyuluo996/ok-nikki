import re

from qfluentwidgets import FluentIcon

from src.tasks.MyBaseTask import MyBaseTask


class MineTask(MyBaseTask):
    """美鸭梨挖掘: 进入挖掘页, 有成品则「一键收获」并「再次挖掘」形成循环;
    队列全新为空(从未设置挖掘目标)时提示手动设置一次, 之后即可每日自动循环"""

    GATHER = re.compile('一键收获')
    DIG_AGAIN = re.compile('再次挖掘|继续挖掘|开始挖掘')
    DIGGING_TIMER = re.compile(r'\d{2}:\d{2}:\d{2}')
    NEED_SETUP = re.compile('选择物资|挖掘队列（0/|挖掘队列\\(0/')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = "Meiyali Dig"
        self.description = "Claim finished Meiyali dig rewards and start digging again."
        self.icon = FluentIcon.SHOPPING_CART
        self.default_config.update({
            'Dig Again After Harvest': True,
            'Allow Foreground Steal': False,
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
            self.log_error('MineTask: cannot open the dig page in background, '
                           'enable "Allow Foreground Steal" or open it manually.', notify=True)
            self.debug_screenshot('mine_page_not_open')
            self.close_pause_menu()
            return False
        self.harvest()
        # 挖掘页 -> 菜单(接力: 邮件/挖掘同界面)
        self.send_key('esc', after_sleep=2)
        if not self.ocr(match=self.MENU_MARKERS):
            self.close_pause_menu()
        return True

    def open_mine_page(self, attempts=2):
        """打开挖掘页。网格入口不吃 PostMessage 点击:
        1) 悬停+Enter(纯后台, 光标短暂移过去再还原); 2) 真实点击(会抢前台, 需配置允许)"""
        for _ in range(attempts):
            if self.page_sig() == 'mine':
                return True
            if not self.open_pause_menu():
                return False
            entry = next((b for b in self.ocr(log=False) if '美鸭梨挖掘' in b.name), None)
            if not entry:
                self.sleep(1)
                continue
            # 热区在图标上(文字上方 ~55px), 点文字无效
            cx, cy = entry.x + entry.width / 2, entry.y - 55
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
        self.park_cursor()
        self.sleep(0.5)
        gather = self.wait_ocr(match=self.GATHER, time_out=3, log=True)
        if not gather:
            if self.ocr(match=self.DIGGING_TIMER, log=True):
                self.info_set(self.tr('Dig'), self.tr('In Progress'))
                self.log_info('MineTask: queues are digging, nothing to harvest yet.')
            elif self.ocr(match=self.NEED_SETUP, log=True):
                self.info_set(self.tr('Dig'), self.tr('Need Manual Setup'))
                self.log_error('MineTask: no dig target set, please set it manually once.', notify=True)
            else:
                self.debug_screenshot('mine_unknown_state')
                self.log_info('MineTask: no harvest button found.')
            return
        self.click_box(gather[0], down_time=0.15, after_sleep=1.5)
        self.confirm_dialog()
        # 收获弹窗上直接「再次挖掘」, 用相同物资续挖
        again = self.wait_ocr(match=self.DIG_AGAIN, time_out=4, log=True)
        if again and self.config.get('Dig Again After Harvest'):
            self.click_box(again[0], down_time=0.15, after_sleep=2)
            self.confirm_dialog()
            self.info_set(self.tr('Dig'), self.tr('Harvested & Restarted'))
            self.log_info('MineTask: harvested and digging again.', notify=True)
        else:
            self.info_set(self.tr('Dig'), self.tr('Harvested'))
            self.log_info('MineTask: harvested (no re-dig).', notify=True)
