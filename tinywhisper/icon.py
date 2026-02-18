"""Tray icon — feather silhouette as macOS template image."""

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont, QIcon, QImage, QPainter, QPixmap

_TRAY_SRC = Path(__file__).parent / "tray_icon.jpg"


def _build_template(logical: int = 22, scale: int = 2, zoom: float = 2.07) -> QPixmap:
    """Load feather image, map white -> opaque black, dark -> transparent.

    zoom > 1 scales the source larger than the target then crops to center,
    effectively trimming the thick black padding around the feather.
    """
    size = logical * scale
    src = QPixmap(str(_TRAY_SRC))
    if src.isNull():
        return _fallback(size)

    zoomed = int(size * zoom)
    big = src.scaled(
        zoomed, zoomed,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )
    # Crop center size×size out of the zoomed pixmap
    ox = (big.width() - size) // 2
    oy = (big.height() - size) // 2
    scaled = big.copy(ox, oy, size, size)

    img = scaled.toImage().convertToFormat(QImage.Format.Format_ARGB32)
    for y in range(img.height()):
        for x in range(img.width()):
            p = img.pixel(x, y)
            brightness = ((p >> 16) & 0xFF) * 299 + ((p >> 8) & 0xFF) * 587 + (p & 0xFF) * 114
            alpha = brightness // 1000  # 0–255
            img.setPixel(x, y, (alpha << 24) & 0xFF000000)  # black, variable alpha

    px = QPixmap.fromImage(img)
    px.setDevicePixelRatio(scale)
    return px


def _fallback(size: int) -> QPixmap:
    px = QPixmap(size, size)
    px.fill(Qt.GlobalColor.transparent)
    p = QPainter(px)
    p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    p.setPen(QColor(0, 0, 0))
    p.setFont(QFont(".AppleSystemUIFont", 24, QFont.Weight.Bold))
    from PyQt6.QtCore import QRect
    p.drawText(QRect(0, 0, size, size), Qt.AlignmentFlag.AlignCenter, "TW")
    p.end()
    return px


def create_tray_icon() -> QIcon:
    """Return a macOS template tray icon from the feather image."""
    px = _build_template()
    icon = QIcon(px)
    icon.setIsMask(True)
    return icon
