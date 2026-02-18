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
    # Stub version/git so screenshots are stable across commits.
    _mod._get_version = lambda: "0.1.0"  # type: ignore[assignment]
    _mod._get_git_commit = lambda: ""  # type: ignore[assignment]

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


# -- Themes grid ------------------------------------------------------------


def capture_themes(config: AppConfig) -> Path:
    """One waveform screenshot per built-in theme + a composite grid."""
    import math as _math

    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import QColor, QPainter, QPixmap

    from tinywhisper.config import OverlayConfig
    from tinywhisper.overlay import WaveformOverlay
    from tinywhisper.themes import THEMES

    themes_dir = SCREENSHOTS_DIR / "themes"
    themes_dir.mkdir(exist_ok=True)

    W, H = 300, 60
    COLS = 3
    PAD = 10
    LABEL_H = 20

    def _make_amps(n: int) -> list[float]:
        import random
        rng = random.Random(7)  # deterministic seed for reproducibility
        # Slow envelope groups bars like spoken words; fast wave adds fine detail
        return [
            max(0.04, min(1.0,
                abs(_math.sin(i * 0.13)) ** 0.7          # slow speech envelope
                * (abs(_math.sin(i * 0.95 + 0.4)) * 0.7 + 0.3)  # fast detail
                + rng.uniform(-0.08, 0.08)               # noise
            ))
            for i in range(n)
        ]

    theme_items = list(THEMES.items())
    ROWS = _math.ceil(len(theme_items) / COLS)

    grid_w = COLS * W + (COLS + 1) * PAD
    grid_h = ROWS * (H + LABEL_H) + (ROWS + 1) * PAD
    grid = QPixmap(grid_w, grid_h)
    grid.fill(QColor("#111111"))
    grid_painter = QPainter(grid)
    grid_painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    font = grid_painter.font()
    font.setFamily(".AppleSystemUIFont")
    font.setPointSize(10)
    grid_painter.setFont(font)

    for idx, (key, theme) in enumerate(theme_items):
        ov_cfg = OverlayConfig(
            enabled=True,
            width=W,
            height=H,
            opacity=theme.opacity,
            color=theme.color,
            bg_color=theme.bg_color,
            gradient=bool(theme.gradient_colors),
            gradient_colors=theme.gradient_colors,
        )
        overlay = WaveformOverlay(ov_cfg)
        overlay.show()
        # Write directly to avoid the *8 saturation in push_amplitude
        overlay._bars.extend(_make_amps(WaveformOverlay.MAX_BARS))
        overlay.update()
        px = overlay.grab()
        overlay.close()

        px.save(str(themes_dir / f"{key}.png"))

        col = idx % COLS
        row = idx // COLS
        x = PAD + col * (W + PAD)
        y = PAD + row * (H + LABEL_H + PAD)

        grid_painter.drawPixmap(x, y, px)
        grid_painter.setPen(QColor("#AAAAAA"))
        grid_painter.drawText(x, y + H + 2, W, LABEL_H, Qt.AlignmentFlag.AlignCenter, theme.label)

    grid_painter.end()

    composite = SCREENSHOTS_DIR / "themes.png"
    grid.save(str(composite))
    return composite


# ---------------------------------------------------------------------------
# Registry & CLI
# ---------------------------------------------------------------------------

TARGETS: dict[str, tuple[str, object]] = {
    "welcome": ("Welcome window", capture_welcome),
    "settings": ("Advanced Settings window", capture_settings),
    "overlay": ("Waveform overlay bar", capture_overlay),
    "waveform": ("Waveform preview widget", capture_waveform),
    "themes": ("All themes grid + per-theme PNGs", capture_themes),
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
