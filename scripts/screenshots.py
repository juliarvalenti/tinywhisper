#!/usr/bin/env python3
"""Capture screenshots of TinyWhisper UI components for documentation.

Renders each window with realistic mock data and saves PNGs to ``screenshots/``.
macOS-only system frameworks are automatically stubbed so the script works on
any platform (Linux CI, contributor laptops, etc.).

Usage:
    python3 scripts/screenshots.py                  # all targets
    python3 scripts/screenshots.py welcome settings  # specific targets
"""

import math
import sys
from pathlib import Path
from unittest.mock import MagicMock

# ---------------------------------------------------------------------------
# Stub macOS-only frameworks before any tinywhisper imports so the modules
# can be loaded on Linux / CI without raising ImportError.
# ---------------------------------------------------------------------------
for _mod in (
    "Quartz",
    "ApplicationServices",
    "AVFoundation",
    "ServiceManagement",
):
    if _mod not in sys.modules:
        sys.modules[_mod] = MagicMock()

from PyQt6.QtGui import QColor  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

from tinywhisper.config import AppConfig  # noqa: E402

SCREENSHOTS_DIR = Path(__file__).resolve().parent.parent / "screenshots"

# ---------------------------------------------------------------------------
# Capture helpers
# ---------------------------------------------------------------------------


def _save(widget, name: str) -> Path:
    """Grab a widget's rendered pixels and write to disk as PNG."""
    SCREENSHOTS_DIR.mkdir(exist_ok=True)
    path = SCREENSHOTS_DIR / f"{name}.png"
    pixmap = widget.grab()
    pixmap.save(str(path))
    return path


# -- Welcome ----------------------------------------------------------------


def capture_welcome(config: AppConfig) -> Path:
    """Welcome / permissions / options window (shown on first launch)."""
    import tinywhisper.welcome as _mod

    # Patch helpers that require macOS APIs or audio hardware.
    _mod._check_input_monitoring = lambda: True  # type: ignore[assignment]
    _mod._check_accessibility = lambda: True  # type: ignore[assignment]
    _mod._check_microphone = lambda: 3  # type: ignore[assignment]
    _mod.is_launch_at_startup = lambda: False  # type: ignore[assignment]
    _mod._list_input_devices = lambda: [  # type: ignore[assignment]
        {"index": 0, "name": "MacBook Pro Microphone"},
        {"index": 1, "name": "External USB Microphone"},
    ]

    from tinywhisper.welcome import WelcomeWindow

    win = WelcomeWindow(
        hotkey_label="Option+Space",
        model_label="Parakeet TDT 0.6b",
        current_modifier="option",
        current_key="space",
    )
    win.set_ready("Option+Space")
    win.show()
    path = _save(win, "welcome")
    win.close()
    return path


# -- Settings ---------------------------------------------------------------


def capture_settings(config: AppConfig) -> Path:
    """Advanced Settings window (overlay + tidier configuration)."""
    from tinywhisper.settings import SettingsWindow

    win = SettingsWindow(config)
    win.show()
    path = _save(win, "settings")
    win.close()
    return path


# -- Overlay ----------------------------------------------------------------


def capture_overlay(config: AppConfig) -> Path:
    """Waveform overlay bar shown while recording."""
    from tinywhisper.overlay import WaveformOverlay

    overlay = WaveformOverlay(config.overlay)
    # Feed synthetic amplitude data so the bars are visible.
    for i in range(overlay.MAX_BARS):
        amp = abs(math.sin(i * 0.3)) * 0.12 + 0.02
        overlay.push_amplitude(amp)
    overlay.show()
    path = _save(overlay, "overlay")
    overlay.close()
    return path


# -- Waveform preview -------------------------------------------------------


def capture_waveform(config: AppConfig) -> Path:
    """Standalone waveform preview widget (from the settings panel)."""
    from tinywhisper.settings import WaveformPreview

    preview = WaveformPreview()
    preview.setFixedSize(config.overlay.width, config.overlay.height)
    preview.set_opacity(config.overlay.opacity)
    preview.set_color(QColor(config.overlay.color))
    preview.set_bg_color(QColor(config.overlay.bg_color))
    # Tick the animation a few times to populate bars.
    for _ in range(10):
        preview._tick()
    preview.show()
    path = _save(preview, "waveform")
    preview.close()
    return path


# ---------------------------------------------------------------------------
# Registry & CLI
# ---------------------------------------------------------------------------

TARGETS: dict[str, tuple[str, object]] = {
    "welcome": ("Welcome window", capture_welcome),
    "settings": ("Advanced Settings window", capture_settings),
    "overlay": ("Waveform overlay bar", capture_overlay),
    "waveform": ("Waveform preview widget", capture_waveform),
}


def main():
    app = QApplication(sys.argv)
    config = AppConfig()  # all defaults

    requested = sys.argv[1:] or list(TARGETS)

    if requested == ["--help"] or requested == ["-h"]:
        print("usage: screenshots.py [target ...]\n")
        print("Available targets:")
        for name, (desc, _) in TARGETS.items():
            print(f"  {name:12s}  {desc}")
        sys.exit(0)

    print(f"Saving to {SCREENSHOTS_DIR}/\n")

    for name in requested:
        if name not in TARGETS:
            print(f"  unknown target '{name}', choices: {', '.join(TARGETS)}")
            continue
        desc, fn = TARGETS[name]
        try:
            path = fn(config)  # type: ignore[operator]
            print(f"  {name:12s} -> {path.name}")
        except Exception as e:
            print(f"  {name:12s} !! {e}")

    print("\nDone.")
    app.quit()


if __name__ == "__main__":
    main()
