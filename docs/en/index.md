# ok-nikki

[中文](../index.md)

ok-nikki is an automation tool for the Infinity Nikki Windows client, built on
[ok-script](https://github.com/ok-oldking/ok-script), driving the game with
computer vision and OCR.

> ⚠️ For personal learning only. Comply with the game terms of service; use at your own risk.

## Start Here

1. Install dependencies and run with the [Quick start](getting-started.md).
2. Review the runtime target in [App configuration](configuration.md).
3. Add new tasks with [Task development](tasks.md).
4. Build an EXE with [Packaging and release](release.md).

## Existing Tasks

- **Daily Quest**: opens the pause menu and claims mail attachments plus the
  free shop pack. OCR keywords live in `src/tasks/DailyTask.py`; when a keyword
  misses, the task saves a screenshot under `screenshots/` for calibration in
  debug mode.

## Project Layout

- `src/config.py`: app and runtime target (game exe, window class, resolution).
- `src/tasks/MyBaseTask.py`: Esc-menu navigation and OCR debugging helpers.
- `src/tasks/DailyTask.py`: the daily quest task.
- `assets/`: COCO template annotations (for future template matching).
- `i18n/`: gettext catalogs (en_US / zh_CN).

## Further Reading (Chinese)

- [Intro to game automation](https://github.com/ok-oldking/ok-script/blob/master/docs/intro_to_automation/README.md)
- [ok-script quick start](https://github.com/ok-oldking/ok-script/blob/master/docs/quick_start/README.md)
- [After quick start](https://github.com/ok-oldking/ok-script/blob/master/docs/after_quick_start/README.md)
- [API documentation](https://github.com/ok-oldking/ok-script/blob/master/docs/api_doc/README.md)
