import re

from qfluentwidgets import FluentIcon

from src.tasks.MyBaseTask import MyBaseTask


class DailyTask(MyBaseTask):
    """一键日常: 打开暂停菜单, 领取邮件附件和商城免费礼包"""

    # 各页面/按钮的 OCR 关键字(正则), 兼容简中和英文界面, 不准就用 debug 模式校准
    MAIL_PAGE = re.compile('领取|系统邮件|好友邮件|删已读|删除邮件|附件|Mail')
    SHOP_ENTRY = re.compile('商城|商店|Shop')
    CLAIM = re.compile('一键领取|全部领取|领取全部|领取|Claim')
    FREE = re.compile('免费|一键领取|Free')
    # 实测坐标(相对比例): 美鸭梨菜单底部工具排的信封 / 大世界右上角快捷排第一个图标(商城)
    MAIL_ICON_POS = (0.447, 0.930)
    SHOP_ICON_POS = (0.633, 0.062)
    # 邮件页底部「领取全部」按钮
    CLAIM_ALL_POS = (0.292, 0.947)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = "Daily Quest"
        self.description = "Open the in-game menu, claim mail attachments and the free shop pack."
        self.icon = FluentIcon.DATE_TIME
        self.default_config.update({
            'Claim Mail': True,
            'Claim Shop Free Pack': True,
        })
        self.config_description.update({
            'Claim Mail': 'Open the mailbox (envelope icon in the Meiyali menu) and claim all attachments.',
            'Claim Shop Free Pack': 'Open the shop and claim the free daily pack.',
        })

    def run(self, **kwargs):
        self.info_clear()
        if not self.ensure_foreground():
            return
        if not self.ensure_in_game():
            return
        if self.config.get('Claim Mail'):
            self.claim_mail_flow()
        if self.config.get('Claim Shop Free Pack'):
            self.claim_shop_free() # 商城直接走大世界右上角入口, 需在关闭菜单的状态下执行
        self.close_pause_menu()
        self.log_info('DailyTask finished.', notify=True)

    def claim_mail_flow(self, leave_menu_open=False):
        """开菜单进邮件领取。leave_menu_open=True 时领取后只退一次 Esc 停在菜单
        (挖掘入口同在菜单里, 供 MineTask 接力, 不用回大世界再开)"""
        # 邮件入口是美鸭梨菜单底部工具排的信封图标(无文字, 用坐标点击)
        if not self.open_pause_menu():
            self.log_error('DailyTask: cannot open Meiyali menu.', notify=True)
            self.debug_screenshot('no_pause_menu')
            return False
        in_mail = False
        for _ in range(2): # 菜单动画/点击偶发丢失, 重试一次
            self.click(*self.MAIL_ICON_POS, down_time=0.15, after_sleep=2.5) # 游戏会丢超短点击, 需长按
            in_mail = self.wait_ocr(match=self.MAIL_PAGE, time_out=3, log=True)
            if in_mail:
                break
            if not self.ocr(match=self.MENU_MARKERS, log=True): # 菜单被点没了就重开
                self.open_pause_menu()
        if not in_mail:
            self.log_info('DailyTask: failed to open mailbox.')
            self.debug_screenshot('mail_page_not_open')
            self.close_pause_menu()
            return False
        self.park_cursor() # 移开真实光标到角落, 防止悬停弹出物品 tooltip 挡住按钮
        self.sleep(0.5)
        claim = self.wait_ocr(match=self.CLAIM, time_out=3, log=True)
        if not claim:
            # OCR 不中(按钮被挡/艺术字)时兜底: 直接点「领取全部」固定位置
            self.click(*self.CLAIM_ALL_POS, down_time=0.15, after_sleep=2)
        else:
            self.click_box(claim[0], after_sleep=1.5, down_time=0.15)
        self.confirm_dialog()
        self.info_set(self.tr('Mail'), self.tr('Claimed'))
        self.log_info('DailyTask: mail claimed.', notify=True)
        self.send_key('esc', after_sleep=1.5) # 邮件页 -> 菜单
        if not leave_menu_open:
            self.close_pause_menu()
        return True

    def claim_shop_free(self):
        # 商城入口在大世界右上角快捷排: 热区是图标(文字上方); 优先热键 H, 图标真实点击兜底
        if not self.wait_page('shop', 1):
            self.send_key('h', after_sleep=3)
        if not self.wait_page('shop', 2):
            entry = self.wait_ocr(match=self.SHOP_ENTRY, time_out=3, log=True)
            if entry:
                box = entry[0]
                self.real_click(box.x + box.width / 2, box.y - self.px(40))
            else: # OCR 不中退回坐标(右上角第一个图标)
                self.real_click(self.SHOP_ICON_POS[0] * self.width, self.SHOP_ICON_POS[1] * self.height)
        if not self.wait_page('shop', 3):
            self.log_info('DailyTask: shop page did not open (hotkey H and icon click both missed).')
            self.debug_screenshot('shop_not_open')
            self.close_pause_menu()
            return
        # 页内先找「免费」(每日礼包), 再找「一键领取」(循星之旅等进度奖励)
        target = self.wait_ocr(match=self.FREE, time_out=4, log=True)
        if not target:
            target = self.wait_ocr(match=self.CLAIM, time_out=3, log=True)
        if not target:
            self.log_info('DailyTask: no free pack found in shop.')
            self.debug_screenshot('shop_no_free')
            self.send_key('esc', after_sleep=1)
            return
        self.click_box(target[0], after_sleep=1.5, down_time=0.15)
        self.confirm_dialog()
        self.info_set(self.tr('Shop'), self.tr('Claimed'))
        self.log_info('DailyTask: shop free pack claimed.', notify=True)
        self.send_key('esc', after_sleep=1)
        self.send_key('esc', after_sleep=1) # 商城可能有多层页面, 多退一层
