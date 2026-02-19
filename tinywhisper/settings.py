"""Settings window for overlay appearance with live preview."""

import math
import random

from PyQt6.QtCore import Qt, QRectF, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QLinearGradient, QPainter, QPen
from PyQt6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from tinywhisper.config import AppConfig, CONFIG_DIR, CONFIG_PATH
from tinywhisper.overlay import gradient_color_at
from tinywhisper.themes import THEMES, THEME_ORDER

import yaml


class WaveformPreview(QWidget):
    """Animated waveform preview that reflects current settings."""

    MAX_BARS = 60

    def __init__(self, parent=None):
        super().__init__(parent)
        self._opacity = 0.85
        self._color = QColor("#FF6B6B")
        self._bg_color = QColor("#1E1E1E")
        self._gradient = False
        self._gradient_colors: list[QColor] = []
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

        # Bars
        bar_w = max(3, (w - 24) // self.MAX_BARS - 1)
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


class SettingsWindow(QWidget):
    """Overlay settings with sliders, color pickers, and live preview."""

    settings_changed = pyqtSignal()
    hotkey_changed = pyqtSignal()

    MODIFIERS = ["Option", "Ctrl", "Cmd", "Shift"]
    KEYS = ["Space", "Tab", "Enter", "F1", "F2", "F3", "F4", "F5",
            "F6", "F7", "F8", "F9", "F10", "F11", "F12"]

    def __init__(self, config: AppConfig, parent=None):
        super().__init__(parent)
        self._config = config
        self._color = QColor(config.overlay.color)
        self._bg_color = QColor(config.overlay.bg_color)

        # Gradient state
        grad_colors = config.overlay.gradient_colors
        self._grad_start = QColor(grad_colors[0]) if grad_colors else QColor("#FF6B6B")
        self._grad_end = QColor(grad_colors[-1]) if grad_colors else QColor("#8BE9FD")
        self._grad_mid = (
            QColor(grad_colors[len(grad_colors) // 2])
            if len(grad_colors) >= 3
            else None
        )
        self._gradient_colors_raw = list(grad_colors)  # keep full list from themes

        self.setWindowTitle("TinyWhisper Advanced Settings")
        self.setFixedSize(420, 820)
        self.setWindowFlags(
            Qt.WindowType.Window | Qt.WindowType.WindowStaysOnTopHint
        )

        self.setStyleSheet("""
            QComboBox, QSpinBox { padding: 4px 8px; }
            QPlainTextEdit { padding: 6px; }
            QLineEdit { padding: 4px 8px; }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(6)

        # ── Hotkey ───────────────────────────────────────────────────────────
        hk_header = QLabel("Hotkey")
        hk_header.setStyleSheet("font-weight: bold;")
        layout.addWidget(hk_header)
        hotkey_row = QHBoxLayout()
        self._mod_combo = QComboBox()
        self._mod_combo.addItems(self.MODIFIERS)
        self._mod_combo.setCurrentText(config.hotkey.modifier.capitalize())
        hotkey_row.addWidget(self._mod_combo)
        hotkey_row.addWidget(QLabel("+"))
        self._key_combo = QComboBox()
        self._key_combo.addItems(self.KEYS)
        self._key_combo.setCurrentText(config.hotkey.key.capitalize())
        hotkey_row.addWidget(self._key_combo)
        hotkey_row.addStretch()
        layout.addLayout(hotkey_row)

        layout.addSpacing(12)

        # ── Overlay ──────────────────────────────────────────────────────────
        ov_header = QLabel("Overlay")
        ov_header.setStyleSheet("font-weight: bold;")
        layout.addWidget(ov_header)

        # Theme selector
        theme_row = QHBoxLayout()
        theme_row.addWidget(QLabel("Theme"))
        self._theme_combo = QComboBox()
        self._theme_combo.addItem("Custom")
        for key in THEME_ORDER:
            self._theme_combo.addItem(THEMES[key].label, key)
        # Set current theme
        current_theme = config.overlay.theme
        if current_theme and current_theme in THEMES:
            idx = THEME_ORDER.index(current_theme) + 1  # +1 for "Custom"
            self._theme_combo.setCurrentIndex(idx)
        else:
            self._theme_combo.setCurrentIndex(0)
        self._theme_combo.currentIndexChanged.connect(self._on_theme_changed)
        theme_row.addWidget(self._theme_combo, 1)
        layout.addLayout(theme_row)

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

        # ── Gradient ─────────────────────────────────────────────────────────
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

        # Wrap in a widget so we can show/hide it
        self._grad_colors_widget = QWidget()
        self._grad_colors_widget.setLayout(self._grad_colors_row)
        self._grad_colors_widget.setVisible(config.overlay.gradient)
        layout.addWidget(self._grad_colors_widget)

        # ── Pulse ────────────────────────────────────────────────────────────
        pulse_row = QHBoxLayout()
        pulse_row.addWidget(QLabel("Background Pulse"))
        self._pulse_check = QCheckBox()
        self._pulse_check.setChecked(config.overlay.pulse)
        pulse_row.addStretch()
        self._pulse_color = QColor(config.overlay.pulse_color)
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

        # ── Tidier ──────────────────────────────────────────────────────────
        layout.addSpacing(12)
        tidier_header = QLabel("Tidier")
        tidier_header.setStyleSheet("font-weight: bold;")
        layout.addWidget(tidier_header)

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

        layout.addWidget(QLabel("Prompt (leave blank for default)"))
        self._tidier_prompt = QPlainTextEdit()
        self._tidier_prompt.setFixedHeight(72)
        self._tidier_prompt.setPlainText(config.tidier.prompt)
        self._tidier_prompt.setPlaceholderText(
            "Fix capitalization and punctuation, remove filler words. "
            "Return only the cleaned text."
        )
        layout.addWidget(self._tidier_prompt)

        self._on_tidier_toggled(config.tidier.enabled)

        # Save button
        save_btn = QPushButton("Save && Apply")
        save_btn.clicked.connect(self._save)
        layout.addWidget(save_btn)

        # Track whether we're programmatically updating controls
        self._updating = False

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

    def _on_tidier_toggled(self, enabled: bool):
        self._tidier_model_combo.setEnabled(enabled)
        self._tidier_prompt.setEnabled(enabled)

    # ── Overlay callbacks ─────────────────────────────────────────────────

    def showEvent(self, a0):  # type: ignore[override]
        super().showEvent(a0)
        self._preview.reset()
        self._preview.start()

    def hideEvent(self, a0):  # type: ignore[override]
        super().hideEvent(a0)
        self._preview.stop()

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
        self._config.hotkey.modifier = self._mod_combo.currentText().lower()
        self._config.hotkey.key = self._key_combo.currentText().lower()
        hotkey_changed = (
            self._config.hotkey.modifier != old_mod
            or self._config.hotkey.key != old_key
        )

        # Overlay
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

        # Tidier
        self._config.tidier.enabled = self._tidier_enabled.isChecked()
        self._config.tidier.model = self._tidier_model_combo.currentText().strip()
        self._config.tidier.prompt = self._tidier_prompt.toPlainText().strip()

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
            },
            "tidier": {
                "enabled": self._config.tidier.enabled,
                "model": self._config.tidier.model,
                "prompt": self._config.tidier.prompt,
                "max_tokens": self._config.tidier.max_tokens,
            },
        }
        with open(CONFIG_PATH, "w") as f:
            yaml.dump(data, f, default_flow_style=False)

        self.settings_changed.emit()
        if hotkey_changed:
            self.hotkey_changed.emit()
        self.hide()
