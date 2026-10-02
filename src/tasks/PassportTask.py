import re

from qfluentwidgets import FluentIcon

from src.tasks.MyBaseTask import MyBaseTask


class PassportTask(MyBaseTask):
    """奇迹之旅(通行证): J 键打开, 领取免费轨道可领的奖励。
    页面特征「悠远颂歌」为大世界顶栏所无, 判定安全"""

    CLAIM = re.compile('一键领取|全部领取|领取|收下')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = "Passport"
        self.description = "Open the Whim Journey (battle pass) and claim free rewards."
        self.icon = FluentIcon.GLOBE
        self.default_config.update({
            'Claim Passport Rewards': True,
        })
        self.config_description.update({
            'Claim Passport Rewards': 'Claim free-track rewards in the Whim Journey.',
        })

    def run(self, **kwargs):
        self.info_clear()
        if not self.ensure_in_game():
            self.log_error('PassportTask: not in game.', notify=True)
            return
        if not self.open_passport():
            self.log_error('PassportTask: cannot open the Whim Journey.', notify=True)
            self.debug_screenshot('passport_not_open')
            self.back_to_world()
            return
        claimed = 0
        if self.config.get('Claim Passport Rewards'):
            claimed = self.claim_rewards()
        self.info_set(self.tr('Passport'), f'{self.tr("Claimed")} x{claimed}')
        self.back_to_world()
        self.log_info(f'PassportTask finished, claimed {claimed}.', notify=True)

    def open_passport(self, attempts=3):
        """J 键打开奇迹之旅(后台实测可用)"""
        if self.page_sig() == 'passport':
            return True
        for _ in range(attempts):
            self.send_key('j', after_sleep=3)
            if self.page_sig() == 'passport':
                return True
            self.close_pause_menu()
        return False

    def claim_rewards(self):
        self.park_cursor()
        claimed = 0
        claim = self.wait_ocr(match=self.CLAIM, time_out=4, log=True)
        while claim and claimed < 20: # 通行证可领层级多, 上限放宽
            self.click_box(claim[0], down_time=0.15, after_sleep=1.5)
            self.confirm_dialog()
            claimed += 1
            self.park_cursor()
            self.sleep(0.5)
            claim = self.wait_ocr(match=self.CLAIM, time_out=2, log=True)
        self.debug_screenshot('passport_after_claim')
        return claimed
