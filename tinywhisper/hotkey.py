"""Global hotkey via HID key-state polling.

Polls CGEventSourceKeyState on a QTimer to detect the configured hotkey.
Unlike CGEventTap, this reads raw HID hardware state and is not blocked
when apps enable Secure Event Input (e.g. Webex, Firefox).

Still requires Input Monitoring permission.
"""

from __future__ import annotations

import logging

import Quartz  # pyright: ignore[reportMissingImports]
from PyQt6.QtCore import QObject, QTimer, pyqtSignal

log = logging.getLogger(__name__)

# macOS virtual key codes
_VKEY_MAP = {
    "space": 49, "tab": 48, "enter": 36, "return": 36,
    "backspace": 51, "escape": 53, "esc": 53,
    "f1": 122, "f2": 120, "f3": 99, "f4": 118,
    "f5": 96, "f6": 97, "f7": 98, "f8": 100,
    "f9": 101, "f10": 109, "f11": 103, "f12": 111,
    "a": 0, "b": 11, "c": 8, "d": 2, "e": 14, "f": 3,
    "g": 5, "h": 4, "i": 34, "j": 38, "k": 40, "l": 37,
    "m": 46, "n": 45, "o": 31, "p": 35, "q": 12, "r": 15,
    "s": 1, "t": 17, "u": 32, "v": 9, "w": 13, "x": 7,
    "y": 16, "z": 6,
    "0": 29, "1": 18, "2": 19, "3": 20, "4": 21,
    "5": 23, "6": 22, "7": 26, "8": 28, "9": 25,
}

# CGEvent modifier flags
_MODIFIER_MAP = {
    "option": Quartz.kCGEventFlagMaskAlternate,
    "alt": Quartz.kCGEventFlagMaskAlternate,
    "ctrl": Quartz.kCGEventFlagMaskControl,
    "control": Quartz.kCGEventFlagMaskControl,
    "cmd": Quartz.kCGEventFlagMaskCommand,
    "command": Quartz.kCGEventFlagMaskCommand,
    "shift": Quartz.kCGEventFlagMaskShift,
    "none": 0,
    "": 0,
}

# Mask to isolate modifier keys we care about
_MOD_MASK = (
    Quartz.kCGEventFlagMaskAlternate
    | Quartz.kCGEventFlagMaskControl
    | Quartz.kCGEventFlagMaskCommand
    | Quartz.kCGEventFlagMaskShift
)

_HID_STATE = Quartz.kCGEventSourceStateHIDSystemState


def check_access() -> bool:
    """Check if Input Monitoring permission is granted."""
    return Quartz.CGPreflightListenEventAccess()


def request_access() -> bool:
    """Request Input Monitoring permission (triggers macOS prompt)."""
    return Quartz.CGRequestListenEventAccess()


class HotkeyListener(QObject):
    """Global hotkey via HID key-state polling — immune to Secure Event Input."""

    toggled = pyqtSignal()

    def __init__(self, modifier: str = "option", key: str = "space", parent: QObject | None = None):
        super().__init__(parent)
        self._modifier_flag = _MODIFIER_MAP.get(modifier.lower(), Quartz.kCGEventFlagMaskAlternate)
        self._vkey = _VKEY_MAP.get(key.lower(), 49)
        self._was_pressed = False
        self._timer = QTimer(self)
        self._timer.setInterval(50)
        self._timer.timeout.connect(self._poll)

    def update_binding(self, modifier: str, key: str) -> None:
        """Update the hotkey binding."""
        self._modifier_flag = _MODIFIER_MAP.get(modifier.lower(), Quartz.kCGEventFlagMaskAlternate)
        self._vkey = _VKEY_MAP.get(key.lower(), 49)

    def _poll(self) -> None:
        """Check HID hardware key state for the configured hotkey combo."""
        flags = Quartz.CGEventSourceFlagsState(_HID_STATE) & _MOD_MASK
        mod_match = flags == self._modifier_flag
        key_down = Quartz.CGEventSourceKeyState(_HID_STATE, self._vkey)
        pressed = mod_match and key_down
        if pressed and not self._was_pressed:
            self.toggled.emit()
        self._was_pressed = pressed

    def start(self) -> None:
        if not check_access():
            log.info("Input Monitoring not granted, requesting…")
            request_access()
            if not check_access():
                log.warning("Input Monitoring still not granted. "
                            "Grant permission in System Settings > Privacy & Security > Input Monitoring, "
                            "then restart.")
        self._timer.start()
        log.info("Hotkey listener started (vkey=%d, poll=%dms)", self._vkey, self._timer.interval())

    def stop(self) -> None:
        self._timer.stop()
