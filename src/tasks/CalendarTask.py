import re

from qfluentwidgets import FluentIcon

from src.tasks.MyBaseTask import MyBaseTask


class CalendarTask(MyBaseTask):
    """奇想日历(每日任务): 打开日历面板, 领取已达成的每日任务奖励"""

    # 页面特征与按钮(文案未全部实机校准, 失败自动截图到 screenshots/)
    PAGE_TITLE = re.compile('奇想日历|每日任务|Daily')
    CLAIM = re.compile('一键领取|全部领取|领取全部|领取|收下|Claim')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = "Calendar Reward"
        self.description = "Open the Whim Calendar and claim daily quest rewards."
        self.icon = FluentIcon.CALENDAR
        self.default_config.update({
            'Claim Daily Rewards': True,
        })
        self.config_description.update({
            'Claim Daily Rewards': 'Claim all available daily quest rewards in the calendar.',
        })

    def run(self):
        self.info_clear()
        if not self.ensure_foreground():
            return
        if not self.ensure_in_game():
            return
        if not self.open_calendar():
            self.log_error('CalendarTask: cannot open the Whim Calendar.', notify=True)
            self.debug_screenshot('calendar_not_open')
            return
        self.claim_rewards()
        self.send_key('esc', after_sleep=1.5)
        self.log_info('CalendarTask finished.', notify=True)

    def open_calendar(self, attempts=2):
        """打开奇想日历: 优先 OCR 右上角入口(带文字), 失败用 L 键(默认快捷键)"""
        for _ in range(attempts):
            entry = self.wait_ocr(match=self.PAGE_TITLE, time_out=3, log=True)
            if entry:
                self.click_box(entry[0], down_time=0.15, after_sleep=3)
            else:
                self.send_key('l', after_sleep=3) # 游戏默认奇想日历快捷键
            if self.ocr(match=self.PAGE_TITLE, log=True):
                return True
            # 可能已在页面里(入口文字即标题)
            if self.wait_ocr(match=re.compile('朝夕心愿|星海拾光|心愿|活跃'), time_out=2, log=True):
                return True
        return False

    def claim_rewards(self):
        self.move_relative(*self.SAFE_POS) # 防悬停 tooltip
        self.sleep(0.5)
        claim = self.wait_ocr(match=self.CLAIM, time_out=4, log=True)
        claimed = 0
        while claim and claimed < 5: # 逐个领, 最多 5 轮防死循环
            self.click_box(claim[0], down_time=0.15, after_sleep=1.5)
            self.confirm_dialog()
            claimed += 1
            self.move_relative(*self.SAFE_POS)
            self.sleep(0.5)
            claim = self.wait_ocr(match=self.CLAIM, time_out=3, log=True)
        self.info_set(self.tr('Calendar'), f'{self.tr("Claimed")} x{claimed}')
        self.log_info(f'CalendarTask: claimed {claimed} rewards.', notify=True)
        if claimed == 0:
            self.debug_screenshot('calendar_no_claim')
