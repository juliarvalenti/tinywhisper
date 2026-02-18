"""Programmatic tray icon — 'TW' text (macOS template image)."""

from PyQt6.QtCore import Qt, QRect
from PyQt6.QtGui import QColor, QFont, QIcon, QPainter, QPixmap


def create_tray_icon() -> QIcon:
    """Create a macOS-style template icon with 'TW' text."""
    logical = 22
    scale = 2  # Retina
    size = logical * scale
    px = QPixmap(size, size)
    px.fill(Qt.GlobalColor.transparent)

    p = QPainter(px)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    p.setPen(QColor(0, 0, 0))  # black — macOS inverts for dark mode
    p.setFont(QFont(".AppleSystemUIFont", 24, QFont.Weight.Bold))
    p.drawText(QRect(0, 0, size, size), Qt.AlignmentFlag.AlignCenter, "TW")

    p.end()
    px.setDevicePixelRatio(scale)

    icon = QIcon(px)
    icon.setIsMask(True)
    return icon
