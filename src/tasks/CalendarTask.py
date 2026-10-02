import re

from qfluentwidgets import FluentIcon

from src.tasks.MyBaseTask import MyBaseTask


class CalendarTask(MyBaseTask):
    """奇想日历: L 键打开日历页, 领取可领的奖励, 并探查朝夕心愿(每日任务)进度"""

    # 页面特征不能用「奇想日历」标题词: 大世界顶栏快捷排也有同文字
    CLAIM = re.compile('一键领取|全部领取|领取全部|领取|收下|Claim')
    ZHAOXI = re.compile('朝夕心愿')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = "Whim Calendar"
        self.description = "Open the Whim Calendar, claim available rewards and check daily quests."
        self.icon = FluentIcon.CALENDAR
        self.default_config.update({
            'Claim Calendar Rewards': True,
            'Open Zhaoxi Quests': True,
        })
        self.config_description.update({
            'Claim Calendar Rewards': 'Claim available rewards on the Whim Calendar page.',
            'Open Zhaoxi Quests': 'Open the Zhaoxi daily quest page to check progress.',
        })

    def run(self):
        self.info_clear()
        if not self.ensure_in_game():
            self.log_error('CalendarTask: not in game.', notify=True)
            return
        if not self.open_calendar():
            self.log_error('CalendarTask: cannot open the Whim Calendar.', notify=True)
            self.debug_screenshot('calendar_not_open')
            self.back_to_world()
            return
        if self.config.get('Claim Calendar Rewards'):
            self.claim_rewards()
        if self.config.get('Open Zhaoxi Quests'):
            self.open_zhaoxi()
        self.back_to_world()
        self.log_info('CalendarTask finished.', notify=True)

    def open_calendar(self, attempts=3):
        """打开奇想日历: L 键(实测后台可用)优先, 顶栏入口 OCR 点击兜底"""
        if self.page_sig() == 'calendar':
            return True
        for _ in range(attempts):
            self.send_key('l', after_sleep=3)
            if self.page_sig() == 'calendar':
                return True
            # L 没中: 顶栏「奇想日历」标签点击(热区为图标且世界 HUD 只吃真实点击)
            entry = next((b for b in self.ocr(log=False)
                          if '奇想日历' in b.name and b.y + b.height / 2 < 130), None)
            if entry:
                self.real_click(entry.x + entry.width / 2, entry.y - 45)
                if self.page_sig() == 'calendar':
                    return True
            self.close_pause_menu()
        return False

    def claim_rewards(self):
        self.park_cursor()
        self.sleep(0.5)
        claimed = 0
        claim = self.wait_ocr(match=self.CLAIM, time_out=3, log=True)
        while claim and claimed < 5: # 逐个领, 最多 5 轮防死循环
            self.click_box(claim[0], down_time=0.15, after_sleep=1.5)
            self.confirm_dialog()
            claimed += 1
            self.park_cursor()
            self.sleep(0.5)
            claim = self.wait_ocr(match=self.CLAIM, time_out=2, log=True)
        self.info_set(self.tr('Calendar'), f'{self.tr("Claimed")} x{claimed}')
        self.log_info(f'CalendarTask: claimed {claimed} rewards.')
        if claimed == 0:
            self.debug_screenshot('calendar_no_claim')

    def open_zhaoxi(self):
        """从日历页点开朝夕心愿(每日任务列表), 领取可领奖励后返回"""
        row = next((b for b in self.ocr(log=False) if self.ZHAOXI.search(b.name)), None)
        if not row:
            self.log_info('CalendarTask: Zhaoxi entry not found on calendar page.')
            return
        self.click_box(row, down_time=0.15, after_sleep=2.5)
        if not self.wait_page('zhaoxi', 5):
            self.debug_screenshot('zhaoxi_not_open')
            return
        self.park_cursor()
        claimed = 0
        claim = self.wait_ocr(match=self.CLAIM, time_out=3, log=True)
        while claim and claimed < 5:
            self.click_box(claim[0], down_time=0.15, after_sleep=1.5)
            self.confirm_dialog()
            claimed += 1
            self.park_cursor()
            claim = self.wait_ocr(match=self.CLAIM, time_out=2, log=True)
        # 读取今日任务进度(如「一起拍0/1张照片」); 任务本身需大世界玩法, 不自动执行
        tasks = [b.name for b in self.ocr(log=False) if re.search(r'\d+/\d+', b.name)]
        if claimed > 0:
            self.info_set(self.tr('Zhaoxi Quests'), f'{self.tr("Claimed")} x{claimed}')
        elif tasks:
            self.info_set(self.tr('Zhaoxi Quests'), tasks[0][:40])
        self.log_info(f'CalendarTask: zhaoxi claimed {claimed}, tasks: {tasks[:3]}.')
        self.debug_screenshot('zhaoxi_page') # 校准用: 记录每日任务列表内容
        self.send_key('esc', after_sleep=2) # 回日历页
