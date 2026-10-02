# ok-nikki

English | [中文](README.md)

ok-nikki is an automation tool for the Infinity Nikki Windows client, built on [ok-script](https://github.com/ok-oldking/ok-script). It simulates user input via computer vision and OCR — no memory reading, no file modification.

> ⚠️ **Disclaimer**: This is an external assistant tool for personal learning. Automate at your own risk and comply with the Infinity Nikki terms of service and fair-play policy. Do not use it for commercial purposes.

## Status

Scaffold stage, shipping with:

- **Daily Quest**: opens the in-game pause menu and claims mail attachments plus the free shop pack (OCR keyword driven, calibrate with debug mode).
- Full ok-script GUI (Qt / Web), diagnosis task, screenshot test.
- Task / config / i18n / test / packaging skeletons.

OCR keywords and click flows are written from general knowledge of the game UI and are not fully verified on a live client. When a flow gets stuck, run `main_debug.py`, check the auto-saved screenshots under `screenshots/`, and calibrate the regex keywords in `src/tasks/DailyTask.py`.

## Requirements

- Windows 10/11, Python 3.12
- Infinity Nikki PC client, 16:9, at least 1280x720
- Default in-game key bindings; no FPS overlay on the game window

## Quick Start

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --index-url https://pypi.org/simple/ --upgrade pip
python -m pip install --index-url https://pypi.org/simple/ --no-deps --upgrade -r requirements.txt
python main_debug.py
```

1. Start the game manually and enter the open world.
2. Run `python main_debug.py` (debug, draws boxes) or `python main.py` (release). If the game runs as administrator, run the terminal as administrator too.
3. Click "Screenshot Test" in the app to verify capture, then run the Daily Quest task.

For the web UI, use `requirements-web.txt` and `python web_main_debug.py`.

## Development

- Tasks live in `src/tasks/`; `MyBaseTask` provides Esc-menu navigation and OCR debugging helpers.
- Register new tasks in `onetime_tasks` in `src/config.py`; see `docs/en/tasks.md`.
- Run tests: `python -m unittest tests.TestMain`.
- Packaging: push a `v*` tag to trigger GitHub Actions; set your own `git_url` in `pyappify.yml` first.

## Credits

- [ok-script](https://github.com/ok-oldking/ok-script) — automation framework
- [ok-script-app](https://github.com/ok-oldking/ok-script-app) — project template
- [OnnxOCR](https://github.com/ok-oldking/OnnxOCR)
- [PyQt-Fluent-Widgets](https://github.com/zhiyiYo/PyQt-Fluent-Widgets)
