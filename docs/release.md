# 打包与发布

## 发布相关文件

- `.github/workflows/build.yml`：监听 `v*` tag，运行测试、打包并创建 GitHub Release。
- `pyappify.yml`：定义应用名称、入口、图标、Python 版本和更新仓库。
- `pyproject.toml`：定义 Qt、Web 和文档依赖 profile。
- `requirements.txt`、`requirements-web.txt`：由 TOML profile 编译的安装锁定文件。
- `deploy.txt`：如使用独立更新仓库，定义需要同步的文件。

当前配置未接入 Mirror酱 与 CNB；如需接入可参考
[ok-script-app 模板](https://github.com/ok-oldking/ok-script-app) 的工作流。

## 首次发布前

1. 在 `pyappify.yml` 中把 `China` profile 的 `git_url` 改成自己的仓库地址
   （前期测试可直接用源码仓库；正式发布建议用独立的轻量更新仓库）。
2. 如使用独立更新仓库，在 `build.yml` 中补回同步步骤并配置对应 Secrets。
3. 如需自定义 Release 说明，编辑 `build.yml` 中的 Release 步骤。

## 推送版本 tag

提交并推送项目，再创建符合 `v*` 规则的 tag：

```bash
git add .
git commit -m "Initialize ok-nikki"
git push origin HEAD
git tag v0.1.0
git push origin v0.1.0
```

GitHub Actions 会运行测试、打包 EXE，并创建对应的 GitHub Release。
安装包名：`ok-nikki-win32-China-setup.exe`、`ok-nikki-win32-Web-setup.exe`。

## 修改依赖后重新编译锁定文件

```powershell
python -m piptools compile --extra qt --strip-extras --no-header --output-file requirements.txt pyproject.toml
python -m piptools compile --extra web --strip-extras --no-header --output-file requirements-web.txt pyproject.toml
python -m piptools compile --extra docs --strip-extras --no-header --output-file requirements-docs.txt pyproject.toml
```

Qt 锁定文件使用 `--no-deps` 安装。编译完成后，删除生成的 `pyside6` 和
`pyside6-addons` 条目，但保留 `pyside6-essentials`，避免 Fluent Widgets
重新引入未使用的完整 PySide6 组件。
