# Build TinyWhisper.app

Build the native macOS .app bundle for TinyWhisper.

## Steps

1. Run the build script:
   ```bash
   python3 build_app.py
   ```

2. Install to /Applications (optional):
   ```bash
   cp -r TinyWhisper.app /Applications/
   ```

3. Launch:
   ```bash
   open /Applications/TinyWhisper.app
   # or
   open TinyWhisper.app
   ```

## Notes

- Requires macOS with Apple Silicon and Python 3.10+
- The build compiles `launcher.c` against the local Python framework — no rebuild needed for Python code changes
- Each rebuild changes the code signature, which **resets macOS permissions** (Input Monitoring, Accessibility, Microphone). Only rebuild when `launcher.c`, `build_app.py`, or `Info.plist` changes.
- Ad-hoc codesigning is used (`codesign --force --deep --sign -`)
- The app is an LSUIElement (menu bar only, no dock icon)

## Troubleshooting

- If permissions are lost after rebuild, re-grant them in System Settings > Privacy & Security
- If the app won't launch from Finder, it may already be running (check menu bar for TW icon). Kill with `pkill -f TinyWhisper` first.
- To reset all permissions: `tccutil reset All com.juliarvalenti.tinywhisper`
