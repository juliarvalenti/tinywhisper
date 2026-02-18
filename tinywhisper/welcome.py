"""Welcome / options screen."""

import logging
import subprocess
from collections.abc import Callable
from pathlib import Path

import Quartz  # pyright: ignore[reportMissingImports]
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QPixmap
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
# Git / version info
# ---------------------------------------------------------------------------

def _get_version() -> str:
    try:
        from importlib.metadata import version
        return version("tinywhisper")
    except Exception:
        return "0.1.0"


def _get_git_commit() -> str:
    try:
        repo = Path(__file__).parent.parent
        return subprocess.check_output(
            ["git", "-C", str(repo), "rev-parse", "--short", "HEAD"],
            stderr=subprocess.DEVNULL,
        ).decode().strip()
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# UI constants
# ---------------------------------------------------------------------------

MODIFIERS = ["Option", "Ctrl", "Cmd", "Shift"]
KEYS = ["Space", "Tab", "Enter", "F1", "F2", "F3", "F4", "F5",
        "F6", "F7", "F8", "F9", "F10", "F11", "F12"]

_FONT = QFont(".AppleSystemUIFont", 12)
_BOLD = QFont(".AppleSystemUIFont", 12, QFont.Weight.Bold)
_SMALL = QFont(".AppleSystemUIFont", 11)
_TINY = QFont(".AppleSystemUIFont", 10)
_LABEL_W = 130  # fixed width for left-column labels


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


def _vdivider() -> QFrame:
    line = QFrame()
    line.setFrameShape(QFrame.Shape.VLine)
    line.setStyleSheet("color: rgba(128,128,128,0.20);")
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
# Model status row (right panel)
# ---------------------------------------------------------------------------

class _ModelRow(QWidget):
    def __init__(self, label: str, parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 3, 0, 3)
        lay.setSpacing(6)

        self._dot = QLabel("●")
        self._dot.setFont(_SMALL)
        self._dot.setStyleSheet("color: #888;")
        lay.addWidget(self._dot)

        self._label = QLabel(label)
        self._label.setFont(_SMALL)
        lay.addWidget(self._label, 1)

        self._status = QLabel("loading…")
        self._status.setFont(_TINY)
        self._status.setStyleSheet("color: #888;")
        lay.addWidget(self._status)

    def set_loading(self, text: str = "loading…"):
        self._dot.setStyleSheet("color: #FF9800;")
        self._status.setText(text)
        self._status.setStyleSheet("color: #888;")

    def set_ready(self):
        self._dot.setStyleSheet("color: #4CAF50;")
        self._status.setText("ready")
        self._status.setStyleSheet("color: #4CAF50;")

    def set_error(self, msg: str = "error"):
        self._dot.setStyleSheet("color: #F44336;")
        self._status.setText(msg)
        self._status.setStyleSheet("color: #F44336;")

    def set_disabled(self):
        self._dot.setStyleSheet("color: #555;")
        self._status.setText("disabled")
        self._status.setStyleSheet("color: #555;")


# ---------------------------------------------------------------------------
# Welcome / options window
# ---------------------------------------------------------------------------

