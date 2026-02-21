"""Settings window for overlay appearance with live preview."""

from __future__ import annotations

import math
import random
from pathlib import Path

import yaml
from PyQt6.QtCore import Qt, QRectF, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QLinearGradient, QPainter, QPen
from PyQt6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QColorDialog,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from tinywhisper.config import AppConfig, CONFIG_DIR, CONFIG_PATH, WaveformStyle
from tinywhisper.overlay import gradient_color_at
from tinywhisper.themes import THEMES, THEME_ORDER
from tinywhisper.welcome import _list_input_devices

# ---------------------------------------------------------------------------
# Prompt script helpers
# ---------------------------------------------------------------------------

# Scripts live as real files in tinywhisper/scripts/ and are copied to
# ~/.config/tinywhisper/scripts/ at startup.  Settings just stores the path.
# Known script names — checked against the destination dir to avoid touching
# the bundle path (which lives under ~/Documents/) on every launch.
_BUNDLED_SCRIPT_NAMES = ["claude-context.py"]


def _seed_example_scripts(scripts_dir: Path) -> None:
    """Copy bundled prompt scripts to scripts_dir if they don't exist yet.

    We check destinations first so we never access the bundle path (which may
    be under ~/Documents/) once all scripts are already seeded.
    """
    missing = [n for n in _BUNDLED_SCRIPT_NAMES if not (scripts_dir / n).exists()]
    if not missing:
        return
    import shutil
    bundle_dir = Path(__file__).parent / "scripts"
    for name in missing:
        src = bundle_dir / name
        dst = scripts_dir / name
        if src.exists():
            shutil.copy2(src, dst)
            dst.chmod(0o755)


