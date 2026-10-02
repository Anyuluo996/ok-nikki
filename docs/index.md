# ok-nikki

[English](en/index.md)

ok-nikki 是一个基于 [ok-script](https://github.com/ok-oldking/ok-script) 的《无限暖暖》(Infinity Nikki) Windows 客户端自动化工具, 通过图像识别与 OCR 模拟用户操作。

> ⚠️ 仅供个人学习交流, 请遵守游戏用户协议与公平运营条款, 使用风险自负。

## 从这里开始

1. 按照[快速开始](getting-started.md)安装依赖并运行。
2. 在[应用配置](configuration.md)中了解运行目标(当前为 Windows 客户端)。
3. 根据[任务开发](tasks.md)添加新任务。
4. 使用[打包与发布](release.md)中的流程生成 EXE。

## 已有任务

- **一键日常 (Daily Quest)**: 打开暂停菜单, 领取邮件附件和商城免费礼包。
  OCR 关键字在 `src/tasks/DailyTask.py` 中, 未命中时任务会自动保存截图到
  `screenshots/`, 用 debug 模式对照校准即可。

## 项目结构

- `src/config.py`: 应用与运行目标(游戏进程/窗口类/分辨率)配置。
- `src/tasks/MyBaseTask.py`: Esc 菜单导航与 OCR 调试辅助。
- `src/tasks/DailyTask.py`: 一键日常任务。
- `assets/`: COCO 模板标注(后续做模板匹配时使用)。
- `i18n/`: gettext 翻译(en_US / zh_CN)。

## 继续阅读

- [游戏自动化入门](https://github.com/ok-oldking/ok-script/blob/master/docs/intro_to_automation/README.md)
- [ok-script 快速开始](https://github.com/ok-oldking/ok-script/blob/master/docs/quick_start/README.md)
- [进阶使用](https://github.com/ok-oldking/ok-script/blob/master/docs/after_quick_start/README.md)
- [API 文档](https://github.com/ok-oldking/ok-script/blob/master/docs/api_doc/README.md)
