# Build TinyWhisper.app

Build the native macOS .app bundle for TinyWhisper.

## Full build + deploy flow

```bash
pkill -f TinyWhisper 2>/dev/null   # kill running instance first
uv sync --no-editable --reinstall-package tinywhisper  # force reinstall even if version unchanged
uv run --no-sync build_app.py      # --no-sync prevents uv from re-syncing as editable
cp -r TinyWhisper.app /Applications/
```

## Reset permissions after build

If the user asks to reset permissions (or uses `--reset-perms`):

```bash
uv run --no-sync build_app.py --reset-perms
```

This runs `tccutil reset All app.tinywhisper` to clear all TCC permissions, forcing macOS to re-prompt on next launch.

## Launch

```bash
open /Applications/TinyWhisper.app
# or double-click in Finder
```

## Notes

- Requires macOS 13+ on Apple Silicon and Python 3.10+
- **Always use `uv sync --no-editable --reinstall-package tinywhisper`** — `--no-editable` copies the real package (editable installs create `.pth` stubs that break the bundle). `--reinstall-package tinywhisper` forces a rebuild even when the version number hasn't changed, preventing stale code in the bundle.
- **Always use `uv run --no-sync`** — `uv run` without `--no-sync` implicitly re-syncs and reinstalls tinywhisper as editable, undoing the `--no-editable` install
- The build copies venv site-packages into `Contents/Resources/site-packages/` (excluding `__pycache__`, `*.pyc`, `*.pth`, `_virtualenv.*`). The launcher resolves this path relative to itself at runtime using `_NSGetExecutablePath()`, so the bundle is fully self-contained with no references to external paths
- `launcher.c` sets `PYTHONHOME`, `PYTHONIOENCODING=utf-8`, and `LC_ALL=en_US.UTF-8` at startup — required for Finder launches which have no locale set
- Each rebuild changes the code signature, which **resets macOS permissions** (Input Monitoring, Accessibility, Microphone). Only rebuild when `launcher.c`, `build_app.py`, or `Info.plist` changes.
- Ad-hoc codesigning is used (`codesign --force --deep --sign -`)
- The app is an LSUIElement (menu bar only, no dock icon)
- App icon: `TinyWhisper.icns` is copied into `Contents/Resources/` during build. Regenerate with `uv run scripts/create_icon.py && iconutil -c icns TinyWhisper.iconset -o TinyWhisper.icns`

## Troubleshooting

- If permissions are lost after rebuild, re-grant them in System Settings > Privacy & Security
- If the app won't launch from Finder, it may already be running (check menu bar). Kill with `pkill -f TinyWhisper` first.
- To reset all permissions: `tccutil reset All app.tinywhisper`
- Crash on Finder launch? Check `~/.config/tinywhisper/tinywhisper.log` — Python exceptions are captured there even when launched without a terminal
- Icon not showing in Finder? Run: `killall Finder; killall Dock` and `/System/Library/Frameworks/CoreServices.framework/Versions/A/Frameworks/LaunchServices.framework/Versions/A/Support/lsregister -f /Applications/TinyWhisper.app`
