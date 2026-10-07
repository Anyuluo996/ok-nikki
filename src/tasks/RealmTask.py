import re

from qfluentwidgets import FluentIcon

from src.tasks.MyBaseTask import MyBaseTask


class RealmTask(MyBaseTask):
    """幻境挑战: 按固定优先级消耗活跃能量(体力), Drain Energy 时一键最大次数耗光。
    优先级: 周本(心之突破, 按「Weekly Boss」配置, 本周奖励次数已用完则跳过)
    → 素材兑换(按「Material Exchange Count」配置, 进副本激化台兑换)
    → 魔物试炼幻境 → 祝福闪光幻境(快速挑战 40 体力/次)。
    心之突破有关卡列表(奇格格达/卷卷); 素材激化没有快速挑战, 需进副本走到激化台"""

    QUICK_PLAY = re.compile('快速挑战')
    WEEKLY_REALM = '心之突破幻境'
    MATERIAL_REALM = '素材激化幻境'
    WEEKLY_COUNT = re.compile(r'每周幻境')
    # 快速挑战类幻境的消耗优先级(周本/素材兑换在 quick_challenge 里按配置先行)
    DRAIN_REALMS = ('魔物试炼幻境', '祝福闪光幻境')
    # 朝夕心愿任务关键词 → 对应幻境: 优先按任务文本补齐 500 活跃度所需
    TASK_REALM_MAP = [
        (re.compile('魔物试炼'), '魔物试炼幻境'),
        (re.compile('祝福闪光'), '祝福闪光幻境'),
        (re.compile('素材激化'), '素材激化幻境'),
    ]
    CLAIM_COST = 40  # 快速挑战单次消耗(注入弹窗「消耗40活跃能量」)
    # 副本激化台交互提示与产物/材料格特征
    ESCALATE_PROMPT = re.compile('打开素材激化台|激化台')
    ESCALATE_BUTTON = re.compile('激化材料')
    PRODUCTS = ('噗灵', '丝线', '闪亮泡泡')
    NUM_TILE = re.compile(r'\d+(\.\d+)?(kg|万)?')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = "Realm Challenge"
        self.description = "Spend all active energy by priority: weekly boss (per config) -> material exchange (per config) -> monster trial -> blessing flash."
        self.icon = FluentIcon.FLAG
        self.default_config.update({
            'Challenge Count': 1,
            'Drain Energy': False,  # 注入弹窗一键最大次数, 耗光活跃能量
            'Weekly Boss': '',  # 空=不打周本; 奇格格达 / 卷卷
            'Material Exchange Count': 0,  # >0 时优先做素材激化兑换
            'Escalate Product': '噗灵',  # 噗灵 / 丝线 / 闪亮泡泡
            'Escalate Max': True,  # 选择材料弹窗按箭头一键最大数量
        })
        self.config_description.update({
            'Challenge Count': 'Quick challenges per realm when Drain Energy is off.',
            'Drain Energy': 'Use the max-count arrow in the inject dialog to deplete all active energy (40 per claim).',
            'Weekly Boss': 'Weekly boss to challenge: 奇格格达 or 卷卷. Empty = skip weekly.',
            'Material Exchange Count': 'Material realm exchanges before quick challenges (0 = off).',
            'Escalate Product': 'Product to escalate into: 噗灵 / 丝线 / 闪亮泡泡.',
            'Escalate Max': 'Pick the most stocked material and max its quantity via the arrow.',
        })

    def run(self, **kwargs):
        self.info_clear()
        if not self.ensure_in_game():
            self.log_error('RealmTask: not in game.', notify=True)
            return
        if not self.open_whim_calendar():
            self.log_error('RealmTask: cannot open the Whim Calendar.', notify=True)
            self.debug_screenshot('realm_no_calendar')
            self.back_to_world()
            return
        self.quick_challenge()
        self.report_weekly_count()
        self.back_to_world()
        self.log_info('RealmTask finished.', notify=True)

    def realm_flow(self):
        """日历接力: 假定已停在奇想日历页(入口同页), 完成后停在原处由调用方退出"""
        return self.quick_challenge()

    def quick_challenge(self):
        """两段式消耗体力:
        1) 优先按朝夕心愿任务文本路由(魔物试炼/祝福闪光/素材激化),
           精确按任务缺口次数打, 补齐 500 活跃度所需;
        2) 剩余体力按固定优先级耗光: 周本(按配置) → 素材兑换(按配置) →
           魔物试炼 → 祝福闪光, Drain Energy 时一键最大次数"""
        count = int(self.config.get('Challenge Count') or 1)
        weekly_boss = (self.config.get('Weekly Boss') or '').strip()
        material_count = int(self.config.get('Material Exchange Count') or 0)
        total = 0

        # —— 1) 朝夕文本路由: 未完成任务按缺口次数精确打 ——
        for pat, realm in self.TASK_REALM_MAP:
            detail = next((d for d in self.zhaoxi_texts_today() if pat.search(d)), None)
            if detail is None:
                continue
            need = self._task_need_claims(detail)
            if need <= 0:
                self.log_info(f'RealmTask: zhaoxi task already done: {detail[:30]}...')
                continue
            self.log_info(f'RealmTask: zhaoxi task needs {need} more claims @ {realm}.')
            if realm == self.MATERIAL_REALM:
                self.material_flow(min(need, count))
                continue
            for i in range(min(need, count)):
                made = self.enter_realm_and_run(realm, drain=False)
                if made <= 0:
                    break
                total += made
                self.info_set(self.tr('Realm'), f'{realm} {self.tr("Challenged")} x{total}')
                if self.config.get('Dry Run'):
                    break

        # —— 2) 剩余体力按固定优先级耗光 ——
        if weekly_boss:
            made = self.enter_realm_and_run(self.WEEKLY_REALM, weekly_boss)
            if made > 0:
                total += made
                self.info_set(self.tr('Weekly Realm'), f'{self.tr("Challenged")} x{made}')
        if material_count > 0:
            self.material_flow(material_count)
        for realm in self.DRAIN_REALMS:
            for i in range(count):
                self.log_info(f'RealmTask: quick challenge #{i + 1} @ {realm} (total {total}).')
                made = self.enter_realm_and_run(realm)
                if made <= 0:
                    self.log_info(f'RealmTask: {realm} made no progress '
                                  '(depleted or entry missing), next.')
                    break
                total += made
                self.info_set(self.tr('Realm'), f'{realm} {self.tr("Challenged")} x{total}')
                if self.config.get('Dry Run'):
                    break
            if self.config.get('Dry Run') and total:
                break
        if total:
            self.log_info(f'RealmTask: claimed {total} realm rewards this run.', notify=True)
        else:
            self.log_info('RealmTask: nothing claimed (energy depleted or nothing configured).')

    @staticmethod
    def _task_need_claims(detail):
        """朝夕任务文本里的进度 N/M → 还需的快速挑战次数(40 体力/次, 向上取整);
        读不到进度视为还需 1 次, N>=M 视为已完成返回 0"""
        pairs = [(int(n), int(m)) for n, m in re.findall(r'(\d+)\s*/\s*(\d+)', detail)]
        prog = next(((n, m) for n, m in pairs if n <= m), None)
        if prog is None:
            return 1
        n, m = prog
        if n >= m:
            return 0
        return -(-(m - n) // RealmTask.CLAIM_COST)

    def open_realm_hub(self, attempts=2):
        """日历页右上的幻境挑战卡 → 幻境挑战 hub。
        卡面水晶是动图, 模板时灵时不灵; 优先点「每日幻境」行文字锚点(行可点),
        兜底「每周幻境」行/旧坐标"""
        if self.page_sig() == 'realm':
            return True
        for _ in range(attempts):
            # 动图模板每轮重找, 避免第二轮点过期 box
            crystal = self.find_template('CalendarRealmCrystal', time_out=2)
            if crystal:
                self.click_box(crystal, down_time=0.15, after_sleep=1)
            else:
                boxes = self.ocr(log=False)
                daily = next((b for b in boxes if '每日幻境' in b.name), None)
                weekly = next((b for b in boxes if self.WEEKLY_COUNT.search(b.name)), None)
                if daily:
                    self.click_box(daily, down_time=0.15, after_sleep=1)
                elif weekly:
                    self.click_box(weekly, down_time=0.15, after_sleep=1)
                else:
                    self.click(0.687, 0.228, down_time=0.15, after_sleep=1)
            if self.wait_page('realm', 6):
                return True
            self.debug_screenshot('realm_hub_miss')
            self.close_pause_menu()
            if not self.open_whim_calendar():
                return False
        return self.page_sig() == 'realm'

    def enter_realm_and_run(self, realm_name, level_name=None, drain=None):
        """进入指定幻境(日历挑战列表内联或幻境 hub 页都可点), 选关并快速挑战。
        drain=None 用 Drain Energy 配置, True/False 强制开/关一键最大次数。
        返回本次领取的奖励次数; 0 = 没打成(体力不足/次数用尽/流程失败), 调用方应停止"""
        boxes = self.ocr(log=False)
        if self.page_sig(boxes) != 'realm' or not any(realm_name in b.name for b in boxes):
            if not self.open_whim_calendar() or not self.open_realm_hub():
                return 0
            boxes = self.ocr(log=False)
        entry = next((b for b in boxes if realm_name in b.name), None)
        if not entry:
            self.debug_screenshot('realm_no_entry')
            return 0
        self.click_box(entry, down_time=0.15, after_sleep=3)
        if realm_name == self.WEEKLY_REALM:
            # 零点击预检: 周页右下就有「本周剩余奖励次数 0/1」, 没次数不开任何弹窗
            if self.weekly_remain_zero():
                self.info_set(self.tr('Weekly Realm'), self.tr('Weekly Done'))
                self.log_info('RealmTask: weekly reward already claimed this week, '
                              'skip without clicking.', notify=True)
                return 0
        if level_name:
            # 心之突破有关卡列表(奇格格达/卷卷); 其他幻境默认选中, 直接找快速挑战
            level = self.wait_ocr(match=re.compile(level_name), time_out=6, log=True)
            if not level:
                self.debug_screenshot('realm_no_level')
                return 0
            self.click_box(level[0], down_time=0.15, after_sleep=1.5)
        # 快速挑战: 图像识别优先, OCR 兜底
        quick = self.find_template('QuickChallengeButton', time_out=3)
        if not quick:
            quick = self.wait_ocr(match=self.QUICK_PLAY, time_out=5, log=True)
        if not quick:
            self.debug_screenshot('realm_no_quick')
            return 0
        self.click_box(quick, down_time=0.15, after_sleep=2)
        # 试炼奖励弹窗: 金色「注入活跃能量」按钮(图像识别优先, 弹窗标题含同文字取 y 最大)
        inject = self.find_template('InjectEnergyButton', time_out=3)
        if inject:
            # 周本次数再确认(弹窗里一定有这行)
            if realm_name == self.WEEKLY_REALM and self.weekly_remain_zero():
                self.info_set(self.tr('Weekly Realm'), self.tr('Weekly Done'))
                self.log_info('RealmTask: weekly 0/1 in dialog, cancel.')
                if not self.cancel_dialog():
                    # 弹窗没有可点的取消时用 Esc 兜底, 不残留弹窗
                    self.send_key('esc', after_sleep=1.5)
                return 0
        else:
            cands = [b for b in self.ocr(log=False) if '注入活跃能量' in b.name]
            inject = max(cands, key=lambda b: b.y) if cands else None
        if not inject:
            self.debug_screenshot('realm_no_inject')
            return 0
        claims = 1
        use_drain = self.config.get('Drain Energy') if drain is None else drain
        if use_drain:
            claims = self._inject_max(inject)
            if claims <= 0:
                return 0
        if self.config.get('Dry Run'):
            self.log_info('RealmTask: DRY RUN - would inject energy here, no energy spent.')
            self.debug_screenshot('realm_dry_inject')
            self.cancel_dialog()
            return 1
        self.click_box(inject, down_time=0.15, after_sleep=3)
        self.park_cursor()
        self.debug_screenshot('realm_after_inject')
        # 奖励页按 F(交互键)关闭
        self.sleep(2)
        self.send_key('f', after_sleep=1.5)
        self.send_key('f', after_sleep=1.5)
        self.debug_screenshot('realm_after_award')
        return claims

    # 注入弹窗「消耗40活跃能量, 领取奖励N次」中的次数
    CLAIM_COUNT = re.compile(r'领取奖励\s*(\d+)\s*次')

    @staticmethod
    def parse_claim_count(texts):
        """从 OCR 文本行解析注入弹窗的最大可领次数, 读不到返回 None"""
        for t in texts:
            m = re.search(r'领取奖励\s*(\d+)\s*次', t)
            if m:
                return int(m.group(1))
        return None

    def _inject_max(self, inject):
        """Drain Energy: 点「换取次数」行的一键最大箭头(→|), 次数拉到体力可负担的最大。
        返回可领次数; 0 次(体力不足单次消耗)或读不到次数时取消弹窗返回 0。
        箭头在「注入活跃能量」按钮正上方 ~178px(1080p 标定 (1117,528) vs (1117,706))"""
        self.click(inject.x + inject.width / 2, inject.y - self.px(178),
                   down_time=0.1, after_sleep=1)
        n = self.parse_claim_count(b.name for b in self.ocr(log=False))
        if n is None:
            self.log_info('RealmTask: claim count not readable after max-click, cancel.')
            self.debug_screenshot('realm_no_claim_count')
            self.cancel_dialog()
            return 0
        if n <= 0:
            self.log_info('RealmTask: active energy below single-claim cost, done.', notify=True)
            self.cancel_dialog()
            return 0
        self.log_info(f'RealmTask: drain mode, injecting max claims = {n}.', notify=True)
        return n

    # ---------- 素材激化幻境: 进副本兑换 ----------

    def material_flow(self, count):
        """素材激化幻境: 进副本在激化台兑换 count 次(无快速挑战), 完成后退出副本"""
        done = 0
        if self.enter_material_realm():
            for i in range(count):
                self.log_info(f'RealmTask: material exchange #{i + 1}/{count}')
                if not self.material_exchange_once(i == 0):
                    self.log_info(f'RealmTask: material exchange #{i + 1} failed.')
                    self.debug_screenshot('material_fail')
                    break
                done += 1
                self.info_set(self.tr('Material Realm'),
                              f'{self.tr("Exchanged")} {done}/{count}')
        else:
            self.log_info('RealmTask: cannot enter the Material Realm.')
            self.debug_screenshot('material_no_enter')
        if not self.leave_material_dungeon():
            # 门点不动(卡副本), 走菜单退出到登录重进
            self.log_info('RealmTask: leave dungeon failed, relogin recovery.', notify=True)
            self.recover_via_relogin()
        return done

    def enter_material_realm(self, attempts=2):
        """日历 → 幻境 hub → 素材激化卡 → 「前往」进副本(与快速挑战不同, 这里只有前往)"""
        for attempt in range(attempts):
            boxes = self.ocr(log=False)
            self.log_info(f'RealmTask: enter material[{attempt}] start sig={self.page_sig(boxes)}.')
            if (self.page_sig(boxes) == 'realm'
                    and self.MATERIAL_REALM in ' '.join(b.name for b in boxes)):
                go = next((b for b in boxes if b.name.strip() == '前往'), None)
                if go:
                    self.log_info('RealmTask: material level page with 前往, clicking.')
                    self.click_box(go, down_time=0.15, after_sleep=8)
                    return True
            if not self.open_whim_calendar():
                self.log_info('RealmTask: enter material calendar open failed.')
                continue
            if not self.open_realm_hub():
                self.log_info('RealmTask: enter material hub open failed.')
                continue
            boxes = self.ocr(log=False)
            mat = next((b for b in boxes if self.MATERIAL_REALM in b.name), None)
            if not mat:
                self.log_info('RealmTask: material card not found on hub.')
                self.debug_screenshot('material_no_card')
                self.send_key('esc', after_sleep=2)
                continue
            self.click_box(mat, down_time=0.15, after_sleep=3)
            boxes = self.ocr(log=False)
            go = next((b for b in boxes if b.name.strip() == '前往'), None)
            if not go:
                self.log_info('RealmTask: 前往 not found on material level page.')
                self.debug_screenshot('material_no_go')
                self.send_key('esc', after_sleep=2)
                continue
            self.click_box(go, down_time=0.15, after_sleep=8)
            return True
        return False

    def material_prompt(self, attempts=3):
        """确保站在激化台交互范围(有「打开素材激化台」提示), 没有则按住 W 小步前移。
        出生点正对激化台, 实测 1 段(1.5s)即到, 多走会掉下平台"""
        for _ in range(attempts):
            if self.ocr(match=self.ESCALATE_PROMPT, log=True):
                return True
            self.send_key('w', down_time=1.5, after_sleep=1)
        return bool(self.ocr(match=self.ESCALATE_PROMPT, log=True))

    def material_exchange_once(self, first):
        """一次完整兑换: F → 选产物 → 选材料确认 → 激化材料。
        Dry Run 只走到选择材料弹窗即取消, 不消耗体力"""
        if not self.material_prompt():
            self.debug_screenshot('material_no_prompt')
            return False
        boxes = self.ocr(log=False)
        if first or not any('预计获得' in b.name for b in boxes):
            self.park_cursor()
            self.send_key('f', after_sleep=2.5)
            boxes = self.ocr(log=False)
        if any('选择产物' in b.name for b in boxes) and not self.pick_product():
            return False
        if not self.add_material():
            return False
        if self.config.get('Dry Run'):
            self.log_info('RealmTask: DRY RUN - would escalate material here, no energy spent.')
            self.debug_screenshot('material_dry')
            self.send_key('esc', after_sleep=1.5)  # 关选择材料弹窗
            self.send_key('esc', after_sleep=1.5)  # 关素材激化界面
            return True
        escalate = self.wait_ocr(match=self.ESCALATE_BUTTON, time_out=4, log=True)
        if not escalate:
            self.debug_screenshot('material_no_escalate')
            return False
        self.click_box(escalate[0], down_time=0.15, after_sleep=2.5)
        self.confirm_dialog()
        # 激化触发水晶动画小剧场(右下「F 跳过」), 跳过后才是恭喜获得页
        if self.wait_ocr(match=re.compile('跳过'), time_out=4, log=True):
            self.send_key('f', after_sleep=2)
        self.close_reward_page(4)
        self.debug_screenshot('material_after_escalate')
        return True

    def pick_product(self):
        """选择产物页: 点配置产物(标签在圆圈上方, 点标签下方圆心)"""
        name = (self.config.get('Escalate Product') or '噗灵').strip()
        boxes = self.ocr(log=False)
        label = next((b for b in boxes if name in b.name and b.y > self.height * 0.14), None)
        if not label:
            label = next((b for b in boxes
                          if any(p in b.name for p in self.PRODUCTS) and b.y > self.height * 0.14), None)
        if not label:
            self.debug_screenshot('material_no_product')
            return False
        self.click(label.x + label.width / 2, label.y + label.height + self.px(55),
                   down_time=0.15, after_sleep=2.5)
        return bool(self.wait_ocr(match=re.compile('预计获得|品质'), time_out=4, log=True))

    def _scan_material_tiles(self):
        """当前可见的材料格(数量文字在格子右下)"""
        return [b for b in self.ocr(log=False)
                if self.NUM_TILE.fullmatch(b.name.strip())
                and self.height * 0.11 < b.y < self.height * 0.88
                and b.x < self.width * 0.57]

    def add_material(self, attempts=3):
        """点数量最多的材料格 → 「选择材料」弹窗 → 按箭头一键最大 → 确认。
        网格有多页: 下滑一页对比, 更优就点第二页的, 否则滑回第一页点原来的。
        箭头(→|)是图形按钮, 固定在「确认」按钮上方偏右; 游戏会把最大数量限到体力可负担"""
        confirm = None
        for _ in range(attempts):
            tiles = self._scan_material_tiles()
            if not tiles:
                self.debug_screenshot('material_no_tile')
                return False

            def qty(b):
                m = re.match(r'(\d+(?:\.\d+)?)', b.name.strip())
                return float(m.group(1)) if m else 0.0
            best = max(tiles, key=qty)
            best1 = best
            # 下滑一页找数量更多的材料(滚轮不吃 posted, 用真实滚轮, 会短暂拉前台)
            self.real_scroll(self.width * 0.365, self.height * 0.463, 1)
            self.sleep(1)
            tiles2 = self._scan_material_tiles()
            page2 = '无'
            if tiles2:
                best2 = max(tiles2, key=qty)
                page2 = f'{best2.name}({qty(best2):g})'
                if qty(best2) > qty(best):
                    best = best2
                else:
                    self.real_scroll(self.width * 0.365, self.height * 0.463, -1)
                    self.sleep(1)
            self.log_info(f'RealmTask: material page1 best "{best1.name}"({qty(best1):g}), '
                          f'page2 best {page2}, pick "{best.name}" @ ({best.x},{best.y}).')
            # 数量文字在格子右下角, 格子可点区在文字上方
            self.click(best.x + best.width / 2, best.y - self.px(25),
                       down_time=0.15, after_sleep=2)
            confirm = self.wait_ocr(match=re.compile('选择材料|需消耗|确认'), time_out=4, log=True)
            if confirm:
                break
        if not confirm:
            self.debug_screenshot('material_no_dialog')
            return False
        boxes = self.ocr(log=False)
        confirm = next((b for b in boxes if b.name.strip() == '确认'), None)
        if not confirm:
            self.debug_screenshot('material_no_confirm')
            return False
        if self.config.get('Escalate Max', True):
            # 一键最大: 游戏会把数量限到体力可负担的范围
            self.click(confirm.x + confirm.width / 2 + self.px(25), confirm.y - self.px(245),
                       down_time=0.05, after_sleep=1)
            cost = self._dialog_cost(self.ocr(log=False))
            energy = self._energy_available()
            self.log_info(f'RealmTask: escalate max cost={cost}, energy={energy}.')
            if cost == 0:
                # 该材料价值 0 或没有可负担数量, 清空退回 1 个
                clear = next((b for b in self.ocr(log=False)
                              if b.name.strip() == '清空'), None)
                if clear:
                    self.click_box(clear, down_time=0.15, after_sleep=1)
                self.click(confirm.x + confirm.width / 2 - self.px(35), confirm.y - self.px(245),
                           down_time=0.05, after_sleep=0.8)
        self.click_box(confirm, down_time=0.15, after_sleep=1.5)
        if self.wait_ocr(match=re.compile('确认'), time_out=2, log=True):
            # 弹窗没关掉(数量无效), 取消本次
            self.log_info('RealmTask: material dialog still open, cancel.')
            self.debug_screenshot('material_confirm_stuck')
            self.send_key('esc', after_sleep=1.5)
            return False
        return True

    def _dialog_cost(self, boxes):
        """「选择材料」弹窗里 需消耗 的数值"""
        label = next((b for b in boxes if '需消耗' in b.name), None)
        if not label:
            return None
        cands = [b for b in boxes
                 if re.fullmatch(r'\d+', b.name.strip())
                 and abs(b.y - label.y) < self.px(30) and b.x > label.x]
        return int(cands[0].name) if cands else None

    def _energy_available(self):
        m = re.search(r'(\d+)\s*/\s*\d+', ' '.join(b.name for b in self.ocr(log=False)))
        return int(m.group(1)) if m else None

    def in_material_dungeon(self, boxes=None):
        """副本判定: 左上角 BACKSPACE 门按钮(素材激化界面开着时会盖住它)"""
        boxes = boxes or self.ocr(log=False)
        return next((b for b in boxes
                     if b.name.strip().upper() == 'BACKSPACE'
                     and b.x < self.width * 0.115 and b.y < self.height * 0.39), None)

    def leave_material_dungeon(self, attempts=4):
        """退出副本: 先关素材激化界面, 再点击左上门图标(实测 PostMessage 点击有效,
        真实点击反而无效), 有确认框点确认"""
        for i in range(attempts):
            boxes = self.ocr(log=False)
            if any(re.search('预计获得|选择产物|品质', b.name) for b in boxes):
                self.send_key('esc', after_sleep=1.5)
                continue
            back = self.in_material_dungeon(boxes)
            if not back:
                return True
            # 图标可点区在文字上方但偏下, 实测 y-22 点不中, y-12 才行
            self.click(back.x + back.width / 2, max(10, back.y - self.px(12)),
                       down_time=0.15, after_sleep=2.5)
            if self.confirm_dialog(time_out=3):
                self.sleep(3)
            self.sleep(1)
        return not self.in_material_dungeon()

    def weekly_remain_zero(self):
        """周本剩余奖励次数是否 0/1(周页右下/弹窗内); 0 误识为 O/o 也容忍"""
        joined = ' '.join(b.name for b in self.ocr(log=False))
        return bool(re.search(r'剩余奖励次数[^0-9]*[0oO]\s*/\s*1', joined))

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
