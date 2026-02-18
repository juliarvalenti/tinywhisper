"""Welcome screen with permission onboarding flow."""

import logging
import subprocess
from collections.abc import Callable

import Quartz  # pyright: ignore[reportMissingImports]
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QComboBox, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget,
)


log = logging.getLogger(__name__)

# --- Permission checks ---

def _check_input_monitoring() -> bool:
    # CGPreflightListenEventAccess() doesn't update until restart.
    # Try creating a listen-only event tap as a probe.
    if Quartz.CGPreflightListenEventAccess():
        return True
    try:
        tap = Quartz.CGEventTapCreate(
            Quartz.kCGSessionEventTap,
            Quartz.kCGHeadInsertEventTap,
            Quartz.kCGEventTapOptionListenOnly,
            Quartz.CGEventMaskBit(Quartz.kCGEventKeyDown),
            lambda proxy, event_type, event, refcon: event,
            None,
        )
        if tap is not None:
            # Clean up the probe tap immediately
            Quartz.CFRelease(tap)
            return True
    except Exception:
        pass
    return False


def _check_accessibility() -> bool:
    from ApplicationServices import AXIsProcessTrusted  # pyright: ignore[reportMissingImports]
    return AXIsProcessTrusted()


def _check_microphone() -> int:
    """Return AVAuthorizationStatus: 0=notDetermined, 1=restricted, 2=denied, 3=authorized."""
    import AVFoundation  # pyright: ignore[reportMissingImports]
    return AVFoundation.AVCaptureDevice.authorizationStatusForMediaType_(AVFoundation.AVMediaTypeAudio)


def _request_input_monitoring():
    Quartz.CGRequestListenEventAccess()


def _open_accessibility_settings():
    subprocess.Popen(["open", "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility"])


def _open_input_monitoring_settings():
    subprocess.Popen(["open", "x-apple.systempreferences:com.apple.preference.security?Privacy_ListenEvent"])


def _open_microphone_settings():
    subprocess.Popen(["open", "x-apple.systempreferences:com.apple.preference.security?Privacy_Microphone"])


# --- UI ---

_GRANTED_STYLE = "color: #4CAF50; font-weight: bold;"
_PENDING_STYLE = "color: #FF9800; font-weight: bold;"
_LABEL_FONT = QFont(".AppleSystemUIFont", 12)
_STATUS_FONT = QFont(".AppleSystemUIFont", 12, QFont.Weight.Bold)


class _PermissionRow(QWidget):
    def __init__(self, label: str, open_fn, btn_text: str = "Open Settings", parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)

        self._label = QLabel(label)
        self._label.setFont(_LABEL_FONT)
        layout.addWidget(self._label)

        layout.addStretch()

        self._status = QLabel("pending")
        self._status.setFont(_STATUS_FONT)
        self._status.setStyleSheet(_PENDING_STYLE)
        layout.addWidget(self._status)

        self._btn = QPushButton(btn_text)
        self._btn.setFixedWidth(110)
        self._btn.clicked.connect(open_fn)
        layout.addWidget(self._btn)

    def set_granted(self):
        self._status.setText("granted")
        self._status.setStyleSheet(_GRANTED_STYLE)
        self._btn.setEnabled(False)
        self._btn.setText("Done")

    @property
    def is_granted(self) -> bool:
        return self._status.text() == "granted"


def _list_input_devices() -> list[dict]:
    """Return list of input audio devices as [{index, name}]."""
    import sounddevice as sd
    devices = sd.query_devices()
    return [
        {"index": i, "name": d["name"]}
        for i, d in enumerate(devices)
        if d["max_input_channels"] > 0
    ]


MODIFIERS = ["Option", "Ctrl", "Cmd", "Shift"]
KEYS = ["Space", "Tab", "Enter", "F1", "F2", "F3", "F4", "F5",
        "F6", "F7", "F8", "F9", "F10", "F11", "F12"]