class WelcomeWindow(QWidget):
    def __init__(
        self,
        hotkey_label: str,
        model_label: str,
        tidier_label: str = "",
        current_device: str | None = None,
        current_modifier: str = "option",
        current_key: str = "space",
        parent=None,
    ):
        super().__init__(parent)
        self.device_changed: Callable[..., None] | None = None  # set by app.py
        self.hotkey_changed: Callable[..., None] | None = None  # set by app.py
        self.open_settings: Callable[[], None] | None = None   # set by app.py
        self.setWindowTitle("TinyWhisper")
        self.setFixedWidth(760)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Header ──────────────────────────────────────────────────────────
        header_widget = QWidget()
        header_widget.setStyleSheet("background: transparent;")
        header_lay = QHBoxLayout(header_widget)
        header_lay.setContentsMargins(24, 18, 24, 12)
        header_lay.setSpacing(12)

        icon_lbl = QLabel()
        icon_path = Path(__file__).parent / "icon.png"
        icon_px = QPixmap(str(icon_path))
        if not icon_px.isNull():
            icon_px = icon_px.scaled(
                48, 48,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            icon_lbl.setPixmap(icon_px)
        icon_lbl.setFixedSize(48, 48)
        header_lay.addWidget(icon_lbl)

        title = QLabel("TinyWhisper")
        title.setFont(QFont(".AppleSystemUIFont", 18, QFont.Weight.Bold))
        header_lay.addWidget(title)
        header_lay.addStretch()
        root.addWidget(header_widget)
        root.addWidget(_divider())

        # ── Body (two columns) ───────────────────────────────────────────────
        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)

        # ── Left panel ───────────────────────────────────────────────────────
        left = QWidget()
        left_lay = QVBoxLayout(left)
        left_lay.setContentsMargins(24, 20, 20, 20)
        left_lay.setSpacing(0)

        # Permissions
        left_lay.addWidget(_section_label("Permissions"))
        left_lay.addSpacing(10)
        self._input_row = _PermRow("Input Monitoring", self._on_input)
        self._access_row = _PermRow("Accessibility", _open_accessibility_settings)
        self._mic_row = _PermRow("Microphone", self._request_mic, btn_text="Grant Access")
        left_lay.addWidget(self._input_row)
        left_lay.addWidget(self._access_row)
        left_lay.addWidget(self._mic_row)

        left_lay.addSpacing(16)
        left_lay.addWidget(_divider())
        left_lay.addSpacing(16)

        # Options
        left_lay.addWidget(_section_label("Options"))
        left_lay.addSpacing(10)

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
        left_lay.addLayout(_opt_row("Hotkey", hk_widget))
        left_lay.addSpacing(8)

        # Audio input
        self._device_combo = QComboBox()
        self._device_combo.setFont(_FONT)
        self._populate_devices(current_device)
        left_lay.addLayout(_opt_row("Audio Input", self._device_combo))
        left_lay.addSpacing(8)

        # Launch at startup
        self._startup_check = QCheckBox()
        self._startup_check.setChecked(is_launch_at_startup())
        left_lay.addLayout(_opt_row("Launch at Startup", self._startup_check))
        body.addWidget(left, 3)

        # ── Vertical divider ─────────────────────────────────────────────────
        body.addWidget(_vdivider())

        # ── Right panel ──────────────────────────────────────────────────────
        right = QWidget()
        right_lay = QVBoxLayout(right)
        right_lay.setContentsMargins(20, 20, 24, 20)
        right_lay.setSpacing(0)

        # Model status
        right_lay.addWidget(_section_label("Model Status"))
        right_lay.addSpacing(10)

        self._transcription_row = _ModelRow(model_label)
        self._transcription_row.set_loading()
        right_lay.addWidget(self._transcription_row)

        if tidier_label:
            self._tidier_row: _ModelRow | None = _ModelRow(tidier_label)
            self._tidier_row.set_loading()
        else:
            self._tidier_row = _ModelRow("Tidier")
            self._tidier_row.set_disabled()
        right_lay.addWidget(self._tidier_row)

        right_lay.addSpacing(16)
        right_lay.addWidget(_divider())
        right_lay.addSpacing(16)

        # Git / version
        right_lay.addWidget(_section_label("Version"))
        right_lay.addSpacing(10)

        version = _get_version()
        commit = _get_git_commit()
        ver_text = f"v{version}"
        if commit:
            ver_text += f"  ·  {commit}"
        ver_lbl = QLabel(ver_text)
        ver_lbl.setFont(_SMALL)
        right_lay.addWidget(ver_lbl)

        gh = QLabel('<a href="https://github.com/juliarvalenti/tinywhisper">github.com/juliarvalenti/tinywhisper</a>')
        gh.setFont(_SMALL)
        gh.setOpenExternalLinks(True)
        gh.setStyleSheet("color: #888;")
        right_lay.addWidget(gh)

        right_lay.addSpacing(16)
        right_lay.addWidget(_divider())
        right_lay.addSpacing(16)

        # License
        right_lay.addWidget(_section_label("License"))
        right_lay.addSpacing(10)

        mit = QLabel("MIT License")
        mit.setFont(_SMALL)
        right_lay.addWidget(mit)

        copy_lbl = QLabel("Copyright © 2025 Julia Valenti")
        copy_lbl.setFont(_TINY)
        copy_lbl.setStyleSheet("color: #888;")
        right_lay.addWidget(copy_lbl)

        perm_lbl = QLabel(
            "Permission is hereby granted, free of charge, to any person\n"
            "obtaining a copy of this software to use, copy, modify, merge,\n"
            "publish, distribute, sublicense, and/or sell copies."
        )
        perm_lbl.setFont(_TINY)
        perm_lbl.setStyleSheet("color: #666;")
        perm_lbl.setWordWrap(True)
        right_lay.addSpacing(6)
        right_lay.addWidget(perm_lbl)
        body.addWidget(right, 2)

        root.addLayout(body, 1)
        root.addWidget(_divider())

        # ── Footer ───────────────────────────────────────────────────────────
        footer_widget = QWidget()
        footer_lay = QHBoxLayout(footer_widget)
        footer_lay.setContentsMargins(24, 10, 24, 14)
        footer_lay.addStretch()
        settings_btn = QPushButton("Advanced Settings…")
        settings_btn.setFont(_SMALL)
        settings_btn.clicked.connect(self._open_settings)
        footer_lay.addWidget(settings_btn)
        close_btn = QPushButton("Close")
        close_btn.setFont(_SMALL)
        close_btn.clicked.connect(self.close)
        footer_lay.addWidget(close_btn)
        root.addWidget(footer_widget)

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

    def set_ready(self, hotkey_label: str, tidier_label: str = ""):
        self._transcription_row.set_ready()
        if tidier_label:
            self._tidier_row = _ModelRow(tidier_label) if self._tidier_row is None else self._tidier_row
            self._tidier_row._label.setText(tidier_label)
            self._tidier_row.set_ready()
        else:
            if self._tidier_row:
                self._tidier_row.set_disabled()

    def set_error(self, msg: str):
        self._transcription_row.set_error(msg)

    def set_tidier_error(self, msg: str):
        if self._tidier_row:
            self._tidier_row.set_error(msg)

    def refresh_startup(self):
        """Sync checkbox with actual system state (e.g. after tray toggle)."""
        self._startup_check.blockSignals(True)
        self._startup_check.setChecked(is_launch_at_startup())
        self._startup_check.blockSignals(False)
