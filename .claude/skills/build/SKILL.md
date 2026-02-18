# Build TinyWhisper.app

Build the native macOS .app bundle for TinyWhisper.

## Full build + deploy flow

```bash
pkill -f TinyWhisper 2>/dev/null   # kill running instance first
pip install .                       # non-editable install (required — editable installs trigger Documents TCC prompt)
python3 build_app.py
cp -r TinyWhisper.app /Applications/
```

## Launch

```bash
open /Applications/TinyWhisper.app
# or double-click in Finder
```

## Notes

- Requires macOS 13+ on Apple Silicon and Python 3.10+
- **Always use `pip install .` (not `-e`)** — editable installs symlink into `~/Documents/` and trigger a macOS TCC permission prompt when the .app imports code
- The build compiles `launcher.c` against the local Python framework — no rebuild needed for Python-only changes, but you must re-run `pip install .` so site-packages is updated
- `launcher.c` sets `PYTHONHOME`, `PYTHONIOENCODING=utf-8`, and `LC_ALL=en_US.UTF-8` at startup — required for Finder launches which have no locale set
- Each rebuild changes the code signature, which **resets macOS permissions** (Input Monitoring, Accessibility, Microphone). Only rebuild when `launcher.c`, `build_app.py`, or `Info.plist` changes.
- Ad-hoc codesigning is used (`codesign --force --deep --sign -`)
- The app is an LSUIElement (menu bar only, no dock icon)
- App icon: `TinyWhisper.icns` is copied into `Contents/Resources/` during build. Regenerate with `python3 scripts/create_icon.py && iconutil -c icns TinyWhisper.iconset -o TinyWhisper.icns`

## Troubleshooting

- If permissions are lost after rebuild, re-grant them in System Settings > Privacy & Security
- If the app won't launch from Finder, it may already be running (check menu bar). Kill with `pkill -f TinyWhisper` first.
- To reset all permissions: `tccutil reset All com.juliarvalenti.tinywhisper`
- Crash on Finder launch? Check `~/.config/tinywhisper/tinywhisper.log` — Python exceptions are captured there even when launched without a terminal
- Icon not showing in Finder? Run: `killall Finder; killall Dock` and `/System/Library/Frameworks/CoreServices.framework/Versions/A/Frameworks/LaunchServices.framework/Versions/A/Support/lsregister -f /Applications/TinyWhisper.app`