class WelcomeWindow(QWidget):
    def __init__(self, hotkey_label: str, model_label: str, current_device: str | None = None,
                 current_modifier: str = "option", current_key: str = "space", parent=None):
        super().__init__(parent)
        self.device_changed: Callable[..., None] | None = None  # set by app.py
        self.hotkey_changed: Callable[..., None] | None = None  # set by app.py
        self._hotkey_label = hotkey_label
        self.setWindowTitle("TinyWhisper")
        self.setFixedSize(420, 440)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 20)
        layout.setSpacing(8)

        # Title
        title = QLabel("TinyWhisper")
        title.setFont(QFont(".AppleSystemUIFont", 22, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # Model status
        self._model_status = QLabel(f"Loading {model_label}...")
        self._model_status.setFont(QFont(".AppleSystemUIFont", 12))
        self._model_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._model_status.setStyleSheet("color: #888;")
        layout.addWidget(self._model_status)

        layout.addSpacing(8)

        # Permissions header
        perms_header = QLabel("Permissions")
        perms_header.setFont(QFont(".AppleSystemUIFont", 13, QFont.Weight.Bold))
        layout.addWidget(perms_header)

        # Permission rows
        self._input_row = _PermissionRow("Input Monitoring", self._on_input)
        self._accessibility_row = _PermissionRow("Accessibility", _open_accessibility_settings)
        self._mic_row = _PermissionRow("Microphone", self._request_mic, btn_text="Grant Access")

        layout.addWidget(self._input_row)
        layout.addWidget(self._accessibility_row)
        layout.addWidget(self._mic_row)

        layout.addSpacing(8)

        # Hotkey selector
        hk_header = QLabel("Hotkey")
        hk_header.setFont(QFont(".AppleSystemUIFont", 13, QFont.Weight.Bold))
        layout.addWidget(hk_header)

        hk_row = QHBoxLayout()
        self._mod_combo = QComboBox()
        self._mod_combo.setFont(QFont(".AppleSystemUIFont", 12))
        self._mod_combo.addItems(MODIFIERS)
        self._mod_combo.setCurrentText(current_modifier.capitalize())
        hk_row.addWidget(self._mod_combo)
        plus_label = QLabel("+")
        plus_label.setFont(QFont(".AppleSystemUIFont", 12))
        hk_row.addWidget(plus_label)
        self._key_combo = QComboBox()
        self._key_combo.setFont(QFont(".AppleSystemUIFont", 12))
        self._key_combo.addItems(KEYS)
        self._key_combo.setCurrentText(current_key.capitalize())
        hk_row.addWidget(self._key_combo)
        hk_row.addStretch()
        layout.addLayout(hk_row)

        self._mod_combo.currentIndexChanged.connect(self._on_hotkey_changed)
        self._key_combo.currentIndexChanged.connect(self._on_hotkey_changed)

        layout.addSpacing(8)

        # Audio device selector
        dev_header = QLabel("Audio Input")
        dev_header.setFont(QFont(".AppleSystemUIFont", 13, QFont.Weight.Bold))
        layout.addWidget(dev_header)

        self._device_combo = QComboBox()
        self._device_combo.setFont(QFont(".AppleSystemUIFont", 12))
        self._populate_devices(current_device)
        self._device_combo.currentIndexChanged.connect(self._on_device_changed)
        layout.addWidget(self._device_combo)

        layout.addStretch()

        # GitHub link
        gh_link = QLabel('<a href="https://github.com/juliarvalenti/tinywhisper">github.com/juliarvalenti/tinywhisper</a>')
        gh_link.setFont(QFont(".AppleSystemUIFont", 11))
        gh_link.setAlignment(Qt.AlignmentFlag.AlignCenter)
        gh_link.setOpenExternalLinks(True)
        gh_link.setStyleSheet("color: #888;")
        layout.addWidget(gh_link)

        # Close hint + button
        hint = QLabel("You may close this window.")
        hint.setFont(QFont(".AppleSystemUIFont", 11))
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint.setStyleSheet("color: #666;")
        layout.addWidget(hint)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)
        layout.addWidget(close_btn)

        # Poll permissions every second
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._poll_permissions)
        self._timer.start(1000)

        # Initial check
        self._poll_permissions()

    def _on_input(self):
        _request_input_monitoring()
        _open_input_monitoring_settings()

    def _request_mic(self):
        """Trigger macOS mic permission prompt.

        AVFoundation.requestAccessForMediaType:completionHandler: requires an ObjC
        block with a specific signature that pyobjc struggles with.  Instead, we use
        AVCaptureDeviceInput which reliably triggers the TCC prompt when mic access
        is undetermined.
        """
        import AVFoundation  # pyright: ignore[reportMissingImports]

        status = AVFoundation.AVCaptureDevice.authorizationStatusForMediaType_(
            AVFoundation.AVMediaTypeAudio
        )
        if status == 0:  # notDetermined — trigger the prompt
            try:
                device = AVFoundation.AVCaptureDevice.defaultDeviceWithMediaType_(
                    AVFoundation.AVMediaTypeAudio
                )
                if device is not None:
                    # Creating an AVCaptureDeviceInput triggers the TCC mic prompt
                    _input, _err = AVFoundation.AVCaptureDeviceInput.deviceInputWithDevice_error_(
                        device, None
                    )
                    if _err:
                        log.warning("AVCaptureDeviceInput error: %s", _err)
                else:
                    log.warning("No audio capture device found")
            except Exception as e:
                log.error("Failed to trigger mic permission prompt: %s", e)
        elif status == 2:  # denied — open settings
            _open_microphone_settings()

    def _poll_permissions(self):
        try:
            if not self._input_row.is_granted and _check_input_monitoring():
                self._input_row.set_granted()
                log.info("Input Monitoring permission granted")

            if not self._accessibility_row.is_granted and _check_accessibility():
                self._accessibility_row.set_granted()
                log.info("Accessibility permission granted")

            if not self._mic_row.is_granted and _check_microphone() == 3:
                self._mic_row.set_granted()
                log.info("Microphone permission granted")

            # Stop polling once all granted
            if self._input_row.is_granted and self._accessibility_row.is_granted and self._mic_row.is_granted:
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

    def set_ready(self, hotkey_label: str):
        self._model_status.setText("Model ready")
        self._model_status.setStyleSheet("color: #4CAF50;")

    def set_error(self, msg: str):
        self._model_status.setText(f"Error: {msg}")
        self._model_status.setStyleSheet("color: #F44336;")
