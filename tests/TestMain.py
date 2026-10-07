import unittest

from src.config import config
from ok.test.TaskTestCase import TaskTestCase

from src.tasks.DailyTask import DailyTask
from src.tasks.MineTask import MineTask
from src.tasks.RealmTask import RealmTask


class TestDailyTask(TaskTestCase):
    task_class = DailyTask

    config = config

    def test_task_metadata(self):
        self.assertEqual("Daily Quest", self.task.name)
        self.assertTrue(self.task.description)

    def test_default_config(self):
        self.assertIsInstance(self.task.default_config['Claim Mail'], bool)
        self.assertIsInstance(self.task.default_config['Claim Shop Free Pack'], bool)
        self.assertTrue(self.task.default_config['Claim Mail'])
        self.assertTrue(self.task.default_config['Claim Shop Free Pack'])

    def test_task_registered_in_config(self):
        registered = [pair[1] for pair in config['onetime_tasks']]
        self.assertIn('DailyTask', registered)
        self.assertIn('DiagnosisTask', registered)

    def test_windows_target_configured(self):
        self.assertEqual(['X6Game-Win64-Shipping.exe'], config['windows']['exe'])
        self.assertEqual('UnrealWindow', config['windows']['hwnd_class'])

    def test_realm_and_mine_defaults(self):
        # 借用同一 executor 构造, 避免多套件反复 init_ok/destroy_ok 留僵尸线程
        realm = RealmTask(self.task.executor, None)
        self.assertFalse(realm.default_config['Drain Energy'])
        self.assertIsInstance(realm.default_config['Challenge Count'], int)
        self.assertIn('Drain Energy', realm.config_description)
        mine = MineTask(self.task.executor, None)
        # 网格入口只认真实点击, 后台温和激活打不开挖掘页(实测), 默认必须允许抢前台
        self.assertTrue(mine.default_config['Allow Foreground Steal'])
        self.assertTrue(mine.default_config['Dig Again After Harvest'])


if __name__ == '__main__':
    unittest.main()
