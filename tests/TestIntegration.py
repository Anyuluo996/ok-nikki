import threading
import types
import unittest

import numpy as np
from ok.device.interaction_methods.genshin import GenshinInteraction

from src.config import config
from src.device.NikkiInteraction import NikkiInteraction
from src.process_feature import binarize_for_matching, convert_bw, process_feature
from src.tasks.MouseResetTask import MouseResetTask
from src.tasks.MyBaseTask import MyBaseTask
from src.tasks.RealmTask import RealmTask

# TaskTestCase.setUpClass 会清空 config['trigger_tasks'], 导入时先快照
_TRIGGER_TASKS_SNAPSHOT = [pair[1] for pair in config['trigger_tasks']]


class _StubCapture:
    width = 1920
    height = 1080

    def get_abs_cords(self, x, y):
        return x, y


class _StubHwndWindow:
    top_hwnd = 0
    hwnd = 0
    visible_monitors = []

    def is_foreground(self):
        return False


class TestProcessFeature(unittest.TestCase):

    def test_binarize_for_matching(self):
        img = np.zeros((4, 4, 3), dtype=np.uint8)
        img[:2] = 250
        out = binarize_for_matching(img)
        self.assertEqual(out.shape, (4, 4))
        self.assertEqual(out[0, 0], 255)
        self.assertEqual(out[3, 3], 0)

    def test_convert_bw_keeps_channels(self):
        img = np.zeros((2, 2, 3), dtype=np.uint8)
        img[0, 0] = 250
        out = convert_bw(img)
        self.assertEqual(out.shape, (2, 2, 3))
        self.assertEqual(out[0, 0, 0], 255)
        self.assertEqual(out[1, 1, 0], 0)

    def test_process_feature_noop_for_unregistered(self):
        class _Feature:
            mat = np.full((2, 2, 3), 128, dtype=np.uint8)

        feature = _Feature()
        process_feature('UnknownFeature', feature)
        self.assertEqual(feature.mat[0, 0, 0], 128)

    def test_config_wires_feature_processor(self):
        self.assertIs(config['template_matching']['feature_processor'], process_feature)


class TestNikkiInteraction(unittest.TestCase):

    def setUp(self):
        self.interaction = NikkiInteraction(_StubCapture(), _StubHwndWindow())

    def test_has_input_lock(self):
        self.assertIsInstance(self.interaction._input_lock, type(threading.RLock()))

    def test_operate_counts_operating_and_propagates(self):
        seen = []

        def work():
            seen.append(self.interaction._operating)
            return 42

        self.assertEqual(self.interaction.operate(work), 42)
        self.assertEqual(seen, [1])
        self.assertEqual(self.interaction._operating, 0)

    def test_operate_resets_counter_on_exception(self):
        def boom():
            raise RuntimeError('x')

        self.interaction.operate(boom)
        self.assertEqual(self.interaction._operating, 0)

    def test_hold_operating(self):
        with self.interaction.hold_operating():
            self.assertEqual(self.interaction._operating, 1)
            with self.interaction.hold_operating():
                self.assertEqual(self.interaction._operating, 2)
        self.assertEqual(self.interaction._operating, 0)

    def test_hold_operating_resets_on_exception(self):
        try:
            with self.interaction.hold_operating():
                raise RuntimeError('x')
        except RuntimeError:
            pass
        self.assertEqual(self.interaction._operating, 0)

    def test_send_key_down_up_overridden_not_genshin(self):
        # 父类 GenshinInteraction.send_key_up 不发 WM_KEYUP 且会 deactivate, 必须被覆写
        self.assertIsNot(NikkiInteraction.send_key_up, GenshinInteraction.send_key_up)
        self.assertIsNot(NikkiInteraction.send_key_down, GenshinInteraction.send_key_down)

    def test_send_key_up_safe_on_invalid_hwnd(self):
        # stub 句柄无效: post 吞异常不抛, 计数器不受影响
        self.interaction.send_key_up('w')
        self.interaction.send_key_down('w')
        self.assertEqual(self.interaction._operating, 0)

    def test_post_swallows_invalid_hwnd(self):
        self.interaction.post(0x0000, 0, 0)  # 不抛即通过


class TestMouseResetTaskMeta(unittest.TestCase):

    def test_registered_in_trigger_tasks(self):
        self.assertIn('MouseResetTask', _TRIGGER_TASKS_SNAPSHOT)


class TestPageSigs(unittest.TestCase):
    """页面特征判定顺序: 顺序错了会把 A 页判成 B 页(实战踩过: 通行证页左下
    返回按钮叫「乐园构想」, park 特征排在 passport 前时通行证页被误判)"""

    def _sig(self, text):
        task = object.__new__(MyBaseTask)  # page_sig 只依赖 PAGE_SIGS, 不用走 __init__
        return task.page_sig([types.SimpleNamespace(name=text)])

    def test_passport_page_not_misparked(self):
        # 通行证页含「悠远颂歌」和左下返回按钮「乐园构想」, 必须判成 passport
        self.assertEqual(self._sig('悠远颂歌 旅行秘宝 旅行任务 乐园构想'), 'passport')

    def test_park_page(self):
        # 乐园构想页用页签名判定(顶栏也有「乐园构想」字样, 不能用作特征)
        self.assertEqual(self._sig('乐园构想 构想契约 乐园纪事 获取乐园基石'), 'park')

    def test_world_topbar_not_misparked(self):
        # 新版大世界顶栏快捷排就带「乐园构想」, 不得判成任何子页
        self.assertEqual(self._sig(MyBaseTask.WORLD_TOPBAR_TEXT), 'other')

    def test_calendar_page(self):
        self.assertEqual(self._sig('阅历挑战 每日灵感'), 'calendar')


class TestRealmDrainParse(unittest.TestCase):
    """注入弹窗「消耗40活跃能量, 领取奖励N次」的次数解析(耗尽体力模式依赖)"""

    def test_parse_claim_count(self):
        self.assertEqual(RealmTask.parse_claim_count(
            ['试炼奖励', '消耗40活跃能量, 领取奖励7次']), 7)
        self.assertEqual(RealmTask.parse_claim_count(['领取奖励 12 次']), 12)
        self.assertIsNone(RealmTask.parse_claim_count(['消耗40活跃能量']))  # 无次数行
        self.assertEqual(RealmTask.parse_claim_count(['领取奖励0次']), 0)  # 体力不足


if __name__ == '__main__':
    unittest.main()
