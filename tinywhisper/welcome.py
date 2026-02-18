"""Welcome / options screen."""

import logging
import subprocess
from collections.abc import Callable

import Quartz  # pyright: ignore[reportMissingImports]
from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QFrame, QHBoxLayout, QLabel,
    QPushButton, QVBoxLayout, QWidget,
)

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Permission helpers
# ---------------------------------------------------------------------------

def _check_input_monitoring() -> bool:
    if Quartz.CGPreflightListenEventAccess():  # pyright: ignore[reportAttributeAccessIssue]
        return True
    try:
        tap = Quartz.CGEventTapCreate(  # pyright: ignore[reportAttributeAccessIssue]
            Quartz.kCGSessionEventTap,  # pyright: ignore[reportAttributeAccessIssue]
            Quartz.kCGHeadInsertEventTap,  # pyright: ignore[reportAttributeAccessIssue]
            Quartz.kCGEventTapOptionListenOnly,  # pyright: ignore[reportAttributeAccessIssue]
            Quartz.CGEventMaskBit(Quartz.kCGEventKeyDown),  # pyright: ignore[reportAttributeAccessIssue]
            lambda proxy, event_type, event, refcon: event,
            None,
        )
        if tap is not None:
            Quartz.CFRelease(tap)  # pyright: ignore[reportAttributeAccessIssue]
            return True
    except Exception:
        pass
    return False


def _check_accessibility() -> bool:
    from ApplicationServices import AXIsProcessTrusted  # pyright: ignore[reportMissingImports]
    return AXIsProcessTrusted()


def _check_microphone() -> int:
    """Return AVAuthorizationStatus: 0=notDetermined 1=restricted 2=denied 3=authorized."""
    import AVFoundation  # pyright: ignore[reportMissingImports]
    return AVFoundation.AVCaptureDevice.authorizationStatusForMediaType_(AVFoundation.AVMediaTypeAudio)


def _request_input_monitoring():
    Quartz.CGRequestListenEventAccess()  # pyright: ignore[reportAttributeAccessIssue]


def _open_accessibility_settings():
    subprocess.Popen(["open", "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility"])


def _open_input_monitoring_settings():
    subprocess.Popen(["open", "x-apple.systempreferences:com.apple.preference.security?Privacy_ListenEvent"])


def _open_microphone_settings():
    subprocess.Popen(["open", "x-apple.systempreferences:com.apple.preference.security?Privacy_Microphone"])


# ---------------------------------------------------------------------------
# Launch at startup (SMAppService, macOS 13+)
# ---------------------------------------------------------------------------

def _startup_service():
    try:
        from ServiceManagement import SMAppService  # pyright: ignore[reportMissingImports]
        return SMAppService.mainAppService()
    except Exception:
        return None


def is_launch_at_startup() -> bool:
    svc = _startup_service()
    if svc is None:
        return False
    try:
        return svc.status() == 1  # SMAppServiceStatusEnabled
    except Exception:
        return False


def set_launch_at_startup(enabled: bool):
    svc = _startup_service()
    if svc is None:
        log.warning("SMAppService not available (requires macOS 13+)")
        return
    try:
        if enabled:
            err = svc.registerAndReturnError_(None)
        else:
            err = svc.unregisterAndReturnError_(None)
        if err:
            log.warning("Launch at startup toggle error: %s", err)
    except Exception as e:
        log.warning("Launch at startup toggle failed: %s", e)


# ---------------------------------------------------------------------------
# Audio device listing
# ---------------------------------------------------------------------------

def _list_input_devices() -> list[dict]:
    import sounddevice as sd
    devices = sd.query_devices()
    return [
        {"index": i, "name": d["name"]}
        for i, d in enumerate(devices)
        if d["max_input_channels"] > 0
    ]


# ---------------------------------------------------------------------------
# UI constants
# ---------------------------------------------------------------------------

MODIFIERS = ["Option", "Ctrl", "Cmd", "Shift"]
KEYS = ["Space", "Tab", "Enter", "F1", "F2", "F3", "F4", "F5",
        "F6", "F7", "F8", "F9", "F10", "F11", "F12"]

_FONT = QFont(".AppleSystemUIFont", 12)
_BOLD = QFont(".AppleSystemUIFont", 12, QFont.Weight.Bold)
_SMALL = QFont(".AppleSystemUIFont", 11)
_LABEL_W = 140  # fixed width for left-column labels


def _section_label(text: str) -> QLabel:
    lbl = QLabel(text.upper())
    lbl.setFont(QFont(".AppleSystemUIFont", 10, QFont.Weight.Bold))
    lbl.setStyleSheet("color: #888; letter-spacing: 0.5px;")
    return lbl


def _divider() -> QFrame:
    line = QFrame()
    line.setFrameShape(QFrame.Shape.HLine)
    line.setStyleSheet("color: rgba(128,128,128,0.25);")
    return line


