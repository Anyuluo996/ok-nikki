# Packaging and Release

## Release Files

- `.github/workflows/build.yml`: watches `v*` tags, runs tests, packages, and creates a GitHub Release.
- `pyappify.yml`: defines the app name, entry point, icon, Python version, and update repositories.
- `pyproject.toml`: defines the Qt, web, and documentation dependency profiles.
- `requirements.txt` and `requirements-web.txt`: compiled installation locks for the TOML profiles.
- `deploy.txt`: lists files copied to a dedicated update repository, if you use one.

MirrorChyan and CNB integrations are currently not configured; see the
[ok-script-app template](https://github.com/ok-oldking/ok-script-app) workflows if you want them.

## Before the First Release

1. Point the `China` profile's `git_url` in `pyappify.yml` to your own repository
   (the source repository is fine for early testing; use a dedicated lightweight
   update repository for releases).
2. If you use a dedicated update repository, add the sync step and secrets back to `build.yml`.
3. Customize the Release step body in `build.yml` if needed.

## Push a Version Tag

Commit and push the project, then create a tag matching `v*`:

```bash
git add .
git commit -m "Initialize ok-nikki"
git push origin HEAD
git tag v0.1.0
git push origin v0.1.0
```

GitHub Actions runs the tests, packages the EXE, and creates the GitHub Release.
Installer names: `ok-nikki-win32-China-setup.exe`, `ok-nikki-win32-Web-setup.exe`.

## Recompile Locks After Changing Dependencies

```powershell
python -m piptools compile --extra qt --strip-extras --no-header --output-file requirements.txt pyproject.toml
python -m piptools compile --extra web --strip-extras --no-header --output-file requirements-web.txt pyproject.toml
python -m piptools compile --extra docs --strip-extras --no-header --output-file requirements-docs.txt pyproject.toml
```

The Qt lock is installed with `--no-deps`. After compilation, remove the
generated `pyside6` and `pyside6-addons` entries while retaining
`pyside6-essentials`, so Fluent Widgets does not restore unused PySide6 modules.
