"""Frameless transparent overlay with scrolling waveform bars."""

from collections import deque

from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import QColor, QLinearGradient, QPainter, QPen
from PyQt6.QtWidgets import QApplication, QWidget

from tinywhisper.config import OverlayConfig


def _lerp_color(c1: QColor, c2: QColor, t: float) -> QColor:
    """Linearly interpolate between two colors."""
    return QColor(
        int(c1.red() + (c2.red() - c1.red()) * t),
        int(c1.green() + (c2.green() - c1.green()) * t),
        int(c1.blue() + (c2.blue() - c1.blue()) * t),
    )


def gradient_color_at(colors: list[QColor], t: float) -> QColor:
    """Return the interpolated color at position *t* (0.0 – 1.0) along
    an evenly-spaced gradient defined by *colors*."""
    if not colors:
        return QColor("#FF6B6B")
    if len(colors) == 1:
        return QColor(colors[0])
    t = max(0.0, min(1.0, t))
    segment = t * (len(colors) - 1)
    idx = int(segment)
    if idx >= len(colors) - 1:
        return QColor(colors[-1])
    return _lerp_color(colors[idx], colors[idx + 1], segment - idx)


class WaveformOverlay(QWidget):
    """A frameless, transparent, always-on-top overlay with gradient waveform."""

    MAX_BARS = 50

    def __init__(self, config: OverlayConfig, parent=None):
        super().__init__(parent)
        self._config = config
        self._bars: deque[float] = deque(maxlen=self.MAX_BARS)
        self._color = QColor(config.color)
        self._bg_color = QColor(config.bg_color)

        # Gradient support
        self._gradient = config.gradient and len(config.gradient_colors) >= 2
        self._gradient_colors = [QColor(c) for c in config.gradient_colors]

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_MacAlwaysShowToolWindow)
        self.setFixedSize(config.width, config.height)
        self._position_window()

    def _position_window(self):
        screen = QApplication.primaryScreen()
        if screen is None:
            return
        geo = screen.availableGeometry()
        x = geo.x() + (geo.width() - self._config.width) // 2
        y = geo.y() + 40
        self.move(x, y)

    def showEvent(self, a0):  # type: ignore[override]
        super().showEvent(a0)
        self._bars.clear()

    def push_amplitude(self, amplitude: float):
        self._bars.append(min(amplitude * 8, 1.0))
        self.update()

    def paintEvent(self, a0):  # type: ignore[override]
        w = self.width()
        h = self.height()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # --- Background with subtle vertical gradient for depth ---
        bg_top = QColor(self._bg_color)
        bg_top.setAlpha(int(255 * self._config.opacity))
        bg_bot = QColor(self._bg_color).darker(130)
        bg_bot.setAlpha(int(255 * self._config.opacity))

        bg_grad = QLinearGradient(0, 0, 0, h)
        bg_grad.setColorAt(0, bg_top)
        bg_grad.setColorAt(1, bg_bot)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(bg_grad)
        painter.drawRoundedRect(QRectF(0, 0, w, h), 14, 14)

        # --- Subtle inner border / highlight at top edge ---
        highlight = QColor(255, 255, 255, 18)
        painter.setPen(QPen(highlight, 1.0))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(QRectF(0.5, 0.5, w - 1, h - 1), 14, 14)

        if not self._bars:
            painter.end()
            return

        # --- Waveform bars ---
        bar_w = max(3, (w - 24) // self.MAX_BARS - 1)
        gap = 1
        total_bar_w = self.MAX_BARS * (bar_w + gap) - gap
        x_start = (w - total_bar_w) / 2
        mid_y = h / 2
        n_bars = len(self._bars)

        painter.setPen(Qt.PenStyle.NoPen)

        for i, amp in enumerate(self._bars):
            bar_h = max(3, int(amp * (h - 18)))
            x = x_start + i * (bar_w + gap)
            y = mid_y - bar_h / 2

            if self._gradient:
                # Position-based color: use bar index relative to total slots
                t = i / max(1, self.MAX_BARS - 1)
                color = gradient_color_at(self._gradient_colors, t)
                # Fade older (leftmost) bars slightly for depth
                if n_bars < self.MAX_BARS:
                    age = 1.0 - (i / max(1, n_bars))
                    color.setAlpha(int(255 * (0.5 + 0.5 * (1.0 - age))))
                painter.setBrush(color)
            else:
                painter.setBrush(self._color)

            painter.drawRoundedRect(QRectF(x, y, bar_w, bar_h), 1.5, 1.5)

        painter.end()