# ---------------------------------------------------------------------------
# Permission row
# ---------------------------------------------------------------------------

class _PermRow(QWidget):
    def __init__(self, label: str, action_fn, btn_text: str = "Open Settings", parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 2, 0, 2)
        lay.setSpacing(8)

        name = QLabel(label)
        name.setFont(_FONT)
        name.setFixedWidth(_LABEL_W)
        lay.addWidget(name)

        self._dot = QLabel("●")
        self._dot.setFont(_FONT)
        self._dot.setStyleSheet("color: #FF9800;")
        lay.addWidget(self._dot)

        self._status = QLabel("pending")
        self._status.setFont(_SMALL)
        self._status.setStyleSheet("color: #888;")
        lay.addWidget(self._status)

        lay.addStretch()

        self._btn = QPushButton(btn_text)
        self._btn.setFont(_SMALL)
        self._btn.setFixedWidth(105)
        self._btn.clicked.connect(action_fn)
        lay.addWidget(self._btn)

    def set_granted(self):
        self._dot.setStyleSheet("color: #4CAF50;")
        self._status.setText("granted")
        self._status.setStyleSheet("color: #4CAF50;")
        self._btn.setEnabled(False)
        self._btn.setText("Done")

    @property
    def is_granted(self) -> bool:
        return self._status.text() == "granted"


# ---------------------------------------------------------------------------
# Option row (label + arbitrary widget)
# ---------------------------------------------------------------------------

def _opt_row(label: str, control: QWidget) -> QHBoxLayout:
    row = QHBoxLayout()
    row.setContentsMargins(0, 0, 0, 0)
    lbl = QLabel(label)
    lbl.setFont(_FONT)
    lbl.setFixedWidth(_LABEL_W)
    row.addWidget(lbl)
    row.addWidget(control, 1)
    return row


# ---------------------------------------------------------------------------
# Welcome / options window
# ---------------------------------------------------------------------------

