# 快速开始

## 1. 安装 Python 3.12 和项目依赖

安装 [Python 3.12.10](https://www.python.org/downloads/release/python-31210/)，然后在仓库目录中执行：

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
$PypiIndex = "https://pypi.org/simple/"
python -m pip install --index-url $PypiIndex --upgrade pip
```

根据界面选择一个依赖 profile。Qt 桌面界面：

```powershell
python -m pip install --index-url $PypiIndex --no-deps --upgrade -r requirements.txt
python main_debug.py
```

Web 界面：

```powershell
python -m pip install --index-url $PypiIndex --no-deps --upgrade -r requirements-web.txt
python web_main_debug.py
```

锁定文件用于可重复安装，是日常开发的推荐方式。如果需要直接从
`pyproject.toml` 解析最新的兼容依赖，可以分别使用：

```powershell
python -m pip install --index-url $PypiIndex ".[qt]"
python -m pip install --index-url $PypiIndex ".[web]"
```

只需执行与目标对应的一条命令。官方 PyPI 的 pip 索引入口是
`https://pypi.org/simple/`，而不是网站首页 `https://pypi.org/`；使用后者会导致
`No matching distribution found`，即使该包实际存在。

通常不需要管理员权限。如果游戏以管理员权限运行，自动化程序也需要以相同权限启动，否则截图或输入可能无法生效。

## 2. 运行首个任务

1. 手动启动《无限暖暖》并进入大世界。
2. 启动 Debug 模式（界面上会绘制识别框，便于校准）：

```powershell
python main_debug.py
```

3. 点击「截图测试」确认截图正常。
4. 运行「一键日常」任务；若流程卡住，检查 `screenshots/` 下的自动截图，
   校准 `src/tasks/DailyTask.py` 中的 OCR 正则关键字。

## 3. 日常开发

1. 按[任务开发](tasks.md)创建并注册新任务。
2. 运行测试：

```powershell
python -m unittest tests.TestMain
```

3. 验证完成后，按[打包与发布](release.md)配置工作流并推送 tag
   （打包前先把 `pyappify.yml` 中的 `git_url` 改成自己的仓库地址）。
