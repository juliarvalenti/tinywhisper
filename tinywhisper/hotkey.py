"""Global hotkey using CGEventTap via Quartz.

Uses CGRequestListenEventAccess() to trigger the macOS permission prompt
and CGEventTapCreate with kCGEventTapOptionListenOnly for passive monitoring.
Integrates with Qt's event loop via CFRunLoop.
"""

from __future__ import annotations

import logging

import Quartz
from PyQt6.QtCore import QObject, pyqtSignal

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
}

# Mask to isolate modifier keys we care about
_MOD_MASK = (
    Quartz.kCGEventFlagMaskAlternate
    | Quartz.kCGEventFlagMaskControl
    | Quartz.kCGEventFlagMaskCommand
    | Quartz.kCGEventFlagMaskShift
)


def check_access() -> bool:
    """Check if Input Monitoring permission is granted."""
    return Quartz.CGPreflightListenEventAccess()


def request_access() -> bool:
    """Request Input Monitoring permission (triggers macOS prompt)."""
    return Quartz.CGRequestListenEventAccess()


class HotkeyListener(QObject):
    """Global hotkey via CGEventTap — needs Input Monitoring permission."""

    toggled = pyqtSignal()

    def __init__(self, modifier: str = "option", key: str = "space", parent=None):
        super().__init__(parent)
        self._modifier_flag = _MODIFIER_MAP.get(modifier.lower(), Quartz.kCGEventFlagMaskAlternate)
        self._vkey = _VKEY_MAP.get(key.lower(), 49)
        self._tap = None
        self._source = None

    def update_binding(self, modifier: str, key: str):
        """Update the hotkey binding. Restarts the tap if running."""
        was_running = self._tap is not None
        if was_running:
            self.stop()
        self._modifier_flag = _MODIFIER_MAP.get(modifier.lower(), Quartz.kCGEventFlagMaskAlternate)
        self._vkey = _VKEY_MAP.get(key.lower(), 49)
        if was_running:
            self.start()

    def start(self):
        # Check / request permission
        if not check_access():
            log.info("Input Monitoring not granted, requesting…")
            request_access()
            if not check_access():
                log.warning("Input Monitoring still not granted. "
                            "Grant permission in System Settings > Privacy & Security > Input Monitoring, "
                            "then restart.")

        def _callback(proxy, event_type, event, refcon):
            keycode = Quartz.CGEventGetIntegerValueField(event, Quartz.kCGKeyboardEventKeycode)
            flags = Quartz.CGEventGetFlags(event) & _MOD_MASK
            if keycode == self._vkey and flags == self._modifier_flag:
                self.toggled.emit()
            return event

        self._tap = Quartz.CGEventTapCreate(
            Quartz.kCGSessionEventTap,
            Quartz.kCGHeadInsertEventTap,
            Quartz.kCGEventTapOptionListenOnly,
            Quartz.CGEventMaskBit(Quartz.kCGEventKeyDown),
            _callback,
            None,
        )

        if self._tap is None:
            log.error("CGEventTapCreate failed — Input Monitoring not granted.")
            return

        self._source = Quartz.CFMachPortCreateRunLoopSource(None, self._tap, 0)
        Quartz.CFRunLoopAddSource(
            Quartz.CFRunLoopGetCurrent(),
            self._source,
            Quartz.kCFRunLoopCommonModes,
        )
        Quartz.CGEventTapEnable(self._tap, True)
        log.info("Hotkey listener started (vkey=%d)", self._vkey)

    def stop(self):
        if self._tap is not None:
            Quartz.CGEventTapEnable(self._tap, False)
            if self._source is not None:
                Quartz.CFRunLoopRemoveSource(
                    Quartz.CFRunLoopGetCurrent(),
                    self._source,
                    Quartz.kCFRunLoopCommonModes,
                )
                self._source = None
            self._tap = None
