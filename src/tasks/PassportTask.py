import re

from qfluentwidgets import FluentIcon

from src.tasks.MyBaseTask import MyBaseTask


class PassportTask(MyBaseTask):
    """奇迹之旅(通行证): J 键打开, 先在「旅行任务」页领取已完成任务的奖励(通行证经验),
    再回「旅行秘宝」页领免费轨道奖励。
    页面特征「悠远颂歌」为大世界顶栏所无, 判定安全;
    旅行任务页任务文本含幻境名, MyBaseTask.PAGE_SIGS 已把 passport 判定放在 realm 之前"""

    CLAIM = re.compile('一键领取|全部领取|领取|收下')
    TASK_CLAIM = re.compile('领取|收下')
    TASK_TAB = re.compile('旅行任务')
    TREASURE_TAB = re.compile('旅行秘宝')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = "Passport"
        self.description = "Open the Whim Journey (battle pass), claim finished travel tasks and free-track rewards."
        self.icon = FluentIcon.GLOBE
        self.default_config.update({
            'Claim Passport Rewards': True,
            'Claim Passport Tasks': True,
        })
        self.config_description.update({
            'Claim Passport Rewards': 'Claim free-track rewards in the Whim Journey.',
            'Claim Passport Tasks': 'Claim rewards of finished tasks on the Travel Tasks tab.',
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
        claimed_tasks = 0
        if self.config.get('Claim Passport Tasks'):
            claimed_tasks = self.claim_travel_tasks()
        claimed = 0
        if self.config.get('Claim Passport Rewards'):
            self.back_to_treasure_tab()
            claimed = self.claim_rewards()
        self.info_set(self.tr('Passport'),
                      f'{self.tr("Claimed")} x{claimed + claimed_tasks}')
        self.back_to_world()
        self.log_info(f'PassportTask finished, tasks {claimed_tasks}, track {claimed}.', notify=True)

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

    def claim_travel_tasks(self, rounds=2):
        """切到旅行任务页, 领取已完成任务的奖励(每轮领完可见项后向下滚一屏再领)"""
        tab = next((b for b in self.ocr(log=False)
                    if self.TASK_TAB.search(b.name) and b.y < 120), None)
        if not tab:
            self.log_info('PassportTask: travel tasks tab not found.')
            self.debug_screenshot('passport_no_task_tab')
            return 0
        self.click_box(tab, down_time=0.15, after_sleep=2.5)
        self.park_cursor()
        claimed = 0
        for rnd in range(rounds):
            while claimed < 30:
                claim = next((b for b in self.ocr(log=False)
                              if self.TASK_CLAIM.fullmatch(b.name.strip())), None)
                if not claim:
                    break
                self.click_box(claim, down_time=0.15, after_sleep=1.5)
                self.confirm_dialog()
                claimed += 1
                self.park_cursor()
                self.sleep(0.5)
            self.debug_screenshot(f'passport_tasks_r{rnd}')
            if rnd + 1 < rounds:
                self.scroll_relative(0.5, 0.5, 1) # 向下滚一屏, 任务列表较长
                self.sleep(1)
        self.log_info(f'PassportTask: claimed {claimed} travel task rewards.')
        if claimed == 0:
            self.debug_screenshot('passport_tasks_no_claim')
        return claimed

    def back_to_treasure_tab(self):
        """从旅行任务页切回旅行秘宝(奖励轨道)页"""
        tab = next((b for b in self.ocr(log=False)
                    if self.TREASURE_TAB.search(b.name) and b.y < 120), None)
        if tab:
            self.click_box(tab, down_time=0.15, after_sleep=2)
        return self.wait_page('passport', 4)

    def claim_rewards(self):
        self.park_cursor()
        claimed = 0
        claim = self.wait_ocr(match=self.CLAIM, time_out=4, log=True)
        while claim and claimed < 20: # 通行证可领层级多, 上限放宽
            self.click_box(claim[0], down_time=0.15, after_sleep=1.5)
            self.confirm_dialog()
            self.close_reward_page() # 一键领取后弹恭喜获得页, 按 F 关闭
            claimed += 1
            self.park_cursor()
            self.sleep(0.5)
            claim = self.wait_ocr(match=self.CLAIM, time_out=2, log=True)
        self.debug_screenshot('passport_after_claim')
        return claimed
