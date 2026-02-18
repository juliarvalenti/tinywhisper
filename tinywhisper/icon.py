"""Programmatic tray icon — monochrome waveform (macOS template image)."""

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QIcon, QPainter, QPixmap


def create_tray_icon() -> QIcon:
    """Create a macOS-style template icon (monochrome, system handles color)."""
    size = 22
    px = QPixmap(size, size)
    px.fill(Qt.GlobalColor.transparent)

    p = QPainter(px)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(0, 0, 0))  # black — macOS inverts for dark mode

    bar_w = 2
    gap = 1
    heights = [5, 10, 16, 12, 8, 14, 6]
    total_w = len(heights) * bar_w + (len(heights) - 1) * gap
    x = (size - total_w) // 2
    mid = size // 2

    for h in heights:
        y = mid - h // 2
        p.drawRoundedRect(x, y, bar_w, h, 1, 1)
        x += bar_w + gap

    p.end()
    px.setDevicePixelRatio(1.0)

    # setIsMask tells macOS to treat this as a template image
    icon = QIcon(px)
    icon.setIsMask(True)
    return icon
