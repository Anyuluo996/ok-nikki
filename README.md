# ok-nikki

[English](README_en.md) | 中文

ok-nikki 是一个基于 [ok-script](https://github.com/ok-oldking/ok-script) 的《无限暖暖》(Infinity Nikki) Windows 客户端自动化工具,通过图像识别与 OCR 模拟用户操作,无内存读取、无文件修改。

> ⚠️ **免责声明**: 本工具为个人学习交流用的外部辅助程序,仅供自动化重复性日常操作。请自行评估并遵守《无限暖暖》用户协议与公平运营条款,使用本工具产生的一切风险由使用者自行承担。请勿用于商业或营利目的。

## 当前状态

项目已完成实机链路打通(2026-10-02):

- **登录页点击进入游戏** → 加载等待 → 弹窗清理 → 大世界判定(`ensure_in_game`)。
- **美鸭梨菜单导航**(Esc):邮件入口为底部信封图标(坐标点击),商城走**大世界右上角快捷入口**(OCR「商城」)。
- 一键日常实测能完整跑通流程;邮件「领取」与商城「免费礼包」的按钮文案需在**账号实际有可领内容**时做最后校准(失败会自动存截图到 `screenshots/`)。

> ⚠️ **必须以管理员身份运行**:无限暖暖游戏进程以管理员权限运行,普通权限的脚本发出的鼠标/键盘输入会被 Windows UIPI 静默丢弃(截图和 OCR 不受影响)。GUI(`main_debug.py`)同样需要管理员终端启动。

## 运行环境

- Windows 10/11,Python 3.12
- 《无限暖暖》PC 客户端(管理员权限运行),16:9 分辨率,最低 1280x720
- 游戏窗口需为窗口化/无边框(全屏独占下 WGC 截图可能收不到帧)

## 快速开始

```powershell
py -3.12 -m venv .venv   # 注意: 本机 py -3.12 若指向 conda, 请改用 uv: uv venv --python 3.12 .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --index-url https://pypi.org/simple/ --upgrade pip
python -m pip install --index-url https://pypi.org/simple/ --no-deps --upgrade -r requirements.txt
```

**方式一: 命令行一键日常(推荐, 自动提权)**

右键"使用 PowerShell 运行" `run_daily_admin.ps1` 并在 UAC 中点"是";或在管理员 PowerShell 中:

```powershell
powershell -ExecutionPolicy Bypass -File D:\app\ok-nikki\run_daily_admin.ps1
```

**方式二: GUI 调试模式**(校准关键字/看识别框)

以管理员身份打开终端后:

```powershell
python main_debug.py
```

1. 手动启动游戏(登录页即可, 任务会自动点「点击进入游戏」)。
2. 在界面中点击「截图测试」确认截图正常, 再运行「一键日常」任务。
3. debug 模式会在游戏画面上绘制识别框, 方便校准 `src/tasks/DailyTask.py` 中的正则关键字。

Web 界面把依赖与启动命令换成 `requirements-web.txt` 和 `python web_main_debug.py`(同样需管理员)。

## 开发

- 任务代码在 `src/tasks/`,基类 `MyBaseTask` 提供 Esc 菜单导航与 OCR 调试辅助。
- 新任务在 `src/config.py` 的 `onetime_tasks` 中注册,写法见 `docs/tasks.md`。
- 运行测试: `python -m unittest tests.TestMain`。
- 文档站点: `docs/`(MkDocs),构建方式见 `docs/documentation.md`。
- 打包发布: 推送 `v*` tag 触发 GitHub Actions,详见 `docs/release.md`;打包前先在 `pyappify.yml` 中把 `git_url` 改成自己的仓库地址。

## 致谢

- [ok-script](https://github.com/ok-oldking/ok-script) — 自动化框架
- [ok-script-app](https://github.com/ok-oldking/ok-script-app) — 项目模板
- [OnnxOCR](https://github.com/ok-oldking/OnnxOCR)
- [PyQt-Fluent-Widgets](https://github.com/zhiyiYo/PyQt-Fluent-Widgets)
