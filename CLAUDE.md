# CLAUDE.md

Project conventions and guidance for AI agents working on TinyWhisper.

## What is TinyWhisper?

Local, on-device voice-to-text for macOS Apple Silicon. Records audio via global hotkey, transcribes with Parakeet or Whisper (MLX), and auto-pastes at cursor. Runs entirely on-device — no cloud APIs.

## Quick reference

```bash
# Install
uv sync

# Lint (must pass with 0 errors — this is what CI runs)
uv run ruff check tinywhisper/

# Type check (must pass with 0 errors — this is what CI runs)
uv run pyright tinywhisper/

# Test (all tests)
uv run pytest tests/ -v

# Test (quick — skip build/compile tests)
uv run pytest tests/ -v -m "not build"

# Test (build only — compiles .app and validates bundle)
uv run pytest tests/ -v -m build

# Run
uv run tinywhisper

# Build native macOS .app (--no-editable avoids Documents TCC prompt)
uv sync --no-editable
uv run build_app.py

# Full setup: install, build .app, launch with animated progress
./setup.sh
```

## Architecture

```
main.py          → Entry point, single-instance lock, logging setup
app.py           → Main orchestrator (TinyWhisperApp), tray menu, signal wiring
recorder.py      → Audio capture via sounddevice, emits amplitude for overlay
transcriber.py   → TranscriptionEngine ABC + ParakeetEngine/WhisperEngine + QThread worker
hotkey.py        → Global hotkey via macOS CGEventTap
overlay.py       → Frameless waveform overlay (50-bar, gradient support)
settings.py      → Advanced Settings UI (theme picker, gradient, tidier config)
welcome.py       → Welcome/permissions window, hotkey + device setup
config.py        → Dataclass config (OverlayConfig, HotkeyConfig, etc.) + YAML load/save
themes.py        → 15 built-in waveform color themes
tidier.py        → Optional local LLM text cleanup (mlx-lm)
clipboard.py     → Copy text + simulate Cmd+V paste
icon.py          → Tray icon generation
```

Signal flow: Hotkey toggles recording → Recorder streams amplitude to Overlay → Worker thread transcribes + optionally tidies → Result auto-pasted at cursor.

## Code style

- **Python 3.10+** — use `X | Y` union syntax, not `Union[X, Y]`
- **Type annotations** on all function signatures
- **`from __future__ import annotations`** at top of modules that need it
- **Imports**: stdlib → third-party → local. Use `TYPE_CHECKING` guards for circular deps
- **Logging**: `log = logging.getLogger(__name__)` per module. No `print()` in production code
- **Naming**: PascalCase classes, snake_case functions, `_private` prefix for internal methods
- **Qt patterns**: pyqtSignal for cross-component communication, QThread for blocking work
- **Section dividers**: `# ── Section Name ───────` for visual separation in longer files
- **Docstrings**: module-level required, function-level kept brief
- **No over-engineering**: minimal abstractions, no speculative features

## CI requirements

Every PR must pass:
1. `ruff check tinywhisper/` — 0 errors
2. `pyright tinywhisper/` — 0 errors (warnings OK for macOS-only imports like Quartz)
3. `pytest tests/` — build pipeline tests pass

## Config system

YAML config at `~/.config/tinywhisper/config.yaml`, deserialized via `dacite` into dataclasses in `config.py`. Defaults are in the dataclass fields. Settings UI writes back to YAML on save.

See `config.example.yaml` for all available options with documentation.

## macOS-specific notes

- **Permissions required**: Input Monitoring (hotkey), Accessibility (Cmd+V paste), Microphone (recording)
- **macOS-only imports** (Quartz, ApplicationServices, AVFoundation, ServiceManagement) — these won't import on Linux. Guard or mock when writing cross-platform utilities (see `scripts/screenshots.py` for the mocking pattern)
- **App bundle rebuilds reset macOS permissions** — only rebuild when `launcher.c`, `build_app.py`, or `Info.plist` changes
- **Always `uv sync --no-editable` before `uv run build_app.py`** — the build script detects the venv and bakes site-packages into the launcher. The `--no-editable` flag is required to avoid a Documents TCC prompt when the .app launches

## Common patterns

**Adding a tray menu item**: Edit `_setup_tray_menu()` in `app.py`. Info-only items get `setEnabled(False)` + `setFont(info_font)`. Action items are normal.

**Adding a config option**: Add field to the relevant dataclass in `config.py` → update `config.example.yaml` → wire into the Settings UI in `settings.py` → persist in `_save()`.

**Adding a theme**: Add entry to `THEMES` dict in `themes.py` and append the key to `THEME_ORDER`.

**Worker thread pattern**: Subclass `QThread`, define `pyqtSignal`s, do work in `run()`. Connect signals before calling `.start()`. See `TranscriptionWorker` in `transcriber.py`.
