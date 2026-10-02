import unittest

from src.config import config
from ok.test.TaskTestCase import TaskTestCase

from src.tasks.DailyTask import DailyTask


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


if __name__ == '__main__':
    unittest.main()