class WaveformPreview(QWidget):
    """Animated waveform preview that reflects current settings."""

    MAX_BARS = 60
    MAX_BRAILLE_BARS = 100

    def __init__(self, parent=None):
        super().__init__(parent)
        self._opacity = 0.85
        self._color = QColor("#FF6B6B")
        self._bg_color = QColor("#1E1E1E")
        self._gradient = False
        self._gradient_colors: list[QColor] = []
        self._braille = False
        self._phase = 0.0
        self._bars: list[float] = [0.0] * self.MAX_BARS

        self._timer = QTimer(self)
        self._timer.setInterval(50)  # 20fps
        self._timer.timeout.connect(self._tick)

    def reset(self):
        self._phase = 0.0
        self._bars = [0.0] * self.MAX_BARS
        self.update()

    def start(self):
        self._timer.start()

    def stop(self):
        self._timer.stop()

    def set_opacity(self, opacity: float):
        self._opacity = opacity
        self.update()

    def set_color(self, color: QColor):
        self._color = color
        self.update()

    def set_bg_color(self, color: QColor):
        self._bg_color = color
        self.update()

    def set_gradient(self, enabled: bool, colors: list[QColor] | None = None):
        self._gradient = enabled and colors is not None and len(colors) >= 2
        if colors is not None:
            self._gradient_colors = list(colors)
        self.update()

    def set_braille(self, enabled: bool):
        self._braille = enabled
        self.update()

    def _tick(self):
        self._phase += 0.15
        for i in range(self.MAX_BARS):
            wave = math.sin(self._phase + i * 0.3) * 0.4 + 0.5
            noise = random.uniform(-0.1, 0.1)
            self._bars[i] = max(0.05, min(1.0, wave + noise))
        self.update()

    def paintEvent(self, a0):  # type: ignore[override]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()

        # Background gradient
        bg_top = QColor(self._bg_color)
        bg_top.setAlpha(int(255 * self._opacity))
        bg_bot = QColor(self._bg_color).darker(130)
        bg_bot.setAlpha(int(255 * self._opacity))
        bg_grad = QLinearGradient(0, 0, 0, h)
        bg_grad.setColorAt(0, bg_top)
        bg_grad.setColorAt(1, bg_bot)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(bg_grad)
        painter.drawRoundedRect(QRectF(0, 0, w, h), 14, 14)

        # Inner highlight
        painter.setPen(QPen(QColor(255, 255, 255, 18), 1.0))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(QRectF(0.5, 0.5, w - 1, h - 1), 14, 14)

        if self._braille:
            # --- Dot grid waveform ---
            r = 1.5
            diameter = r * 2
            min_step_v = diameter + 2.5
            min_step_h = diameter + 2.0

            margin_v = 8
            margin_h = 8
            usable_h = h - margin_v * 2
            usable_w = w - margin_h * 2

            n_rows = max(1, int(usable_h // min_step_v))
            n_cols = max(1, min(self.MAX_BRAILLE_BARS, int(usable_w // min_step_h)))
            step_v = usable_h / n_rows
            step_h = usable_w / n_cols

            x0 = float(margin_h)
            y0 = float(margin_v)

            painter.setPen(Qt.PenStyle.NoPen)

            for i in range(n_cols):
                src = int(i * self.MAX_BARS / n_cols)
                amp = self._bars[src]

                if self._gradient and self._gradient_colors:
                    t = i / max(1, n_cols - 1)
                    base_color = gradient_color_at(self._gradient_colors, t)
                else:
                    base_color = QColor(self._color)

                bar_dots = amp * (n_rows - 1)
                center = (n_rows - 1) / 2
                bar_top = center - bar_dots / 2
                bar_bot = center + bar_dots / 2

                cx = x0 + i * step_h + r
                for row in range(n_rows):
                    dot_on = bar_top <= row <= bar_bot
                    color = QColor(base_color)
                    if not dot_on:
                        color.setAlpha(max(0, int(base_color.alpha() * 0.15)))
                    painter.setBrush(color)
                    cy = y0 + row * step_v + r
                    painter.drawEllipse(QRectF(cx - r, cy - r, diameter, diameter))
        else:
            # --- Rectangular bar waveform ---
            bar_w = max(3, (w - 16) // self.MAX_BARS - 1)
            gap = 1
            total_bar_w = self.MAX_BARS * (bar_w + gap) - gap
            x_start = (w - total_bar_w) / 2
            mid_y = h / 2

            painter.setPen(Qt.PenStyle.NoPen)
            for i, amp in enumerate(self._bars):
                bh = max(3, int(amp * (h - 18)))
                x = x_start + i * (bar_w + gap)
                y = mid_y - bh / 2

                if self._gradient and self._gradient_colors:
                    t = i / max(1, self.MAX_BARS - 1)
                    color = gradient_color_at(self._gradient_colors, t)
                    painter.setBrush(color)
                else:
                    painter.setBrush(self._color)

                painter.drawRoundedRect(QRectF(x, y, bar_w, bh), 1.5, 1.5)

        painter.end()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_COLOR_BTN_STYLE = (
    "background-color: {hex}; border: 1px solid #888; border-radius: 4px;"
)


def _make_color_btn(color: QColor, callback) -> QPushButton:
    btn = QPushButton()
    btn.setFixedSize(60, 28)
    btn.setStyleSheet(_COLOR_BTN_STYLE.format(hex=color.name()))
    btn.clicked.connect(callback)
    return btn


# ---------------------------------------------------------------------------
# Hotkey recorder widget
# ---------------------------------------------------------------------------

class HotkeyRecorder(QWidget):
    """Click-to-record keyboard shortcut widget.

    Shows the current binding as a pill tag.  Click to enter recording mode,
    then press any modifier + key combo.  Escape cancels.
    """

    binding_changed = pyqtSignal(str, str)  # modifier, key

    # On macOS, Qt maps Cmd → MetaModifier and Option → AltModifier.
    _MOD_PRIORITY: list[tuple[Qt.KeyboardModifier, str]] = [
        (Qt.KeyboardModifier.MetaModifier, "cmd"),
        (Qt.KeyboardModifier.AltModifier, "option"),
        (Qt.KeyboardModifier.ControlModifier, "ctrl"),
        (Qt.KeyboardModifier.ShiftModifier, "shift"),
    ]
    _MOD_DISPLAY = {"option": "⌥", "ctrl": "⌃", "cmd": "⌘", "shift": "⇧", "none": ""}

    # Keys that can be bound without a modifier (F-keys + special keys)
    _BARE_KEY_CODES: frozenset[int] = frozenset({
        int(Qt.Key.Key_F1),  int(Qt.Key.Key_F2),  int(Qt.Key.Key_F3),
        int(Qt.Key.Key_F4),  int(Qt.Key.Key_F5),  int(Qt.Key.Key_F6),
        int(Qt.Key.Key_F7),  int(Qt.Key.Key_F8),  int(Qt.Key.Key_F9),
        int(Qt.Key.Key_F10), int(Qt.Key.Key_F11), int(Qt.Key.Key_F12),
        int(Qt.Key.Key_Space), int(Qt.Key.Key_Tab),
        int(Qt.Key.Key_Return), int(Qt.Key.Key_Enter),
        int(Qt.Key.Key_Backspace),
    })

    # Modifier-only key codes — don't commit when these are pressed alone
    _MODIFIER_KEY_CODES: frozenset[int] = frozenset({
        int(Qt.Key.Key_Alt),
        int(Qt.Key.Key_Control),
        int(Qt.Key.Key_Meta),
        int(Qt.Key.Key_Shift),
        int(Qt.Key.Key_AltGr),
        int(Qt.Key.Key_CapsLock),
    })

    # Qt key code → config key string (must match hotkey.py _VKEY_MAP)
    # Populated by _build_qt_key_map() below the class definition.
    _QT_TO_CONFIG: dict[int, str] = {}

    _STYLE_IDLE = (
        "HotkeyRecorder {"
        "  background: rgba(255,255,255,0.07);"
        "  border: 1px solid rgba(255,255,255,0.20);"
        "  border-radius: 8px;"
        "}"
        "HotkeyRecorder:hover {"
        "  background: rgba(255,255,255,0.11);"
        "  border: 1px solid rgba(255,255,255,0.35);"
        "}"
    )
    _STYLE_RECORDING = (
        "HotkeyRecorder {"
        "  background: rgba(255,107,107,0.15);"
        "  border: 2px solid #FF6B6B;"
        "  border-radius: 8px;"
        "}"
    )

    def __init__(self, modifier: str, key: str, parent=None):
        super().__init__(parent)
        self._modifier = modifier
        self._key = key
        self._recording = False

        self.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(38)
        self.setMinimumWidth(180)

        inner = QHBoxLayout(self)
        inner.setContentsMargins(12, 4, 12, 4)
        self._label = QLabel()
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._label.setStyleSheet("font-size: 14px; letter-spacing: 1px;")
        inner.addWidget(self._label)

        self._refresh()

    def get_modifier(self) -> str:
        return self._modifier

    def get_key(self) -> str:
        return self._key

    def _binding_text(self) -> str:
        sym = self._MOD_DISPLAY.get(self._modifier, self._modifier.capitalize())
        key = self._key.upper() if len(self._key) == 1 else self._key.capitalize()
        return f"{sym}  {key}".strip() if sym else key

    def _refresh(self):
        if self._recording:
            self._label.setText("Press shortcut…")
            self.setStyleSheet(self._STYLE_RECORDING)
        else:
            self._label.setText(self._binding_text())
            self.setStyleSheet(self._STYLE_IDLE)

    def mousePressEvent(self, a0):  # type: ignore[override]
        if not self._recording:
            self._recording = True
            self._refresh()
            self.grabKeyboard()
        super().mousePressEvent(a0)

    def keyPressEvent(self, a0):  # type: ignore[override]
        if not self._recording or a0 is None:
            return

        key_int = int(a0.key())

        if key_int == int(Qt.Key.Key_Escape):
            self._cancel()
            return

        # Bare modifier press — show partial feedback and keep waiting
        if key_int in self._MODIFIER_KEY_CODES:
            mods = a0.modifiers()
            for flag, name in self._MOD_PRIORITY:
                if mods & flag:
                    self._label.setText(
                        f"{self._MOD_DISPLAY.get(name, name)}  …"
                    )
                    break
            return

        config_key = self._QT_TO_CONFIG.get(key_int)
        if config_key is None:
            return  # unsupported key — ignore

        mods = a0.modifiers()
        primary_mod: str | None = None
        for flag, name in self._MOD_PRIORITY:
            if mods & flag:
                primary_mod = name
                break

        # Letters and digits require a modifier; F-keys and special keys don't
        if primary_mod is None:
            if key_int not in self._BARE_KEY_CODES:
                self._label.setText("Hold a modifier key…")
                return
            primary_mod = "none"

        self._modifier = primary_mod
        self._key = config_key
        self._commit()

    def focusOutEvent(self, a0):  # type: ignore[override]
        if self._recording:
            self._cancel()
        super().focusOutEvent(a0)

    def _cancel(self):
        self._recording = False
        self.releaseKeyboard()
        self._refresh()

    def _commit(self):
        self._recording = False
        self.releaseKeyboard()
        self._refresh()
        self.binding_changed.emit(self._modifier, self._key)


def _build_qt_key_map() -> dict[int, str]:
    """Build the Qt key-code → config key-string map for HotkeyRecorder."""
    m: dict[int, str] = {
        int(Qt.Key.Key_Space): "space",
        int(Qt.Key.Key_Tab): "tab",
        int(Qt.Key.Key_Return): "enter",
        int(Qt.Key.Key_Enter): "enter",
        int(Qt.Key.Key_Backspace): "backspace",
        int(Qt.Key.Key_F1): "f1",   int(Qt.Key.Key_F2): "f2",
        int(Qt.Key.Key_F3): "f3",   int(Qt.Key.Key_F4): "f4",
        int(Qt.Key.Key_F5): "f5",   int(Qt.Key.Key_F6): "f6",
        int(Qt.Key.Key_F7): "f7",   int(Qt.Key.Key_F8): "f8",
        int(Qt.Key.Key_F9): "f9",   int(Qt.Key.Key_F10): "f10",
        int(Qt.Key.Key_F11): "f11", int(Qt.Key.Key_F12): "f12",
    }
    for c in range(ord("A"), ord("Z") + 1):
        m[c] = chr(c).lower()
    for c in range(ord("0"), ord("9") + 1):
        m[c] = chr(c)
    return m


HotkeyRecorder._QT_TO_CONFIG = _build_qt_key_map()


def _page_header(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet("font-size: 15px; font-weight: bold; margin-bottom: 4px;")
    return lbl


class SettingsWindow(QWidget):
    """Overlay settings with sliders, color pickers, and live preview."""

    settings_changed = pyqtSignal()
    hotkey_changed = pyqtSignal()

    _NAV_BTN_BASE = (
        "QPushButton {"
        "  text-align: left;"
        "  padding: 10px 16px;"
        "  border: none;"
        "  border-radius: 0;"
        "  background: transparent;"
        "  font-size: 13px;"
        "}"
        "QPushButton:hover { background: rgba(255,255,255,0.06); }"
    )
    _NAV_BTN_ACTIVE = (
        "QPushButton {"
        "  text-align: left;"
        "  padding: 10px 16px 10px 12px;"
        "  border: none;"
        "  border-left: 4px solid #FF6B6B;"
        "  border-radius: 0;"
        "  background: rgba(255,107,107,0.10);"
        "  font-size: 13px;"
        "  font-weight: bold;"
        "}"
    )

    def __init__(self, config: AppConfig, parent=None):
        super().__init__(parent)
        self._config = config

        # ── Color / gradient state ────────────────────────────────────────
        self._color = QColor(config.overlay.color)
        self._bg_color = QColor(config.overlay.bg_color)
        grad_colors = config.overlay.gradient_colors
        self._grad_start = QColor(grad_colors[0]) if grad_colors else QColor("#FF6B6B")
        self._grad_end = QColor(grad_colors[-1]) if grad_colors else QColor("#8BE9FD")
        self._grad_mid = (
            QColor(grad_colors[len(grad_colors) // 2])
            if len(grad_colors) >= 3
            else None
        )
        self._gradient_colors_raw = list(grad_colors)
        self._pulse_color = QColor(config.overlay.pulse_color)

        # Track whether we're programmatically updating controls
        self._updating = False

        self.setWindowTitle("TinyWhisper Advanced Settings")
        self.setFixedWidth(640)
        self.setWindowFlags(
            Qt.WindowType.Window | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setStyleSheet("""
            QComboBox, QSpinBox { padding: 4px 8px; }
            QPlainTextEdit { padding: 6px; }
            QLineEdit { padding: 4px 8px; }
        """)

        # ── Root layout: body row + footer ────────────────────────────────
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)

        # Nav sidebar
        self._nav_buttons: list[QPushButton] = []
        nav_widget = self._build_nav()
        body.addWidget(nav_widget)

        # Stacked pages
        self._stack = QStackedWidget()
        self._stack.addWidget(self._build_keybindings_page(config))
        self._stack.addWidget(self._build_overlay_page(config))
        self._stack.addWidget(self._build_recording_page(config))
        self._stack.addWidget(self._build_tidier_page(config))
        body.addWidget(self._stack, 1)

        root.addLayout(body, 1)

        # ── Footer ────────────────────────────────────────────────────────
        footer_widget = QWidget()
        footer_widget.setStyleSheet("border-top: 1px solid rgba(255,255,255,0.10);")
        footer = QHBoxLayout(footer_widget)
        footer.setContentsMargins(16, 12, 16, 16)
        footer.addStretch()
        save_btn = QPushButton("Save && Apply")
        save_btn.setFixedWidth(120)
        save_btn.setStyleSheet(
            "QPushButton {"
            "  background: #0A84FF;"
            "  color: white;"
            "  border: none;"
            "  border-radius: 6px;"
            "  padding: 7px 18px;"
            "  font-size: 13px;"
            "  font-weight: 600;"
            "}"
            "QPushButton:hover { background: #409CFF; }"
            "QPushButton:pressed { background: #0060D0; }"
        )
        save_btn.clicked.connect(self._save)
        footer.addWidget(save_btn)
        root.addWidget(footer_widget)

        # Default to Overlay page
        self._nav_select(1)

        self._on_tidier_toggled(config.tidier.enabled)

    # ── Nav ───────────────────────────────────────────────────────────────

    def _build_nav(self) -> QWidget:
        nav = QWidget()
        nav.setFixedWidth(180)
        nav.setStyleSheet("background: rgba(0,0,0,0.18);")
        layout = QVBoxLayout(nav)
        layout.setContentsMargins(0, 16, 0, 16)
        layout.setSpacing(0)

        sections = ["Keybindings", "Overlay", "Recording", "Tidier"]
        for i, name in enumerate(sections):
            btn = QPushButton(name)
            btn.setStyleSheet(self._NAV_BTN_BASE)
            idx = i
            btn.clicked.connect(lambda checked, n=idx: self._nav_select(n))
            layout.addWidget(btn)
            self._nav_buttons.append(btn)

        layout.addStretch()
        return nav

    def _nav_select(self, index: int) -> None:
        self._stack.setCurrentIndex(index)
        for i, btn in enumerate(self._nav_buttons):
            btn.setStyleSheet(
                self._NAV_BTN_ACTIVE if i == index else self._NAV_BTN_BASE
            )

    # ── Page builders ─────────────────────────────────────────────────────

    def _build_keybindings_page(self, config: AppConfig) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(8)

        layout.addWidget(_page_header("Keybindings"))

        layout.addWidget(QLabel("Toggle recording hotkey"))
        self._hotkey_recorder = HotkeyRecorder(
            config.hotkey.modifier,
            config.hotkey.key,
        )
        layout.addWidget(self._hotkey_recorder)

        hint = QLabel("Click to record a new shortcut. Hold a modifier (⌘ ⌥ ⌃ ⇧) then press any key.")
        hint.setStyleSheet("color: #888; font-size: 11px;")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        layout.addStretch()
        return page

    def _build_overlay_page(self, config: AppConfig) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)

        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(6)

        layout.addWidget(_page_header("Overlay"))

        # Theme selector
        theme_row = QHBoxLayout()
        theme_row.addWidget(QLabel("Theme"))
        self._theme_combo = QComboBox()
        self._theme_combo.addItem("Custom")
        for key in THEME_ORDER:
            self._theme_combo.addItem(THEMES[key].label, key)
        current_theme = config.overlay.theme
        if current_theme and current_theme in THEMES:
            idx = THEME_ORDER.index(current_theme) + 1  # +1 for "Custom"
            self._theme_combo.setCurrentIndex(idx)
        else:
            self._theme_combo.setCurrentIndex(0)
        self._theme_combo.currentIndexChanged.connect(self._on_theme_changed)
        theme_row.addWidget(self._theme_combo, 1)
        layout.addLayout(theme_row)

        # Position selector
        pos_row = QHBoxLayout()
        pos_row.addWidget(QLabel("Position"))
        self._position_combo = QComboBox()
        self._position_combo.addItem("Top Center", "top-center")
        self._position_combo.addItem("Follow Active Monitor", "follow")
        current_pos = config.overlay.position
        for i in range(self._position_combo.count()):
            if self._position_combo.itemData(i) == current_pos:
                self._position_combo.setCurrentIndex(i)
                break
        pos_row.addWidget(self._position_combo, 1)
        layout.addLayout(pos_row)

        layout.addSpacing(4)

        # Live preview
        self._preview = WaveformPreview()
        self._preview.setFixedHeight(60)
        self._preview.set_opacity(config.overlay.opacity)
        self._preview.set_color(self._color)
        self._preview.set_bg_color(self._bg_color)
        self._preview.set_gradient(
            config.overlay.gradient,
            [QColor(c) for c in config.overlay.gradient_colors]
            if config.overlay.gradient_colors else None,
        )
        layout.addWidget(self._preview)

        layout.addSpacing(4)

        # Opacity slider
        layout.addWidget(QLabel("Opacity"))
        opacity_row = QHBoxLayout()
        self._opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self._opacity_slider.setRange(10, 100)
        self._opacity_slider.setValue(int(config.overlay.opacity * 100))
        self._opacity_label = QLabel(f"{int(config.overlay.opacity * 100)}%")
        self._opacity_label.setFixedWidth(40)
        self._opacity_slider.valueChanged.connect(self._on_opacity_changed)
        opacity_row.addWidget(self._opacity_slider)
        opacity_row.addWidget(self._opacity_label)
        layout.addLayout(opacity_row)

        # Width / Height
        wh_row = QHBoxLayout()
        wh_row.setSpacing(12)
        w_col = QVBoxLayout()
        w_col.addWidget(QLabel("Width"))
        self._width_spin = QSpinBox()
        self._width_spin.setRange(100, 99999)
        self._width_spin.setValue(config.overlay.width)
        w_col.addWidget(self._width_spin)
        wh_row.addLayout(w_col)
        h_col = QVBoxLayout()
        h_col.addWidget(QLabel("Height"))
        self._height_spin = QSpinBox()
        self._height_spin.setRange(30, 99999)
        self._height_spin.setValue(config.overlay.height)
        h_col.addWidget(self._height_spin)
        wh_row.addLayout(h_col)
        wh_row.addStretch()
        layout.addLayout(wh_row)

        # Waveform color picker
        wave_color_row = QHBoxLayout()
        wave_color_row.addWidget(QLabel("Bar Color"))
        self._color_btn = _make_color_btn(self._color, self._pick_color)
        wave_color_row.addWidget(self._color_btn)
        wave_color_row.addStretch()
        layout.addLayout(wave_color_row)

        # Background color picker
        bg_color_row = QHBoxLayout()
        bg_color_row.addWidget(QLabel("Background Color"))
        self._bg_color_btn = _make_color_btn(self._bg_color, self._pick_bg_color)
        bg_color_row.addWidget(self._bg_color_btn)
        bg_color_row.addStretch()
        layout.addLayout(bg_color_row)

        # ── Gradient ─────────────────────────────────────────────────────
        grad_row = QHBoxLayout()
        grad_row.addWidget(QLabel("Bar Gradient"))
        self._grad_check = QCheckBox()
        self._grad_check.setChecked(config.overlay.gradient)
        self._grad_check.toggled.connect(self._on_gradient_toggled)
        grad_row.addStretch()
        grad_row.addWidget(self._grad_check)
        layout.addLayout(grad_row)

        # Gradient color pickers (start / end)
        self._grad_colors_row = QHBoxLayout()
        self._grad_colors_row.addWidget(QLabel("Start"))
        self._grad_start_btn = _make_color_btn(self._grad_start, self._pick_grad_start)
        self._grad_colors_row.addWidget(self._grad_start_btn)
        self._grad_colors_row.addSpacing(8)
        self._grad_colors_row.addWidget(QLabel("End"))
        self._grad_end_btn = _make_color_btn(self._grad_end, self._pick_grad_end)
        self._grad_colors_row.addWidget(self._grad_end_btn)
        self._grad_colors_row.addStretch()

        self._grad_colors_widget = QWidget()
        self._grad_colors_widget.setLayout(self._grad_colors_row)
        self._grad_colors_widget.setVisible(config.overlay.gradient)
        layout.addWidget(self._grad_colors_widget)

        # ── Pulse ────────────────────────────────────────────────────────
        pulse_row = QHBoxLayout()
        pulse_row.addWidget(QLabel("Background Pulse"))
        self._pulse_check = QCheckBox()
        self._pulse_check.setChecked(config.overlay.pulse)
        pulse_row.addStretch()
        self._pulse_color_btn = _make_color_btn(self._pulse_color, self._pick_pulse_color)
        pulse_row.addWidget(self._pulse_color_btn)
        pulse_row.addWidget(self._pulse_check)
        layout.addLayout(pulse_row)

        # Pulse opacity slider
        pulse_opacity_row = QHBoxLayout()
        pulse_opacity_row.addWidget(QLabel("Pulse Intensity"))
        self._pulse_opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self._pulse_opacity_slider.setRange(0, 100)
        self._pulse_opacity_slider.setValue(int(config.overlay.pulse_opacity * 100))
        self._pulse_opacity_label = QLabel(f"{int(config.overlay.pulse_opacity * 100)}%")
        self._pulse_opacity_label.setFixedWidth(40)
        self._pulse_opacity_slider.valueChanged.connect(self._on_pulse_opacity_changed)
        pulse_opacity_row.addWidget(self._pulse_opacity_slider)
        pulse_opacity_row.addWidget(self._pulse_opacity_label)
        layout.addLayout(pulse_opacity_row)

        # Waveform style
        style_row = QHBoxLayout()
        style_row.addWidget(QLabel("Waveform Style"))
        self._style_combo = QComboBox()
        self._style_combo.addItem("Bars", WaveformStyle.BARS)
        self._style_combo.addItem("Braille Dots", WaveformStyle.BRAILLE)
        current_style = config.overlay.waveform_style
        for i in range(self._style_combo.count()):
            if self._style_combo.itemData(i) is current_style:
                self._style_combo.setCurrentIndex(i)
                break
        self._style_combo.currentIndexChanged.connect(self._on_style_changed)
        style_row.addWidget(self._style_combo, 1)
        layout.addLayout(style_row)
        self._preview.set_braille(current_style is WaveformStyle.BRAILLE)

        layout.addStretch()
        scroll.setWidget(inner)
        return scroll

    def _build_recording_page(self, config: AppConfig) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(6)

        layout.addWidget(_page_header("Recording"))

        # Input device selector
        layout.addWidget(QLabel("Input Device"))
        self._device_combo_rec = QComboBox()
        self._device_combo_rec.addItem("System Default", None)
        current_device = config.recording.device
        selected = 0
        for dev in _list_input_devices():
            self._device_combo_rec.addItem(dev["name"], dev["name"])
            if current_device and current_device.lower() in dev["name"].lower():
                selected = self._device_combo_rec.count() - 1
        self._device_combo_rec.setCurrentIndex(selected)
        layout.addWidget(self._device_combo_rec)

        device_hint = QLabel(
            "Use System Default to follow macOS routing (recommended). "
            "Select a specific device to override."
        )
        device_hint.setWordWrap(True)
        device_hint.setStyleSheet("color: #888; font-size: 11px;")
        layout.addWidget(device_hint)

        layout.addSpacing(8)

        # Sample rate
        layout.addWidget(QLabel("Sample Rate"))
        self._sample_rate_spin = QSpinBox()
        self._sample_rate_spin.setRange(8000, 48000)
        self._sample_rate_spin.setSingleStep(8000)
        self._sample_rate_spin.setSuffix(" Hz")
        self._sample_rate_spin.setValue(config.recording.sample_rate)
        layout.addWidget(self._sample_rate_spin)

        rate_hint = QLabel(
            "16000 Hz required for Parakeet. Only change if you know what you're doing."
        )
        rate_hint.setWordWrap(True)
        rate_hint.setStyleSheet("color: #888; font-size: 11px;")
        layout.addWidget(rate_hint)

        layout.addStretch()
        return page

    def _build_tidier_page(self, config: AppConfig) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(6)

        layout.addWidget(_page_header("Tidier"))

        tidier_enable_row = QHBoxLayout()
        tidier_enable_row.addWidget(QLabel("Enable LLM cleanup"))
        self._tidier_enabled = QCheckBox()
        self._tidier_enabled.setChecked(config.tidier.enabled)
        self._tidier_enabled.toggled.connect(self._on_tidier_toggled)
        tidier_enable_row.addStretch()
        tidier_enable_row.addWidget(self._tidier_enabled)
        layout.addLayout(tidier_enable_row)

        layout.addWidget(QLabel("Model"))
        self._tidier_model_combo = QComboBox()
        self._tidier_model_combo.setEditable(True)
        tidier_models = [
            "mlx-community/Qwen3-1.7B-4bit",
            "mlx-community/Qwen2.5-1.5B-Instruct-4bit",
            "mlx-community/Qwen2.5-0.5B-Instruct-4bit",
            "mlx-community/Llama-3.2-1B-Instruct-4bit",
        ]
        self._tidier_model_combo.addItems(tidier_models)
        current_model = config.tidier.model
        if current_model in tidier_models:
            self._tidier_model_combo.setCurrentText(current_model)
        else:
            self._tidier_model_combo.insertItem(0, current_model)
            self._tidier_model_combo.setCurrentIndex(0)
        layout.addWidget(self._tidier_model_combo)

        # ── Prompt mode toggle ───────────────────────────────────────────
        mode_row = QHBoxLayout()
        self._prompt_mode_text = QRadioButton("Text")
        self._prompt_mode_script = QRadioButton("Script")
        self._prompt_mode_group = QButtonGroup(self)
        self._prompt_mode_group.addButton(self._prompt_mode_text, 0)
        self._prompt_mode_group.addButton(self._prompt_mode_script, 1)
        use_script = bool(config.tidier.prompt_script)
        self._prompt_mode_text.setChecked(not use_script)
        self._prompt_mode_script.setChecked(use_script)
        mode_row.addWidget(QLabel("Prompt mode"))
        mode_row.addStretch()
        mode_row.addWidget(self._prompt_mode_text)
        mode_row.addWidget(self._prompt_mode_script)
        layout.addLayout(mode_row)

        # Stacked widget — page 0 = text, page 1 = script
        self._prompt_stack = QStackedWidget()

        # Page 0: text prompt
        text_page = QWidget()
        text_layout = QVBoxLayout(text_page)
        text_layout.setContentsMargins(0, 0, 0, 0)
        self._tidier_prompt = QPlainTextEdit()
        self._tidier_prompt.setFixedHeight(72)
        self._tidier_prompt.setPlainText(config.tidier.prompt)
        self._tidier_prompt.setPlaceholderText(
            "Fix capitalization and punctuation, remove filler words. "
            "Return only the cleaned text."
        )
        text_layout.addWidget(self._tidier_prompt)
        text_hint = QLabel("Leave blank to use the built-in default prompt.")
        text_hint.setStyleSheet("color: #888; font-size: 11px;")
        text_layout.addWidget(text_hint)
        self._prompt_stack.addWidget(text_page)

        # Page 1: script
        script_page = QWidget()
        script_layout = QVBoxLayout(script_page)
        script_layout.setContentsMargins(0, 0, 0, 0)
        script_path_row = QHBoxLayout()
        self._tidier_script = QLineEdit()
        self._tidier_script.setText(config.tidier.prompt_script)
        self._tidier_script.setPlaceholderText(
            "~/.config/tinywhisper/scripts/my-script.sh"
        )
        script_path_row.addWidget(self._tidier_script)
        self._browse_script_btn = QPushButton("Browse…")
        self._browse_script_btn.setFixedWidth(72)
        self._browse_script_btn.clicked.connect(self._browse_script)
        script_path_row.addWidget(self._browse_script_btn)
        script_layout.addLayout(script_path_row)
        script_hint = QLabel(
            "The script receives the transcription via <b>$TW_TEXT</b> and "
            "must print the LLM system prompt to stdout. "
            "Supported: <b>.sh</b> (bash), <b>.py</b> (python3), <b>.js</b> (node). "
            "Exit non-zero or print nothing to fall back to the built-in default."
        )
        script_hint.setWordWrap(True)
        script_hint.setStyleSheet("color: #888; font-size: 11px;")
        script_layout.addWidget(script_hint)
        scripts_row = QHBoxLayout()
        self._view_scripts_btn = QPushButton("View Scripts Folder")
        self._view_scripts_btn.clicked.connect(self._open_scripts_folder)
        scripts_row.addWidget(self._view_scripts_btn)
        scripts_row.addStretch()
        script_layout.addLayout(scripts_row)
        self._prompt_stack.addWidget(script_page)

        self._prompt_stack.setCurrentIndex(1 if use_script else 0)
        layout.addWidget(self._prompt_stack)

        self._prompt_mode_group.idToggled.connect(self._on_prompt_mode_toggled)

        layout.addStretch()
        return page

    # ── Theme handling ────────────────────────────────────────────────────

    def _on_theme_changed(self, index: int):
        if self._updating:
            return
        if index == 0:
            # "Custom" selected — keep current values
            return
        theme_key = self._theme_combo.itemData(index)
        if theme_key is None or theme_key not in THEMES:
            return
        theme = THEMES[theme_key]

        self._updating = True

        # Apply theme values to controls
        self._color = QColor(theme.color)
        self._bg_color = QColor(theme.bg_color)
        self._update_color_btn()
        self._update_bg_color_btn()
        self._preview.set_color(self._color)
        self._preview.set_bg_color(self._bg_color)

        # Opacity
        self._opacity_slider.setValue(int(theme.opacity * 100))

        # Gradient
        has_gradient = len(theme.gradient_colors) >= 2
        self._grad_check.setChecked(has_gradient)
        if has_gradient:
            self._grad_start = QColor(theme.gradient_colors[0])
            self._grad_end = QColor(theme.gradient_colors[-1])
            self._gradient_colors_raw = list(theme.gradient_colors)
            self._grad_start_btn.setStyleSheet(
                _COLOR_BTN_STYLE.format(hex=self._grad_start.name())
            )
            self._grad_end_btn.setStyleSheet(
                _COLOR_BTN_STYLE.format(hex=self._grad_end.name())
            )
            gc = [QColor(c) for c in theme.gradient_colors]
            self._preview.set_gradient(True, gc)
        else:
            self._gradient_colors_raw = []
            self._preview.set_gradient(False)

        self._grad_colors_widget.setVisible(has_gradient)

        self._updating = False

    def _mark_custom(self):
        """Switch the theme dropdown to Custom when the user manually edits a value."""
        if not self._updating:
            self._updating = True
            self._theme_combo.setCurrentIndex(0)
            self._updating = False

    # ── Tidier ────────────────────────────────────────────────────────────

    def _on_prompt_mode_toggled(self, btn_id: int, checked: bool):
        if checked:
            self._prompt_stack.setCurrentIndex(btn_id)

    def _browse_script(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Prompt Script",
            str(Path.home() / ".config" / "tinywhisper" / "scripts"),
            "Scripts (*.sh *.py *.js);;All Files (*)",
        )
        if path:
            self._tidier_script.setText(path)

    def _on_tidier_toggled(self, enabled: bool):
        self._tidier_model_combo.setEnabled(enabled)
        self._prompt_mode_text.setEnabled(enabled)
        self._prompt_mode_script.setEnabled(enabled)
        self._prompt_stack.setEnabled(enabled)

    def _open_scripts_folder(self):
        import subprocess
        from tinywhisper.config import SCRIPTS_DIR
        SCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
        _seed_example_scripts(SCRIPTS_DIR)
        subprocess.Popen(["open", str(SCRIPTS_DIR)])

    # ── Overlay callbacks ─────────────────────────────────────────────────

    def showEvent(self, a0):  # type: ignore[override]
        super().showEvent(a0)
        self._preview.reset()
        self._preview.start()

    def hideEvent(self, a0):  # type: ignore[override]
        super().hideEvent(a0)
        self._preview.stop()

    def _on_style_changed(self, index: int):
        style = self._style_combo.itemData(index)
        self._preview.set_braille(style is WaveformStyle.BRAILLE)
        self._mark_custom()

    def _on_opacity_changed(self, value: int):
        self._opacity_label.setText(f"{value}%")
        self._preview.set_opacity(value / 100.0)
        self._mark_custom()

    def _update_color_btn(self):
        self._color_btn.setStyleSheet(
            _COLOR_BTN_STYLE.format(hex=self._color.name())
        )

    def _update_bg_color_btn(self):
        self._bg_color_btn.setStyleSheet(
            _COLOR_BTN_STYLE.format(hex=self._bg_color.name())
        )

    def _pick_color(self):
        color = QColorDialog.getColor(self._color, self, "Bar Color")
        if color.isValid():
            self._color = color
            self._update_color_btn()
            self._preview.set_color(color)
            self._mark_custom()

    def _pick_bg_color(self):
        color = QColorDialog.getColor(self._bg_color, self, "Background Color")
        if color.isValid():
            self._bg_color = color
            self._update_bg_color_btn()
            self._preview.set_bg_color(color)
            self._mark_custom()

    # ── Gradient callbacks ────────────────────────────────────────────────

    def _pick_pulse_color(self):
        color = QColorDialog.getColor(self._pulse_color, self, "Pulse Glow Color")
        if color.isValid():
            self._pulse_color = color
            self._pulse_color_btn.setStyleSheet(
                _COLOR_BTN_STYLE.format(hex=color.name())
            )

    def _on_pulse_opacity_changed(self, value: int):
        self._pulse_opacity_label.setText(f"{value}%")

    def _on_gradient_toggled(self, checked: bool):
        self._grad_colors_widget.setVisible(checked)
        if checked:
            gc = self._current_gradient_qcolors()
            self._preview.set_gradient(True, gc)
        else:
            self._preview.set_gradient(False)
        self._mark_custom()

    def _current_gradient_qcolors(self) -> list[QColor]:
        """Build the QColor list from current gradient state."""
        if self._gradient_colors_raw and len(self._gradient_colors_raw) >= 2:
            return [QColor(c) for c in self._gradient_colors_raw]
        return [QColor(self._grad_start), QColor(self._grad_end)]

    def _pick_grad_start(self):
        color = QColorDialog.getColor(self._grad_start, self, "Gradient Start")
        if color.isValid():
            self._grad_start = color
            self._grad_start_btn.setStyleSheet(
                _COLOR_BTN_STYLE.format(hex=color.name())
            )
            # Reset raw list to 2-stop when user manually picks
            self._gradient_colors_raw = [self._grad_start.name(), self._grad_end.name()]
            self._preview.set_gradient(True, self._current_gradient_qcolors())
            self._mark_custom()

    def _pick_grad_end(self):
        color = QColorDialog.getColor(self._grad_end, self, "Gradient End")
        if color.isValid():
            self._grad_end = color
            self._grad_end_btn.setStyleSheet(
                _COLOR_BTN_STYLE.format(hex=color.name())
            )
            self._gradient_colors_raw = [self._grad_start.name(), self._grad_end.name()]
            self._preview.set_gradient(True, self._current_gradient_qcolors())
            self._mark_custom()

    # ── Save ──────────────────────────────────────────────────────────────

    def _save(self):
        # Hotkey
        old_mod = self._config.hotkey.modifier
        old_key = self._config.hotkey.key
        self._config.hotkey.modifier = self._hotkey_recorder.get_modifier()
        self._config.hotkey.key = self._hotkey_recorder.get_key()
        hotkey_changed = (
            self._config.hotkey.modifier != old_mod
            or self._config.hotkey.key != old_key
        )

        # Overlay
        self._config.overlay.position = self._position_combo.currentData()
        self._config.overlay.opacity = self._opacity_slider.value() / 100.0
        self._config.overlay.width = self._width_spin.value()
        self._config.overlay.height = self._height_spin.value()
        self._config.overlay.color = self._color.name()
        self._config.overlay.bg_color = self._bg_color.name()

        # Theme
        idx = self._theme_combo.currentIndex()
        if idx > 0:
            self._config.overlay.theme = self._theme_combo.itemData(idx) or ""
        else:
            self._config.overlay.theme = ""

        # Waveform style
        self._config.overlay.waveform_style = self._style_combo.currentData()

        # Pulse
        self._config.overlay.pulse = self._pulse_check.isChecked()
        self._config.overlay.pulse_color = self._pulse_color.name()
        self._config.overlay.pulse_opacity = self._pulse_opacity_slider.value() / 100.0

        # Gradient
        self._config.overlay.gradient = self._grad_check.isChecked()
        if self._config.overlay.gradient:
            if self._gradient_colors_raw and len(self._gradient_colors_raw) >= 2:
                self._config.overlay.gradient_colors = list(self._gradient_colors_raw)
            else:
                self._config.overlay.gradient_colors = [
                    self._grad_start.name(),
                    self._grad_end.name(),
                ]
        else:
            self._config.overlay.gradient_colors = []

        # Recording
        self._config.recording.device = self._device_combo_rec.currentData()
        self._config.recording.sample_rate = self._sample_rate_spin.value()

        # Tidier
        self._config.tidier.enabled = self._tidier_enabled.isChecked()
        self._config.tidier.model = self._tidier_model_combo.currentText().strip()
        if self._prompt_mode_text.isChecked():
            self._config.tidier.prompt = self._tidier_prompt.toPlainText().strip()
            self._config.tidier.prompt_script = ""
        else:
            self._config.tidier.prompt = ""
            self._config.tidier.prompt_script = self._tidier_script.text().strip()

        # Write config to disk
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        data = {
            "hotkey": {
                "modifier": self._config.hotkey.modifier,
                "key": self._config.hotkey.key,
            },
            "transcription": {
                "engine": self._config.transcription.engine,
                "parakeet": {"model": self._config.transcription.parakeet.model},
                "whisper": {"model": self._config.transcription.whisper.model},
            },
            "recording": {
                "device": self._config.recording.device,
                "sample_rate": self._config.recording.sample_rate,
                "channels": self._config.recording.channels,
            },
            "overlay": {
                "enabled": self._config.overlay.enabled,
                "width": self._config.overlay.width,
                "height": self._config.overlay.height,
                "position": self._config.overlay.position,
                "opacity": self._config.overlay.opacity,
                "color": self._config.overlay.color,
                "bg_color": self._config.overlay.bg_color,
                "theme": self._config.overlay.theme,
                "gradient": self._config.overlay.gradient,
                "gradient_colors": self._config.overlay.gradient_colors,
                "pulse": self._config.overlay.pulse,
                "pulse_color": self._config.overlay.pulse_color,
                "pulse_opacity": self._config.overlay.pulse_opacity,
                "waveform_style": self._config.overlay.waveform_style.value,
            },
            "tidier": {
                "enabled": self._config.tidier.enabled,
                "model": self._config.tidier.model,
                "prompt": self._config.tidier.prompt,
                "prompt_script": self._config.tidier.prompt_script,
                "max_tokens": self._config.tidier.max_tokens,
            },
        }
        with open(CONFIG_PATH, "w") as f:
            yaml.dump(data, f, default_flow_style=False)

        self.settings_changed.emit()
        if hotkey_changed:
            self.hotkey_changed.emit()
        self.hide()
