# Screenshots

Capture screenshots of every TinyWhisper UI window for documentation, READMEs, and changelogs.

## Capture all screenshots

```bash
python3 scripts/screenshots.py
```

## Capture specific targets

```bash
python3 scripts/screenshots.py welcome settings overlay waveform
```

## Available targets

| Target     | Description                                          |
| ---------- | ---------------------------------------------------- |
| `welcome`  | Welcome / permissions / options window (first launch)|
| `settings` | Advanced Settings window (overlay + tidier config)   |
| `overlay`  | Waveform overlay bar (shown while recording)         |
| `waveform` | Standalone waveform preview widget                   |

## Output

PNGs are written to `screenshots/` in the project root:

```
screenshots/
  welcome.png
  settings.png
  overlay.png
  waveform.png
```

## Notes

- macOS-only system APIs (Quartz, AVFoundation, etc.) are automatically stubbed so the script runs on any platform — including Linux CI
- Audio input devices are simulated with sample entries (MacBook Pro Microphone, External USB Microphone)
- The welcome window is rendered in the "ready" state with all permissions granted
- Default config values are used; edit `AppConfig` defaults or pass a config file to customise appearance
- Run this after UI changes to keep documentation screenshots current
