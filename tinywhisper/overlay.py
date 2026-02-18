"""Frameless transparent overlay with scrolling waveform bars."""

from collections import deque

from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import QColor, QLinearGradient, QPainter, QPen
from PyQt6.QtWidgets import QApplication, QWidget

from tinywhisper.config import OverlayConfig


class WaveformOverlay(QWidget):
    """A frameless, transparent, always-on-top overlay with gradient waveform."""

    MAX_BARS = 50

    def __init__(self, config: OverlayConfig, parent=None):
        super().__init__(parent)
        self._config = config
        self._bars: deque[float] = deque(maxlen=self.MAX_BARS)
        self._color = QColor(config.color)
        self._bg_color = QColor(config.bg_color)

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

    def showEvent(self, event):
        super().showEvent(event)
        self._bars.clear()

    def push_amplitude(self, amplitude: float):
        self._bars.append(min(amplitude * 8, 1.0))
        self.update()

    def paintEvent(self, event):
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

        # --- Waveform bars with vertical gradient ---
        bar_w = max(3, (w - 24) // self.MAX_BARS - 1)
        gap = 1
        total_bar_w = self.MAX_BARS * (bar_w + gap) - gap
        x_start = (w - total_bar_w) / 2
        mid_y = h / 2

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self._color)

        for i, amp in enumerate(self._bars):
            bar_h = max(3, int(amp * (h - 18)))
            x = x_start + i * (bar_w + gap)
            y = mid_y - bar_h / 2
            painter.drawRoundedRect(QRectF(x, y, bar_w, bar_h), 1.5, 1.5)

        painter.end()
