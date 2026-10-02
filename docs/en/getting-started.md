# Quick Start

## 1. Install Python 3.12 and project dependencies

Install [Python 3.12.10](https://www.python.org/downloads/release/python-31210/), then run inside the repository:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
$PypiIndex = "https://pypi.org/simple/"
python -m pip install --index-url $PypiIndex --upgrade pip
```

Pick one profile for the UI. Qt desktop UI:

```powershell
python -m pip install --index-url $PypiIndex --no-deps --upgrade -r requirements.txt
python main_debug.py
```

Web UI:

```powershell
python -m pip install --index-url $PypiIndex --no-deps --upgrade -r requirements-web.txt
python web_main_debug.py
```

The lock files are the recommended daily-development install path. To resolve
the latest compatible dependencies from `pyproject.toml` instead, use:

```powershell
python -m pip install --index-url $PypiIndex ".[qt]"
python -m pip install --index-url $PypiIndex ".[web]"
```

The official PyPI pip index must include `/simple/`; `https://pypi.org/` is not
a valid index URL and leads to `No matching distribution found`.

Administrator rights are usually not required. If the game runs as
administrator, the automation app must run with the same rights, otherwise
capture or input may not work.

## 2. Run the first task

1. Start Infinity Nikki manually and enter the open world.
2. Start debug mode (draws recognition boxes for calibration):

```powershell
python main_debug.py
```

3. Click "Screenshot Test" to verify capture.
4. Run the Daily Quest task. If a flow gets stuck, check the auto-saved
   screenshots under `screenshots/` and calibrate the OCR keywords in
   `src/tasks/DailyTask.py`.

## 3. Day-to-day development

1. Create and register new tasks per [Task development](tasks.md).
2. Run tests:

```powershell
python -m unittest tests.TestMain
```

3. When verified, follow [Packaging and release](release.md) and push a tag
   (set your own `git_url` in `pyappify.yml` first).
