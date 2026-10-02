import re

from qfluentwidgets import FluentIcon

from src.tasks.MyBaseTask import MyBaseTask


class RealmTask(MyBaseTask):
    """幻境挑战: 从奇想日历进入, 快速挑战消耗活跃能量(体力), 完成朝夕心愿的耗能任务。
    流程参考 Whimbox weekly_realm_task: 幻境挑战 hub → 心之突破幻境 → 选关 → 快速挑战
    → 确认注入能量 → 跳过战斗领奖励"""

    WEEKLY_ENTRY = re.compile('心之突破幻境')
    LEVEL = re.compile('奇格格达|卷卷')
    QUICK_PLAY = re.compile('快速挑战')
    WEEKLY_COUNT = re.compile(r'每周幻境')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = "Realm Challenge"
        self.description = "Spend energy via quick challenge in the realm (weekly boss)."
        self.icon = FluentIcon.FLAG
        self.default_config.update({
            'Challenge Count': 1,
            'Realm Level': '奇格格达',
        })
        self.config_description.update({
            'Challenge Count': 'Quick challenges to run (weekly reward is once per week, 1 is enough).',
            'Realm Level': 'Fallback weekly boss level when the zhaoxi tasks do not name one.',
        })

    def run(self):
        self.info_clear()
        if not self.ensure_in_game():
            self.log_error('RealmTask: not in game.', notify=True)
            return
        if not self.open_whim_calendar():
            self.log_error('RealmTask: cannot open the Whim Calendar.', notify=True)
            self.debug_screenshot('realm_no_calendar')
            return
        if not self.open_realm_hub():
            self.log_error('RealmTask: cannot open the realm hub.', notify=True)
            self.debug_screenshot('realm_hub_not_open')
            self.back_to_world()
            return
        self.quick_challenge()
        self.report_weekly_count()
        self.back_to_world()
        self.log_info('RealmTask finished.', notify=True)

    def open_realm_hub(self, attempts=2):
        """日历页右上的幻境挑战卡(每周幻境 1/2 文字所在卡)→ 幻境挑战 hub"""
        if self.page_sig() == 'realm':
            return True
        for _ in range(attempts):
            weekly = next((b for b in self.ocr(log=False) if self.WEEKLY_COUNT.search(b.name)), None)
            if weekly:
                # 卡片中心在「每周幻境」文字左侧
                self.click(1320, max(80, weekly.y - 35), down_time=0.15, after_sleep=3)
            else:
                self.click(0.687, 0.228, down_time=0.15, after_sleep=3)
            if self.page_sig() == 'realm':
                return True
            self.debug_screenshot('realm_hub_miss')
            self.close_pause_menu()
            if not self.open_whim_calendar():
                return False
        return self.page_sig() == 'realm'

    def quick_challenge(self):
        """打哪个 boss 按朝夕心愿任务文本决定(愿望大师=奇格格达/守护兽=卷卷),
        任务没提就打配置的默认关卡"""
        count = int(self.config.get('Challenge Count') or 1)
        texts = ' '.join(getattr(MyBaseTask, 'zhaoxi_task_texts', []))
        if '卷卷' in texts or '守护兽' in texts:
            level_name = '卷卷'
        elif '愿望大师' in texts or '奇格格达' in texts:
            level_name = '奇格格达'
        else:
            level_name = self.config.get('Realm Level') or '奇格格达'
        self.log_info(f'RealmTask: zhaoxi texts decide level = {level_name}')
        for i in range(count):
            self.log_info(f'RealmTask: quick challenge #{i + 1}/{count}')
            if not self.enter_weekly_and_run(level_name):
                self.log_info(f'RealmTask: challenge #{i + 1} did not complete.')
                break
            self.info_set(self.tr('Realm'), f'{level_name} {self.tr("Challenged")} {i + 1}/{count}')
        # 退出由 run() 的 back_to_world 处理(可关弹窗)

    def enter_weekly_and_run(self, level_name):
        boxes = self.ocr(log=False)
        if self.page_sig(boxes) != 'realm' or not any('心之突破幻境' in b.name for b in boxes):
            # 不在幻境相关页: 从日历重来
            if not self.open_whim_calendar() or not self.open_realm_hub():
                return False
            boxes = self.ocr(log=False)
        entry = next((b for b in boxes if self.WEEKLY_ENTRY.search(b.name)), None)
        if not entry:
            self.debug_screenshot('realm_no_weekly_entry')
            return False
        # 心之突破幻境可能在日历挑战列表内联, 也可能在幻境 hub 页, 都可直接点
        self.click_box(entry, down_time=0.15, after_sleep=3)
        # 关卡列表: 点配置的关卡名(奇格格达/卷卷)
        level = self.wait_ocr(match=re.compile(level_name), time_out=6, log=True)
        if not level:
            self.debug_screenshot('realm_no_level')
            return False
        self.click_box(level[0], down_time=0.15, after_sleep=1.5)
        quick = self.wait_ocr(match=self.QUICK_PLAY, time_out=5, log=True)
        if not quick:
            self.debug_screenshot('realm_no_quick')
            return False
        self.click_box(quick[0], down_time=0.15, after_sleep=2)
        # 试炼奖励弹窗: 确认按钮是「注入活跃能量」(弹窗标题含同文字, 取 y 最大的=按钮)
        cands = [b for b in self.ocr(log=False) if '注入活跃能量' in b.name]
        if not cands:
            self.debug_screenshot('realm_no_inject')
            return False
        # 本周奖励一周只领一次: 剩余 0/1 就取消跳过, 不浪费体力
        joined = ' '.join(b.name for b in self.ocr(log=False))
        if re.search(r'剩余奖励次数[^0-9]*0\s*/\s*1', joined):
            self.info_set(self.tr('Weekly Realm'), self.tr('Weekly Done'))
            self.log_info('RealmTask: weekly reward already claimed this week, skip.')
            cancel = next((b for b in self.ocr(log=False) if b.name.strip() == '取消'), None)
            if cancel:
                self.click_box(cancel, down_time=0.15, after_sleep=1.5)
            return True
        inject = max(cands, key=lambda b: b.y)
        self.click_box(inject, down_time=0.15, after_sleep=3)
        self.park_cursor()
        self.debug_screenshot('realm_after_inject')
        # 奖励页按 F(交互键)关闭
        self.sleep(2)
        self.send_key('f', after_sleep=1.5)
        self.send_key('f', after_sleep=1.5)
        self.debug_screenshot('realm_after_award')
        return True

    def report_weekly_count(self):
        """回到日历读每周幻境 N/M 与剩余体力"""
        if not self.open_whim_calendar():
            return
        boxes = self.ocr(log=False)
        joined = ' '.join(b.name for b in boxes)
        m = re.search(r'(\d+)\s*/\s*(\d+)', joined)
        energy = next((b.name for b in boxes if re.search(r'\d+\s*/\s*350', b.name)), '')
        if m:
            self.info_set(self.tr('Weekly Realm'), f'{m.group(1)}/{m.group(2)} {energy}')
            self.log_info(f'RealmTask: weekly count {m.group(0)}, energy {energy}.', notify=True)
