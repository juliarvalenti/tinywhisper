"""Global hotkey listener using pynput, bridged to Qt signals."""

from pynput import keyboard
from PyQt6.QtCore import QObject, pyqtSignal

# Map config names to pynput Key objects
MODIFIER_MAP = {
    "option": (keyboard.Key.alt, keyboard.Key.alt_l, keyboard.Key.alt_r),
    "alt": (keyboard.Key.alt, keyboard.Key.alt_l, keyboard.Key.alt_r),
    "ctrl": (keyboard.Key.ctrl, keyboard.Key.ctrl_l, keyboard.Key.ctrl_r),
    "control": (keyboard.Key.ctrl, keyboard.Key.ctrl_l, keyboard.Key.ctrl_r),
    "cmd": (keyboard.Key.cmd, keyboard.Key.cmd_l, keyboard.Key.cmd_r),
    "command": (keyboard.Key.cmd, keyboard.Key.cmd_l, keyboard.Key.cmd_r),
    "shift": (keyboard.Key.shift, keyboard.Key.shift_l, keyboard.Key.shift_r),
}

KEY_MAP = {
    "space": keyboard.Key.space,
    "tab": keyboard.Key.tab,
    "enter": keyboard.Key.enter,
    "backspace": keyboard.Key.backspace,
    "escape": keyboard.Key.esc,
    "esc": keyboard.Key.esc,
    "f1": keyboard.Key.f1, "f2": keyboard.Key.f2, "f3": keyboard.Key.f3,
    "f4": keyboard.Key.f4, "f5": keyboard.Key.f5, "f6": keyboard.Key.f6,
    "f7": keyboard.Key.f7, "f8": keyboard.Key.f8, "f9": keyboard.Key.f9,
    "f10": keyboard.Key.f10, "f11": keyboard.Key.f11, "f12": keyboard.Key.f12,
}


class HotkeyListener(QObject):
    """Listens for a configurable modifier+key combo and emits a toggle signal."""

    toggled = pyqtSignal()

    def __init__(self, modifier: str = "option", key: str = "space", parent=None):
        super().__init__(parent)
        self._modifier_keys = MODIFIER_MAP.get(modifier.lower(), MODIFIER_MAP["option"])
        key_lower = key.lower()
        self._trigger_key = KEY_MAP.get(key_lower, None)
        self._trigger_char = key_lower if self._trigger_key is None else None
        self._mod_pressed = False
        self._listener: keyboard.Listener | None = None

    def update_binding(self, modifier: str, key: str):
        """Update the hotkey binding. Restarts the listener if running."""
        was_running = self._listener is not None
        if was_running:
            self.stop()
        self._modifier_keys = MODIFIER_MAP.get(modifier.lower(), MODIFIER_MAP["option"])
        key_lower = key.lower()
        self._trigger_key = KEY_MAP.get(key_lower, None)
        self._trigger_char = key_lower if self._trigger_key is None else None
        if was_running:
            self.start()

    def start(self):
        self._listener = keyboard.Listener(
            on_press=self._on_press,
            on_release=self._on_release,
        )
        self._listener.daemon = True
        self._listener.start()

    def stop(self):
        if self._listener is not None:
            self._listener.stop()
            self._listener = None

    def _on_press(self, key):
        if key in self._modifier_keys:
            self._mod_pressed = True
        elif self._mod_pressed:
            if self._trigger_key is not None and key == self._trigger_key:
                self.toggled.emit()
            elif self._trigger_char is not None:
                try:
                    if hasattr(key, 'char') and key.char == self._trigger_char:
                        self.toggled.emit()
                except AttributeError:
                    pass

    def _on_release(self, key):
        if key in self._modifier_keys:
            self._mod_pressed = False
