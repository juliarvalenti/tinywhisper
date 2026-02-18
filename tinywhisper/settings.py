"""Settings window for overlay appearance with live preview."""

import math
import random

from PyQt6.QtCore import Qt, QRectF, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QLinearGradient, QPainter, QPen
from PyQt6.QtWidgets import (
    QColorDialog,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from tinywhisper.config import AppConfig, CONFIG_DIR, CONFIG_PATH

import yaml


class WaveformPreview(QWidget):
    """Animated waveform preview that reflects current settings."""

    MAX_BARS = 60

    def __init__(self, parent=None):
        super().__init__(parent)
        self._opacity = 0.85
        self._color = QColor("#FF6B6B")
        self._bg_color = QColor("#1E1E1E")
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

        # Bars with gradient
        bar_w = max(3, (w - 24) // self.MAX_BARS - 1)
        gap = 1
        total_bar_w = self.MAX_BARS * (bar_w + gap) - gap
        x_start = (w - total_bar_w) / 2
        mid_y = h / 2

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self._color)
        for i, amp in enumerate(self._bars):
            bh = max(3, int(amp * (h - 18)))
            x = x_start + i * (bar_w + gap)
            y = mid_y - bh / 2
            painter.drawRoundedRect(QRectF(x, y, bar_w, bh), 1.5, 1.5)

        painter.end()


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

        self.setWindowTitle("TinyWhisper Settings")
        self.setFixedSize(380, 480)
        self.setWindowFlags(
            Qt.WindowType.Window | Qt.WindowType.WindowStaysOnTopHint
        )

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # Hotkey binding
        layout.addWidget(QLabel("Hotkey"))
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

        layout.addWidget(QLabel(""))  # spacer

        # Live preview
        self._preview = WaveformPreview()
        self._preview.setFixedHeight(60)
        self._preview.set_opacity(config.overlay.opacity)
        self._preview.set_color(self._color)
        self._preview.set_bg_color(self._bg_color)
        layout.addWidget(self._preview)

        # Opacity slider
        layout.addWidget(QLabel("Overlay Opacity"))
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

        # Width
        layout.addWidget(QLabel("Overlay Width"))
        self._width_spin = QSpinBox()
        self._width_spin.setRange(100, 800)
        self._width_spin.setValue(config.overlay.width)
        layout.addWidget(self._width_spin)

        # Height
        layout.addWidget(QLabel("Overlay Height"))
        self._height_spin = QSpinBox()
        self._height_spin.setRange(30, 200)
        self._height_spin.setValue(config.overlay.height)
        layout.addWidget(self._height_spin)

        # Waveform color picker
        wave_color_row = QHBoxLayout()
        wave_color_row.addWidget(QLabel("Waveform Color"))
        self._color_btn = QPushButton()
        self._color_btn.setFixedSize(60, 28)
        self._update_color_btn()
        self._color_btn.clicked.connect(self._pick_color)
        wave_color_row.addWidget(self._color_btn)
        wave_color_row.addStretch()
        layout.addLayout(wave_color_row)

        # Background color picker
        bg_color_row = QHBoxLayout()
        bg_color_row.addWidget(QLabel("Background Color"))
        self._bg_color_btn = QPushButton()
        self._bg_color_btn.setFixedSize(60, 28)
        self._update_bg_color_btn()
        self._bg_color_btn.clicked.connect(self._pick_bg_color)
        bg_color_row.addWidget(self._bg_color_btn)
        bg_color_row.addStretch()
        layout.addLayout(bg_color_row)

        # Save button
        save_btn = QPushButton("Save && Apply")
        save_btn.clicked.connect(self._save)
        layout.addWidget(save_btn)

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

    def _update_color_btn(self):
        self._color_btn.setStyleSheet(
            f"background-color: {self._color.name()}; border: 1px solid #888; border-radius: 4px;"
        )

    def _update_bg_color_btn(self):
        self._bg_color_btn.setStyleSheet(
            f"background-color: {self._bg_color.name()}; border: 1px solid #888; border-radius: 4px;"
        )

    def _pick_color(self):
        color = QColorDialog.getColor(self._color, self, "Waveform Color")
        if color.isValid():
            self._color = color
            self._update_color_btn()
            self._preview.set_color(color)

    def _pick_bg_color(self):
        color = QColorDialog.getColor(self._bg_color, self, "Background Color")
        if color.isValid():
            self._bg_color = color
            self._update_bg_color_btn()
            self._preview.set_bg_color(color)

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
            },
        }
        with open(CONFIG_PATH, "w") as f:
            yaml.dump(data, f, default_flow_style=False)

        self.settings_changed.emit()
        if hotkey_changed:
            self.hotkey_changed.emit()
        self.hide()
