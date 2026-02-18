"""Orchestrator: system tray, wires all components together."""

from __future__ import annotations

import os
import resource
import subprocess
from pathlib import Path

from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from tinywhisper.clipboard import paste_text
from tinywhisper.config import AppConfig, CONFIG_DIR, CONFIG_PATH
from tinywhisper.hotkey import HotkeyListener
from tinywhisper.icon import create_tray_icon
from tinywhisper.overlay import WaveformOverlay
from tinywhisper.recorder import Recorder
from tinywhisper.settings import SettingsWindow
from tinywhisper.transcriber import TranscriptionWorker, create_engine

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
        self._worker: TranscriptionWorker | None = None

        # Transcription engine — preload model
        self._engine = create_engine(config.transcription)
        print(f"Loading {config.transcription.engine} model…", flush=True)
        self._engine.load()
        print("Model loaded.", flush=True)

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
        self._tray.setToolTip("TinyWhisper")
        self._setup_tray_menu()

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

        # Status line
        self._status_action = QAction("Ready", menu)
        self._status_action.setEnabled(False)
        menu.addAction(self._status_action)

        menu.addSeparator()

        # Model info
        self._model_action = QAction(f"Model: {self._model_label()}", menu)
        self._model_action.setEnabled(False)
        menu.addAction(self._model_action)

        # Memory
        self._memory_action = QAction(f"Memory: {_get_memory_mb()} MB", menu)
        self._memory_action.setEnabled(False)
        menu.addAction(self._memory_action)

        # Hotkey
        self._hotkey_action = QAction(f"Hotkey: {self._hotkey_label()}", menu)
        self._hotkey_action.setEnabled(False)
        menu.addAction(self._hotkey_action)

        menu.addSeparator()
        settings_action = QAction("Settings…", menu)
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

    def _set_status(self, text: str):
        self._status_action.setText(text)

    def start(self):
        """Start hotkey listener and show tray icon."""
        self._hotkey.start()
        self._tray.show()
        self._tray.showMessage(
            "TinyWhisper",
            f"Ready — press {self._hotkey_label()} to record",
            QSystemTrayIcon.MessageIcon.Information,
            2000,
        )

    def _on_toggle(self):
        print(f"[toggle] recording={self._recording}", flush=True)
        if self._recording:
            self._stop_recording()
        else:
            self._start_recording()

    def _start_recording(self):
        self._recording = True
        self._set_status("Recording…")
        print("[start] recording", flush=True)
        if self._overlay:
            self._overlay.show()
        self._recorder.start()

    def _stop_recording(self):
        self._recording = False
        self._set_status("Transcribing…")
        if self._overlay:
            self._overlay.hide()
        wav_path = self._recorder.stop()
        print(f"[stop] saved {wav_path}", flush=True)
        self._run_transcription(wav_path)

    def _run_transcription(self, wav_path: Path):
        self._worker = TranscriptionWorker(self._engine, wav_path)
        self._worker.finished.connect(self._on_transcription_done)
        self._worker.error.connect(self._on_transcription_error)
        self._worker.start()

    def _on_transcription_done(self, text: str):
        print(f"[transcription] done: {text!r}", flush=True)
        self._set_status("Ready")
        if not text:
            self._tray.showMessage(
                "TinyWhisper", "No speech detected.", QSystemTrayIcon.MessageIcon.Warning, 2000
            )
            return
        print("[paste] pasting text", flush=True)
        paste_text(text)

    def _on_transcription_error(self, msg: str):
        print(f"[transcription] error: {msg}", flush=True)
        self._set_status("Error — see notification")
        self._tray.showMessage(
            "TinyWhisper",
            f"Transcription error: {msg}",
            QSystemTrayIcon.MessageIcon.Critical,
            3000,
        )

    def _on_settings_changed(self):
        """Rebuild overlay with new settings."""
        if self._overlay:
            self._recorder.amplitude.disconnect(self._overlay.push_amplitude)
            self._overlay.close()
        self._overlay = WaveformOverlay(self._config.overlay)
        self._recorder.amplitude.connect(self._overlay.push_amplitude)
        print(f"[settings] applied: opacity={self._config.overlay.opacity}, color={self._config.overlay.color}, bg={self._config.overlay.bg_color}", flush=True)

    def _open_config_file(self):
        """Create config if missing, then open in default editor."""
        if not CONFIG_PATH.exists():
            # Save current config so there's something to open
            self._settings._save()
        subprocess.Popen(["open", str(CONFIG_PATH)])

    def _on_hotkey_changed(self):
        """Update hotkey binding."""
        self._hotkey.update_binding(self._config.hotkey.modifier, self._config.hotkey.key)
        self._hotkey_action.setText(f"Hotkey: {self._hotkey_label()}")
        print(f"[hotkey] updated to {self._hotkey_label()}", flush=True)

    def _quit(self):
        self._hotkey.stop()
        if self._overlay:
            self._overlay.close()
        self._tray.hide()
        QApplication.quit()