class WelcomeWindow(QWidget):
    device_changed: Callable[..., None] | None = None
    hotkey_changed: Callable[..., None] | None = None
    open_settings: Callable[[], None] | None = None  # set by app.py

    def __init__(
        self,
        hotkey_label: str,
        model_label: str,
        current_device: str | None = None,
        current_modifier: str = "option",
        current_key: str = "space",
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle("TinyWhisper")
        self.setFixedSize(430, 460)

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 16)
        root.setSpacing(0)

        # ── Header ──────────────────────────────────────────────────────────
        header = QHBoxLayout()
        title = QLabel("TinyWhisper")
        title.setFont(QFont(".AppleSystemUIFont", 18, QFont.Weight.Bold))
        header.addWidget(title)
        header.addStretch()
        self._model_status = QLabel(f"Loading {model_label}…")
        self._model_status.setFont(_SMALL)
        self._model_status.setStyleSheet("color: #888;")
        header.addWidget(self._model_status)
        root.addLayout(header)

        root.addSpacing(14)
        root.addWidget(_divider())
        root.addSpacing(10)

        # ── Permissions ──────────────────────────────────────────────────────
        root.addWidget(_section_label("Permissions"))
        root.addSpacing(6)

        self._input_row = _PermRow("Input Monitoring", self._on_input)
        self._access_row = _PermRow("Accessibility", _open_accessibility_settings)
        self._mic_row = _PermRow("Microphone", self._request_mic, btn_text="Grant Access")
        root.addWidget(self._input_row)
        root.addWidget(self._access_row)
        root.addWidget(self._mic_row)

        root.addSpacing(10)
        root.addWidget(_divider())
        root.addSpacing(10)

        # ── Options ──────────────────────────────────────────────────────────
        root.addWidget(_section_label("Options"))
        root.addSpacing(6)

        # Hotkey
        hk_widget = QWidget()
        hk_lay = QHBoxLayout(hk_widget)
        hk_lay.setContentsMargins(0, 0, 0, 0)
        hk_lay.setSpacing(4)
        self._mod_combo = QComboBox()
        self._mod_combo.setFont(_FONT)
        self._mod_combo.addItems(MODIFIERS)
        self._mod_combo.setCurrentText(current_modifier.capitalize())
        hk_lay.addWidget(self._mod_combo)
        plus = QLabel("+")
        plus.setFont(_FONT)
        plus.setStyleSheet("color: #888;")
        hk_lay.addWidget(plus)
        self._key_combo = QComboBox()
        self._key_combo.setFont(_FONT)
        self._key_combo.addItems(KEYS)
        self._key_combo.setCurrentText(current_key.capitalize())
        hk_lay.addWidget(self._key_combo)
        hk_lay.addStretch()
        root.addLayout(_opt_row("Hotkey", hk_widget))
        root.addSpacing(4)

        # Audio input
        self._device_combo = QComboBox()
        self._device_combo.setFont(_FONT)
        self._populate_devices(current_device)
        root.addLayout(_opt_row("Audio Input", self._device_combo))
        root.addSpacing(4)

        # Launch at startup
        self._startup_check = QCheckBox()
        self._startup_check.setChecked(is_launch_at_startup())
        root.addLayout(_opt_row("Launch at Startup", self._startup_check))

        root.addSpacing(10)
        root.addWidget(_divider())
        root.addSpacing(10)

        # ── Footer ───────────────────────────────────────────────────────────
        footer = QHBoxLayout()
        gh = QLabel('<a href="https://github.com/juliarvalenti/tinywhisper">github.com/juliarvalenti/tinywhisper</a>')
        gh.setFont(_SMALL)
        gh.setOpenExternalLinks(True)
        gh.setStyleSheet("color: #888;")
        footer.addWidget(gh)
        footer.addStretch()
        settings_btn = QPushButton("Settings…")
        settings_btn.setFont(_SMALL)
        settings_btn.clicked.connect(self._open_settings)
        footer.addWidget(settings_btn)
        close_btn = QPushButton("Close")
        close_btn.setFont(_SMALL)
        close_btn.clicked.connect(self.close)
        footer.addWidget(close_btn)
        root.addLayout(footer)

        # ── Signals ──────────────────────────────────────────────────────────
        self._mod_combo.currentIndexChanged.connect(self._on_hotkey_changed)
        self._key_combo.currentIndexChanged.connect(self._on_hotkey_changed)
        self._device_combo.currentIndexChanged.connect(self._on_device_changed)
        self._startup_check.toggled.connect(self._on_startup_toggled)

        # ── Permission polling ───────────────────────────────────────────────
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._poll_permissions)
        self._timer.start(1000)
        self._poll_permissions()

    # ── Slots ────────────────────────────────────────────────────────────────

    def _on_input(self):
        _request_input_monitoring()
        _open_input_monitoring_settings()

    def _request_mic(self):
        import AVFoundation  # pyright: ignore[reportMissingImports]
        status = AVFoundation.AVCaptureDevice.authorizationStatusForMediaType_(
            AVFoundation.AVMediaTypeAudio
        )
        if status == 0:
            try:
                device = AVFoundation.AVCaptureDevice.defaultDeviceWithMediaType_(
                    AVFoundation.AVMediaTypeAudio
                )
                if device is not None:
                    AVFoundation.AVCaptureDeviceInput.deviceInputWithDevice_error_(device, None)
            except Exception as e:
                log.error("Failed to trigger mic permission: %s", e)
        elif status == 2:
            _open_microphone_settings()

    def _poll_permissions(self):
        try:
            if not self._input_row.is_granted and _check_input_monitoring():
                self._input_row.set_granted()
                log.info("Input Monitoring permission granted")
            if not self._access_row.is_granted and _check_accessibility():
                self._access_row.set_granted()
                log.info("Accessibility permission granted")
            if not self._mic_row.is_granted and _check_microphone() == 3:
                self._mic_row.set_granted()
                log.info("Microphone permission granted")
            if self._input_row.is_granted and self._access_row.is_granted and self._mic_row.is_granted:
                self._timer.stop()
        except Exception:
            log.exception("Error polling permissions")

    def _populate_devices(self, current_device: str | None):
        self._device_combo.blockSignals(True)
        self._device_combo.clear()
        self._device_combo.addItem("System Default", None)
        selected = 0
        for dev in _list_input_devices():
            self._device_combo.addItem(dev["name"], dev["name"])
            if current_device and current_device.lower() in dev["name"].lower():
                selected = self._device_combo.count() - 1
        self._device_combo.setCurrentIndex(selected)
        self._device_combo.blockSignals(False)

    def _on_device_changed(self, index: int):
        device_name = self._device_combo.itemData(index)
        log.info("Device selected: %s", device_name or "System Default")
        if self.device_changed:
            self.device_changed(device_name)

    def _on_hotkey_changed(self):
        modifier = self._mod_combo.currentText().lower()
        key = self._key_combo.currentText().lower()
        log.info("Hotkey changed to: %s+%s", modifier, key)
        if self.hotkey_changed:
            self.hotkey_changed(modifier, key)

    def _on_startup_toggled(self, checked: bool):
        log.info("Launch at startup: %s", checked)
        set_launch_at_startup(checked)

    def _open_settings(self):
        if self.open_settings:
            self.open_settings()

    # ── Public API ───────────────────────────────────────────────────────────

    def set_ready(self, hotkey_label: str):
        self._model_status.setText("● Model ready")
        self._model_status.setStyleSheet("color: #4CAF50;")

    def set_error(self, msg: str):
        self._model_status.setText(f"Error: {msg}")
        self._model_status.setStyleSheet("color: #F44336;")

    def refresh_startup(self):
        """Sync checkbox with actual system state (e.g. after tray toggle)."""
        self._startup_check.blockSignals(True)
        self._startup_check.setChecked(is_launch_at_startup())
        self._startup_check.blockSignals(False)
