import re

from qfluentwidgets import FluentIcon

from src.tasks.MyBaseTask import MyBaseTask


class RealmTask(MyBaseTask):
    """幻境挑战: 按朝夕心愿任务决定打哪个幻境, 快速挑战消耗活跃能量(体力)。
    周本(心之突破)奖励一周只领一次, 必须在「Weekly Boss」配置里选了奇格格达/卷卷才打;
    奖励次数剩 0/1 时零点击跳过"""

    QUICK_PLAY = re.compile('快速挑战')
    WEEKLY_REALM = '心之突破幻境'
    WEEKLY_COUNT = re.compile(r'每周幻境')
    # 朝夕心愿任务关键词 → 对应幻境(同 Whimbox zxxy_task_info_list 的挑战类映射)
    TASK_REALM_MAP = [
        (re.compile('魔物试炼'), '魔物试炼幻境'),
        (re.compile('祝福闪光'), '祝福闪光幻境'),
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = "Realm Challenge"
        self.description = "Spend energy via quick challenge in the realm chosen by zhaoxi tasks."
        self.icon = FluentIcon.FLAG
        self.default_config.update({
            'Challenge Count': 1,
            'Weekly Boss': '',  # 空=不打周本; 奇格格达 / 卷卷
        })
        self.config_description.update({
            'Challenge Count': 'Quick challenges to run (weekly reward is once per week).',
            'Weekly Boss': 'Weekly boss to challenge: 奇格格达 or 卷卷. Empty = skip weekly.',
        })

    def run(self, **kwargs):
        self.info_clear()
        if not self.ensure_in_game():
            self.log_error('RealmTask: not in game.', notify=True)
            return
        if not self.open_whim_calendar():
            self.log_error('RealmTask: cannot open the Whim Calendar.', notify=True)
            self.debug_screenshot('realm_no_calendar')
            return
        self.quick_challenge()
        self.report_weekly_count()
        self.back_to_world()
        self.log_info('RealmTask finished.', notify=True)

    def realm_flow(self):
        """日历接力: 假定已停在奇想日历页(入口同页), 完成后停在原处由调用方退出"""
        return self.quick_challenge()

    def pick_realm(self):
        """按朝夕心愿任务文本决定打哪个幻境; 任务进度 N>=M 视为已完成跳过"""
        texts = getattr(MyBaseTask, 'zhaoxi_task_texts', [])
        for pat, realm in self.TASK_REALM_MAP:
            for detail in texts:
                if not pat.search(detail):
                    continue
                if self._progress_done(detail):
                    continue
                return realm
        return None

    @staticmethod
    def _progress_done(detail):
        m = re.search(r'(\d+)\s*/\s*(\d+)', detail)
        return bool(m and int(m.group(1)) >= int(m.group(2)))

    def quick_challenge(self):
        count = int(self.config.get('Challenge Count') or 1)
        texts = getattr(MyBaseTask, 'zhaoxi_task_texts', [])
        realm = self.pick_realm()
        level_name = None
        if realm is None:
            # 无专属幻境任务: 体力任务走周本, 但必须显式选了 boss(没选择就不打)
            weekly_boss = (self.config.get('Weekly Boss') or '').strip()
            energy = next((d for d in texts if '活跃能量' in d), None)
            if energy and not self._progress_done(energy):
                if not weekly_boss:
                    self.log_info('RealmTask: energy task unfinished but Weekly Boss not '
                                  'configured, skip (no energy spent).', notify=True)
                    self.info_set(self.tr('Realm'), self.tr('Need Manual Setup'))
                    return
                realm = self.WEEKLY_REALM
                level_name = weekly_boss
            else:
                self.log_info('RealmTask: no unfinished realm-related tasks, skip.')
                return
        for i in range(count):
            self.log_info(f'RealmTask: quick challenge #{i + 1}/{count} @ {realm}')
            if not self.enter_realm_and_run(realm, level_name):
                self.log_info(f'RealmTask: challenge #{i + 1} did not complete.')
                break
            self.info_set(self.tr('Realm'), f'{realm} {self.tr("Challenged")} {i + 1}/{count}')

    def open_realm_hub(self, attempts=2):
        """日历页右上的幻境挑战卡(每周幻境 1/2 文字所在卡)→ 幻境挑战 hub"""
        if self.page_sig() == 'realm':
            return True
        crystal = self.find_template('CalendarRealmCrystal', time_out=2)
        for _ in range(attempts):
            if crystal:
                self.click_box(crystal, down_time=0.15, after_sleep=3)
            else:
                weekly = next((b for b in self.ocr(log=False) if self.WEEKLY_COUNT.search(b.name)), None)
                if weekly:
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

    def enter_realm_and_run(self, realm_name, level_name=None):
        """进入指定幻境(日历挑战列表内联或幻境 hub 页都可点), 选关并快速挑战"""
        boxes = self.ocr(log=False)
        if self.page_sig(boxes) != 'realm' or not any(realm_name in b.name for b in boxes):
            if not self.open_whim_calendar() or not self.open_realm_hub():
                return False
            boxes = self.ocr(log=False)
        entry = next((b for b in boxes if realm_name in b.name), None)
        if not entry:
            self.debug_screenshot('realm_no_entry')
            return False
        self.click_box(entry, down_time=0.15, after_sleep=3)
        if realm_name == self.WEEKLY_REALM:
            # 零点击预检: 周页右下就有「本周剩余奖励次数 0/1」, 没次数不开任何弹窗
            if self.weekly_remain_zero():
                self.info_set(self.tr('Weekly Realm'), self.tr('Weekly Done'))
                self.log_info('RealmTask: weekly reward already claimed this week, '
                              'skip without clicking.', notify=True)
                return True
        if level_name:
            # 心之突破有关卡列表(奇格格达/卷卷); 其他幻境默认选中, 直接找快速挑战
            level = self.wait_ocr(match=re.compile(level_name), time_out=6, log=True)
            if not level:
                self.debug_screenshot('realm_no_level')
                return False
            self.click_box(level[0], down_time=0.15, after_sleep=1.5)
        # 快速挑战: 图像识别优先, OCR 兜底
        quick = self.find_template('QuickChallengeButton', time_out=3)
        if not quick:
            quick = self.wait_ocr(match=self.QUICK_PLAY, time_out=5, log=True)
        if not quick:
            self.debug_screenshot('realm_no_quick')
            return False
        self.click_box(quick, down_time=0.15, after_sleep=2)
        # 试炼奖励弹窗: 金色「注入活跃能量」按钮(图像识别优先, 弹窗标题含同文字取 y 最大)
        inject = self.find_template('InjectEnergyButton', time_out=3)
        if inject:
            # 周本次数再确认(弹窗里一定有这行)
            if realm_name == self.WEEKLY_REALM and self.weekly_remain_zero():
                self.info_set(self.tr('Weekly Realm'), self.tr('Weekly Done'))
                self.log_info('RealmTask: weekly 0/1 in dialog, cancel.')
                self.cancel_dialog()
                return True
        else:
            cands = [b for b in self.ocr(log=False) if '注入活跃能量' in b.name]
            inject = max(cands, key=lambda b: b.y) if cands else None
        if not inject:
            self.debug_screenshot('realm_no_inject')
            return False
        if self.config.get('Dry Run'):
            self.log_info('RealmTask: DRY RUN - would inject energy here, no energy spent.')
            self.debug_screenshot('realm_dry_inject')
            self.cancel_dialog()
            return True
        self.click_box(inject, down_time=0.15, after_sleep=3)
        self.park_cursor()
        self.debug_screenshot('realm_after_inject')
        # 奖励页按 F(交互键)关闭
        self.sleep(2)
        self.send_key('f', after_sleep=1.5)
        self.send_key('f', after_sleep=1.5)
        self.debug_screenshot('realm_after_award')
        return True

    def weekly_remain_zero(self):
        """周本剩余奖励次数是否 0/1(周页右下/弹窗内)"""
        joined = ' '.join(b.name for b in self.ocr(log=False))
        return bool(re.search(r'剩余奖励次数[^0-9]*0\s*/\s*1', joined))

    def cancel_dialog(self):
        """点弹窗「取消」(图像识别优先)"""
        cancel = self.find_template('CancelButton', time_out=2)
        if not cancel:
            cancel = next((b for b in self.ocr(log=False) if b.name.strip() == '取消'), None)
        if cancel:
            self.click_box(cancel, down_time=0.15, after_sleep=1.5)
            return True
        return False

    def report_weekly_count(self):
        """回到日历读每周幻境 N/M 与剩余体力"""
        if not self.open_whim_calendar():
            return
        boxes = self.ocr(log=False)
        joined = ' '.join(b.name for b in boxes)
        m = re.search(r'每周幻境\D*(\d+)\s*/\s*(\d+)', joined)
        energy = next((b.name for b in boxes if re.search(r'\d+\s*/\s*350', b.name)), '')
        if m:
            self.info_set(self.tr('Weekly Realm'), f'{m.group(1)}/{m.group(2)} {energy}')
            self.log_info(f'RealmTask: weekly count {m.group(1)}/{m.group(2)}, energy {energy}.', notify=True)