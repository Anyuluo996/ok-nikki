import re
import time

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

    def run(self, **kwargs):
        self.info_clear()
        if not self.ensure_in_game():
            self.log_error('CalendarTask: not in game.', notify=True)
            return
        if not self.calendar_flow():
            self.back_to_world()
            return
        self.back_to_world()
        self.log_info('CalendarTask finished.', notify=True)

    def calendar_flow(self):
        """日历接力: 开日历→领取→朝夕心愿确认, 结束后停在日历页
        (幻境挑战入口同在日历页, 供 RealmTask 接力, 不用回大世界再按 L)"""
        # 先作废旧任务文本: 探测失败或配置关闭时, RealmTask 不会用昨日任务路由
        MyBaseTask.zhaoxi_task_texts = []
        MyBaseTask.zhaoxi_task_date = None
        if not self.open_whim_calendar():
            self.log_error('CalendarTask: cannot open the Whim Calendar.', notify=True)
            self.debug_screenshot('calendar_not_open')
            self.back_to_world()
            return False
        if self.config.get('Claim Calendar Rewards'):
            self.claim_rewards()
        if self.config.get('Open Zhaoxi Quests'):
            self.open_zhaoxi()
        return self.page_sig() == 'calendar'

    def claim_rewards(self):
        self.park_cursor()
        self.sleep(0.5)
        claimed = 0
        claim = self.wait_ocr(match=self.CLAIM, time_out=3, log=True)
        while claim and claimed < 5: # 逐个领, 最多 5 轮防死循环
            self.click_box(claim[0], down_time=0.15, after_sleep=1.5)
            self.confirm_dialog()
            self.close_reward_page() # 领取可能弹恭喜获得页, 按 F 关闭
            claimed += 1
            self.park_cursor()
            self.sleep(0.5)
            claim = self.wait_ocr(match=self.CLAIM, time_out=2, log=True)
        self.info_set(self.tr('Calendar'), f'{self.tr("Claimed")} x{claimed}')
        self.log_info(f'CalendarTask: claimed {claimed} rewards.')
        if claimed == 0:
            self.debug_screenshot('calendar_no_claim')

    def open_zhaoxi(self):
        """从日历页点开朝夕心愿: 先领里程碑礼物和任务奖励(领完即快速跳过),
        最后确认任务卡文本(供 RealmTask 路由)"""
        row = next((b for b in self.ocr(log=False) if self.ZHAOXI.search(b.name)), None)
        if not row:
            self.log_info('CalendarTask: Zhaoxi entry not found on calendar page.')
            return
        self.click_box(row, down_time=0.15, after_sleep=2.5)
        if not self.wait_page('zhaoxi', 5):
            self.debug_screenshot('zhaoxi_not_open')
            return
        self.claim_zhaoxi_gifts()
        self.park_cursor()
        claimed = 0
        claim = self.wait_ocr(match=self.CLAIM, time_out=2, log=True)
        while claim and claimed < 5:
            self.click_box(claim[0], down_time=0.15, after_sleep=1.5)
            self.confirm_dialog()
            self.close_reward_page()
            claimed += 1
            self.park_cursor()
            claim = self.wait_ocr(match=self.CLAIM, time_out=2, log=True)
        # 确认任务卡文本(RealmTask 路由依赖), 读完读今日任务进度(如「一起拍0/1张照片」)
        self.confirm_zhaoxi_tasks()
        tasks = [b.name for b in self.ocr(log=False) if re.search(r'\d+/\d+', b.name)]
        if claimed > 0:
            self.info_set(self.tr('Zhaoxi Quests'), f'{self.tr("Claimed")} x{claimed}')
        elif tasks:
            self.info_set(self.tr('Zhaoxi Quests'), tasks[0][:40])
        self.log_info(f'CalendarTask: zhaoxi claimed {claimed}, tasks: {tasks[:3]}.')
        self.debug_screenshot('zhaoxi_page') # 校准用: 记录每日任务列表内容
        self.send_key('esc', after_sleep=2) # 回日历页

    # 朝夕心愿任务卡中心(相对比例, 1080p 标定 (549,595)... 参考 Whimbox DAILY_TASK_CENTERS)
    ZHAOXI_CARD_CENTERS = [(0.286, 0.551), (0.411, 0.312), (0.579, 0.350),
                           (0.685, 0.562), (0.798, 0.347)]
    # 页面右侧里程碑礼盒竖排(100..500 活跃度档位); 只点最上面一档即可领取全部已达标档位
    ZHAOXI_GIFT_CENTERS = [(0.943, 0.247), (0.943, 0.344), (0.943, 0.441),
                           (0.943, 0.538), (0.943, 0.635)]

    def claim_zhaoxi_gifts(self):
        """领取朝夕心愿里程碑礼盒: 只点最上面一档即可领走全部已达标的;
        随后读右侧轨道底部星星数字判断活跃度(满 500 结束)"""
        self.click(*self.ZHAOXI_GIFT_CENTERS[0], down_time=0.15, after_sleep=1.2)
        if self.confirm_dialog(time_out=2) or self.close_reward_page(2):
            self.log_info('CalendarTask: zhaoxi milestone gifts claimed.', notify=True)
        else:
            self.log_info('CalendarTask: no zhaoxi milestone gift to claim.')
        self.park_cursor()
        activity = self.read_zhaoxi_activity()
        if activity is None:
            return
        if activity >= 500:
            self.info_set(self.tr('Zhaoxi Quests'), f'{activity}/500')
            self.log_info(f'CalendarTask: zhaoxi activity {activity}/500, milestone complete.', notify=True)
        else:
            self.info_set(self.tr('Zhaoxi Quests'), f'{activity}/500')
            self.log_info(f'CalendarTask: zhaoxi activity {activity}/500.', notify=True)

    def read_zhaoxi_activity(self):
        """右侧里程碑轨道底部的星星数字 = 当前活跃度(如 300); 读不到返回 None"""
        for b in self.ocr(log=False):
            if (b.x > self.width * 0.88 and self.height * 0.70 < b.y < self.height * 0.85
                    and re.fullmatch(r'\d{2,4}', b.name.strip())):
                return int(b.name)
        return None

    def confirm_zhaoxi_tasks(self):
        """确认任务: 逐个点任务卡, 从底部详情条读任务文本与进度
        (完成的卡带勾选图标, 未完成的文本里有 N/M 进度)。
        文本存到 MyBaseTask.zhaoxi_task_texts, 供 RealmTask 决定打哪个幻境 boss"""
        self.park_cursor()
        found = []
        for cx, cy in self.ZHAOXI_CARD_CENTERS:
            self.click(cx, cy, down_time=0.15, after_sleep=1.2)
            detail = ' '.join(b.name for b in self.ocr(log=False)
                              if b.y > self.height * 0.8)
            if detail:
                found.append(detail[:80])
        MyBaseTask.zhaoxi_task_texts = found
        MyBaseTask.zhaoxi_task_date = time.strftime('%Y-%m-%d')
        self.info_set(self.tr('Zhaoxi Quests'), f'{len(found)} {self.tr("Confirmed")}')
        self.log_info(f'CalendarTask: zhaoxi card details: {found}', notify=True)
        self.debug_screenshot('zhaoxi_cards')
