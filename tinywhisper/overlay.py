"""Frameless transparent overlay with scrolling waveform bars."""

import math
import os
from collections import deque

from PyQt6.QtCore import Qt, QRectF, QTimer
from PyQt6.QtGui import QColor, QLinearGradient, QPainter, QPainterPath, QPen
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
    _AGC_DECAY = 0.995  # per-frame decay at ~30fps → peak halves in ~4.6s
    _GLOW_PAD = 48  # extra pixels on each side for pulse glow

    def __init__(self, config: OverlayConfig, parent=None):
        super().__init__(parent)
        self._config = config
        self._bars: deque[float] = deque(maxlen=self.MAX_BARS)
        self._agc_peak: float = 0.0
        self._pulse_phase: float = 0.0
        self._color = QColor(config.color)
        self._bg_color = QColor(config.bg_color)

        # Gradient support
        self._gradient = config.gradient and len(config.gradient_colors) >= 2
        self._gradient_colors = [QColor(c) for c in config.gradient_colors]

        # Extra padding for glow when pulse is enabled
        self._pad = self._GLOW_PAD if config.pulse else 0

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.NoDropShadowWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_MacAlwaysShowToolWindow)
        self.setFixedSize(config.width + self._pad * 2, config.height + self._pad * 2)
        self._position_window()

        # Follow-active-window mode
        self._follow = config.position == "follow"
        self._last_pos: tuple[int, int] | None = None
        if self._follow:
            self._follow_timer = QTimer(self)
            self._follow_timer.setInterval(200)
            self._follow_timer.timeout.connect(self._update_follow_position)

    def _position_window(self):
        screen = QApplication.primaryScreen()
        if screen is None:
            return
        geo = screen.availableGeometry()
        x = geo.x() + (geo.width() - self._config.width) // 2 - self._pad
        y = geo.y() + 40 - self._pad
        self.move(x, y)

    # ── Follow active monitor ───────────────────────────────────────────

    def _get_active_screen_geo(self) -> QRectF | None:
        """Return the available geometry of the screen containing the frontmost window."""
        try:
            from AppKit import NSWorkspace
            import Quartz
        except ImportError:
            return None

        front_app = NSWorkspace.sharedWorkspace().frontmostApplication()
        if front_app is None:
            return None
        front_pid = front_app.processIdentifier()
        if front_pid == os.getpid():
            return None

        windows = Quartz.CGWindowListCopyWindowInfo(
            Quartz.kCGWindowListOptionOnScreenOnly
            | Quartz.kCGWindowListExcludeDesktopElements,
            Quartz.kCGNullWindowID,
        )
        if windows is None:
            return None

        for win in windows:
            if win.get("kCGWindowOwnerPID") != front_pid:
                continue
            if win.get("kCGWindowLayer", -1) != 0:
                continue
            bounds = win.get("kCGWindowBounds")
            if bounds is None:
                continue
            w = int(bounds["Width"])
            h = int(bounds["Height"])
            if w == 0 or h == 0:
                continue
            # Find which screen contains this window's center
            cx = int(bounds["X"]) + w // 2
            cy = int(bounds["Y"]) + h // 2
            app = QApplication.instance()
            if app is not None:
                for s in app.screens():
                    if s.geometry().contains(cx, cy):
                        geo = s.availableGeometry()
                        return QRectF(geo.x(), geo.y(), geo.width(), geo.height())
            break
        return None

    def _update_follow_position(self) -> None:
        """Reposition overlay at top-center of the active monitor."""
        geo = self._get_active_screen_geo()
        if geo is None:
            self._position_window()
            return

        x = int(geo.x()) + (int(geo.width()) - self._config.width) // 2 - self._pad
        y = int(geo.y()) + 40 - self._pad

        pos = (x, y)
        if pos != self._last_pos:
            self._last_pos = pos
            self.move(x, y)

    # ── Visibility events ────────────────────────────────────────────────

    def showEvent(self, a0):  # type: ignore[override]
        super().showEvent(a0)
        self._bars.clear()
        self._agc_peak = 0.0
        self._pulse_phase = 0.0
        if self._follow:
            self._update_follow_position()
            self._follow_timer.start()

    def hideEvent(self, a0):  # type: ignore[override]
        super().hideEvent(a0)
        if self._follow:
            self._follow_timer.stop()
            self._last_pos = None

    def push_amplitude(self, amplitude: float):
        # Exponential-decay AGC: instant attack, slow release (~4.6s half-life)
        self._agc_peak = max(amplitude, self._agc_peak * self._AGC_DECAY)
        floor = 0.005
        normalized = amplitude / max(self._agc_peak, floor)
        self._bars.append(min(normalized, 1.0))
        self._pulse_phase += 0.08
        self.update()

    def _glow_color(self) -> QColor:
        """Return the configured pulse glow color."""
        return QColor(self._config.pulse_color)

    def paintEvent(self, a0):  # type: ignore[override]
        p = self._pad
        w = self._config.width
        h = self._config.height
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # --- Pulsing glow halo behind the background ---
        if self._config.pulse and self._bars:
            glow_base = self._glow_color()
            pulse_t = (math.sin(self._pulse_phase) + 1.0) / 2.0
            glow_radius = self._GLOW_PAD - 4  # stop 4px before widget edge
            # Inner boundary: flush with background edge
            inner_clip = QPainterPath()
            inner_clip.addRoundedRect(QRectF(p, p, w, h), 14, 14)
            painter.save()
            painter.setPen(Qt.PenStyle.NoPen)
            step = 3  # draw every 3px for performance
            intensity = self._config.pulse_opacity
            for i in range(glow_radius, 2, -step):
                # Gaussian falloff: peaks near background, fades to zero
                dist = i / glow_radius  # 0 = edge, 1 = far
                alpha = int(80 * intensity * pulse_t * math.exp(-4.0 * dist * dist))
                if alpha < 1:
                    continue
                outer = QPainterPath()
                outer.addRoundedRect(
                    QRectF(p - i, p - i, w + i * 2, h + i * 2),
                    14 + i, 14 + i,
                )
                inner = QPainterPath()
                inner.addRoundedRect(
                    QRectF(p - i + step, p - i + step,
                           w + (i - step) * 2, h + (i - step) * 2),
                    14 + max(0, i - step), 14 + max(0, i - step),
                )
                ring = outer - inner
                glow = QColor(glow_base)
                glow.setAlpha(alpha)
                painter.setBrush(glow)
                painter.drawPath(ring)
            painter.restore()

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
        painter.drawRoundedRect(QRectF(p, p, w, h), 14, 14)

        # --- Subtle inner border / highlight at top edge ---
        highlight = QColor(255, 255, 255, 18)
        painter.setPen(QPen(highlight, 1.0))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(QRectF(p + 0.5, p + 0.5, w - 1, h - 1), 14, 14)

        if not self._bars:
            painter.end()
            return

        # --- Waveform bars ---
        bar_w = max(3, (w - 24) // self.MAX_BARS - 1)
        gap = 1
        total_bar_w = self.MAX_BARS * (bar_w + gap) - gap
        x_start = p + (w - total_bar_w) / 2
        mid_y = p + h / 2
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
