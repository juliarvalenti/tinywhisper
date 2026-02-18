"""Orchestrator: system tray, wires all components together."""

from __future__ import annotations

import logging
import os
import resource
import subprocess
from pathlib import Path

from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QAction, QActionGroup, QFont
from PyQt6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from tinywhisper.clipboard import paste_text
from tinywhisper.config import AppConfig, CONFIG_PATH
from tinywhisper.hotkey import HotkeyListener, request_access
from tinywhisper.icon import create_tray_icon
from tinywhisper.overlay import WaveformOverlay
from tinywhisper.recorder import Recorder
from tinywhisper.settings import SettingsWindow
from tinywhisper.transcriber import TranscriptionWorker, create_engine
from tinywhisper.welcome import (
    WelcomeWindow, _list_input_devices, is_launch_at_startup, set_launch_at_startup,
)

log = logging.getLogger(__name__)

MODEL_LABELS = {
    "parakeet": "Parakeet TDT 0.6b",
    "whisper": "Whisper Large V3 Turbo",
}


def _get_memory_mb() -> int:
    """Get current RSS in MB."""
    usage = resource.getrusage(resource.RUSAGE_SELF)
    return int(usage.ru_maxrss / (1024 * 1024))  # macOS returns bytes


class TinyWhisperApp:
    """Main application orchestrator."""

    def __init__(self, config: AppConfig):
        self._config = config
        self._recording = False
        self._ready = False
        self._worker: TranscriptionWorker | None = None

        # Request Input Monitoring permission (triggers macOS prompt on first run)
        request_access()

        # Transcription engine — created but not loaded yet
        self._engine = create_engine(config.transcription)

        # Optional text tidier (local LLM) — created but not loaded yet
        self._tidier = None
        if config.tidier.enabled:
            from tinywhisper.tidier import Tidier
            self._tidier = Tidier(config.tidier)

        # Components
        self._recorder = Recorder(config.recording)
        self._hotkey = HotkeyListener(config.hotkey.modifier, config.hotkey.key)
        self._overlay = WaveformOverlay(config.overlay) if config.overlay.enabled else None

        # Settings window
        self._settings = SettingsWindow(config)
        self._settings.settings_changed.connect(self._on_settings_changed)
        self._settings.hotkey_changed.connect(self._on_hotkey_changed)

        # System tray
        self._tray = QSystemTrayIcon()
        self._tray.setIcon(create_tray_icon())
        self._tray.setToolTip("TinyWhisper — loading model…")
        self._setup_tray_menu()

        # Welcome screen
        self._welcome = WelcomeWindow(
            self._hotkey_label(), self._model_label(),
            current_device=config.recording.device,
            current_modifier=config.hotkey.modifier,
            current_key=config.hotkey.key,
        )
        self._welcome.device_changed = self._on_device_changed
        self._welcome.hotkey_changed = self._on_welcome_hotkey_changed
        self._welcome.open_settings = self._settings.show

        # Connections
        self._hotkey.toggled.connect(self._on_toggle)
        if self._overlay:
            self._recorder.amplitude.connect(self._overlay.push_amplitude)

    def _model_label(self) -> str:
        return MODEL_LABELS.get(self._config.transcription.engine, self._config.transcription.engine)

    def _hotkey_label(self) -> str:
        return f"{self._config.hotkey.modifier.capitalize()}+{self._config.hotkey.key.capitalize()}"

    def _setup_tray_menu(self):
        menu = QMenu()
        menu.setStyleSheet("""
            QMenu::item:disabled {
                color: #888888;
            }
        """)

        # Font for read-only informational items — italic signals "not an action"
        info_font = QFont()
        info_font.setItalic(True)

        # Status line
        self._status_action = QAction("Ready", menu)
        self._status_action.setEnabled(False)
        self._status_action.setFont(info_font)
        menu.addAction(self._status_action)

        menu.addSeparator()

        # Model info
        self._model_action = QAction(f"Model: {self._model_label()}", menu)
        self._model_action.setEnabled(False)
        self._model_action.setFont(info_font)
        menu.addAction(self._model_action)

        # Tidier toggle
        self._tidier_action = QAction("Tidier", menu)
        self._tidier_action.setCheckable(True)
        self._tidier_action.setChecked(self._config.tidier.enabled)
        self._tidier_action.triggered.connect(self._on_tray_tidier_toggled)
        menu.addAction(self._tidier_action)

        # Memory
        self._memory_action = QAction(f"Memory: {_get_memory_mb()} MB", menu)
        self._memory_action.setEnabled(False)
        self._memory_action.setFont(info_font)
        menu.addAction(self._memory_action)

        # Hotkey
        self._hotkey_action = QAction(f"Hotkey: {self._hotkey_label()}", menu)
        self._hotkey_action.setEnabled(False)
        self._hotkey_action.setFont(info_font)
        menu.addAction(self._hotkey_action)

        # Audio device submenu
        self._device_menu = QMenu("Audio Input", menu)
        menu.addMenu(self._device_menu)
        self._device_menu.aboutToShow.connect(self._refresh_device_menu)

        menu.addSeparator()

        self._startup_action = QAction("Launch at Startup", menu)
        self._startup_action.setCheckable(True)
        self._startup_action.setChecked(is_launch_at_startup())
        self._startup_action.triggered.connect(self._on_startup_toggled)
        menu.addAction(self._startup_action)

        settings_action = QAction("Advanced Settings…", menu)
        settings_action.triggered.connect(self._settings.show)
        menu.addAction(settings_action)

        config_action = QAction("Open Config File…", menu)
        config_action.triggered.connect(self._open_config_file)
        menu.addAction(config_action)

        menu.addSeparator()
        quit_action = QAction("Quit", menu)
        quit_action.triggered.connect(self._quit)
        menu.addAction(quit_action)

        # Refresh memory when menu is about to show
        menu.aboutToShow.connect(self._refresh_tray_info)

        self._tray.setContextMenu(menu)

    def _refresh_tray_info(self):
        self._memory_action.setText(f"Memory: {_get_memory_mb()} MB")
        self._hotkey_action.setText(f"Hotkey: {self._hotkey_label()}")
        self._startup_action.setChecked(is_launch_at_startup())

    def _on_startup_toggled(self, checked: bool):
        set_launch_at_startup(checked)
        self._welcome.refresh_startup()

    def _on_tray_tidier_toggled(self, checked: bool):
        self._config.tidier.enabled = checked
        self._tidier_action.setChecked(checked)
        log.info("Tidier %s via tray", "enabled" if checked else "disabled")

    def _set_status(self, text: str):
        self._status_action.setText(text)

    def start(self):
        """Show tray + welcome, then load model on main thread via deferred call."""
        self._welcome.show()
        self._tray.show()
        self._set_status("Loading model…")
        self._tray.setToolTip("TinyWhisper — loading model…")

        # Defer model load so the welcome screen renders first
        QTimer.singleShot(0, self._load_model)

    def _load_model(self):
        log.info("Loading %s model…", self._config.transcription.engine)
        try:
            self._engine.load()
        except Exception as e:
            log.error("Model load error: %s", e)
            self._set_status("Error loading model")
            self._welcome.set_error(str(e))
            self._tray.showMessage(
                "TinyWhisper",
                f"Failed to load model: {e}",
                QSystemTrayIcon.MessageIcon.Critical,
                5000,
            )
            return

        if self._tidier is not None:
            self._set_status("Loading tidier model…")
            try:
                self._tidier.load()
            except Exception as e:
                log.error("Tidier model load error: %s", e)
                self._tray.showMessage(
                    "TinyWhisper",
                    f"Tidier model failed to load (disabled): {e}",
                    QSystemTrayIcon.MessageIcon.Warning,
                    3000,
                )
                self._tidier = None

        log.info("Model loaded.")
        self._ready = True
        self._set_status("Ready")
        self._tray.setToolTip("TinyWhisper")
        self._hotkey.start()
        tidier_label = self._config.tidier.model.split("/")[-1] if self._tidier else ""
        self._welcome.set_ready(self._hotkey_label(), tidier_label)
        self._tray.showMessage(
            "TinyWhisper",
            f"Ready — press {self._hotkey_label()} to record",
            QSystemTrayIcon.MessageIcon.Information,
            2000,
        )

    def _on_toggle(self):
        try:
            if not self._ready:
                return
            log.debug("Toggle: recording=%s", self._recording)
            if self._recording:
                self._stop_recording()
            else:
                self._start_recording()
        except Exception:
            log.exception("Error in hotkey toggle")

    def _start_recording(self):
        self._recording = True
        self._set_status("Recording…")
        log.info("Recording started")
        if self._overlay:
            self._overlay.show()
        self._recorder.start()

    def _stop_recording(self):
        self._recording = False
        self._set_status("Transcribing…")
        if self._overlay:
            self._overlay.hide()
        wav_path = self._recorder.stop()
        log.info("Recording saved: %s", wav_path)

        # Don't transcribe empty recordings (causes Metal OOM)
        if os.path.getsize(wav_path) < 1000:
            log.info("Skipping empty recording")
            self._set_status("Ready")
            os.unlink(wav_path)
            return

        self._run_transcription(wav_path)

    def _run_transcription(self, wav_path: Path):
        self._worker = TranscriptionWorker(self._engine, wav_path, tidier=self._tidier)
        self._worker.finished.connect(self._on_transcription_done)
        self._worker.error.connect(self._on_transcription_error)
        self._worker.tidying.connect(lambda: self._set_status("Tidying…"))
        self._worker.start()

    def _on_transcription_done(self, text: str):
        try:
            log.info("Transcription done: %s", text)
            self._set_status("Ready")
            if not text:
                self._tray.showMessage(
                    "TinyWhisper", "No speech detected.", QSystemTrayIcon.MessageIcon.Warning, 2000
                )
                return
            paste_text(text)
        except Exception:
            log.exception("Error in transcription done handler")

    def _on_transcription_error(self, msg: str):
        try:
            log.error("Transcription error: %s", msg)
            self._set_status("Error — see notification")
            self._tray.showMessage(
                "TinyWhisper",
                f"Transcription error: {msg}",
                QSystemTrayIcon.MessageIcon.Critical,
                3000,
            )
        except Exception:
            log.exception("Error in transcription error handler")

    def _on_settings_changed(self):
        """Rebuild overlay and tidier with new settings."""
        if self._overlay:
            self._recorder.amplitude.disconnect(self._overlay.push_amplitude)
            self._overlay.close()
        self._overlay = WaveformOverlay(self._config.overlay)
        self._recorder.amplitude.connect(self._overlay.push_amplitude)
        log.info("Settings applied: opacity=%.2f, color=%s, bg=%s",
                 self._config.overlay.opacity, self._config.overlay.color, self._config.overlay.bg_color)

        # Reinitialize tidier with updated settings
        if self._config.tidier.enabled:
            from tinywhisper.tidier import Tidier
            self._tidier = Tidier(self._config.tidier)
            try:
                self._set_status("Loading tidier…")
                self._tidier.load()
                self._set_status("Ready")
                tidier_label = self._config.tidier.model.split("/")[-1]
                self._welcome.set_ready(self._hotkey_label(), tidier_label)
                log.info("Tidier reloaded: %s", self._config.tidier.model)
            except Exception as e:
                log.error("Tidier load error: %s", e)
                self._tidier = None
                self._welcome.set_ready(self._hotkey_label())
        else:
            self._tidier = None
            self._welcome.set_ready(self._hotkey_label())
        self._tidier_action.setChecked(self._config.tidier.enabled)

    def _open_config_file(self):
        """Create config if missing, then open in default editor."""
        if not CONFIG_PATH.exists():
            # Save current config so there's something to open
            self._settings._save()
        subprocess.Popen(["open", str(CONFIG_PATH)])

    def _on_hotkey_changed(self):
        """Update hotkey binding (from settings window)."""
        self._hotkey.update_binding(self._config.hotkey.modifier, self._config.hotkey.key)
        self._hotkey_action.setText(f"Hotkey: {self._hotkey_label()}")
        log.info("Hotkey updated to %s", self._hotkey_label())

    def _on_welcome_hotkey_changed(self, modifier: str, key: str):
        """Update hotkey binding (from welcome screen)."""
        self._config.hotkey.modifier = modifier
        self._config.hotkey.key = key
        self._hotkey.update_binding(modifier, key)
        self._hotkey_action.setText(f"Hotkey: {self._hotkey_label()}")
        log.info("Hotkey updated to %s", self._hotkey_label())

        # Save to config
        import yaml
        data = {}
        if CONFIG_PATH.exists():
            with open(CONFIG_PATH) as f:
                data = yaml.safe_load(f) or {}
        data.setdefault("hotkey", {})["modifier"] = modifier
        data["hotkey"]["key"] = key
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_PATH, "w") as f:
            yaml.dump(data, f, default_flow_style=False)

    def _refresh_device_menu(self):
        """Rebuild the audio device submenu with current devices."""
        self._device_menu.clear()
        group = QActionGroup(self._device_menu)
        group.setExclusive(True)

        current = self._config.recording.device

        # System default option
        default_action = QAction("System Default", self._device_menu)
        default_action.setCheckable(True)
        default_action.setChecked(current is None)
        default_action.triggered.connect(lambda: self._on_device_changed(None))
        group.addAction(default_action)
        self._device_menu.addAction(default_action)

        self._device_menu.addSeparator()

        for dev in _list_input_devices():
            action = QAction(dev["name"], self._device_menu)
            action.setCheckable(True)
            action.setChecked(
                current is not None and current.lower() in dev["name"].lower()
            )
            name = dev["name"]
            action.triggered.connect(lambda checked, n=name: self._on_device_changed(n))
            group.addAction(action)
            self._device_menu.addAction(action)

    def _on_device_changed(self, device_name: str | None):
        """Update recording device in config and save."""
        self._config.recording.device = device_name
        log.info("Audio device changed to: %s", device_name or "System Default")

        # Save to config file
        import yaml
        data = {}
        if CONFIG_PATH.exists():
            with open(CONFIG_PATH) as f:
                data = yaml.safe_load(f) or {}
        data.setdefault("recording", {})["device"] = device_name
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_PATH, "w") as f:
            yaml.dump(data, f, default_flow_style=False)

    def _quit(self):
        self._hotkey.stop()
        if self._overlay:
            self._overlay.close()
        self._tray.hide()
        QApplication.quit()
