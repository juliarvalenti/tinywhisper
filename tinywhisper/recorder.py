"""Audio recording via sounddevice + WAV export."""

import tempfile
from pathlib import Path

import numpy as np
import sounddevice as sd
import soundfile as sf
from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from tinywhisper.config import RecordingConfig


class Recorder(QObject):
    """Records audio from the default input device, emitting amplitude for the overlay."""

    amplitude = pyqtSignal(object)  # float: current RMS amplitude

    def __init__(self, config: RecordingConfig, parent=None):
        super().__init__(parent)
        self._config = config
        self._chunks: list[np.ndarray] = []
        self._stream: sd.InputStream | None = None
        self._latest_rms: float = 0.0

        # Poll amplitude from main thread instead of emitting from PortAudio callback
        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(33)  # ~30fps
        self._poll_timer.timeout.connect(self._emit_amplitude)

    def start(self):
        """Start capturing audio."""
        self._chunks.clear()
        self._latest_rms = 0.0
        self._stream = sd.InputStream(
            samplerate=self._config.sample_rate,
            channels=self._config.channels,
            dtype="float32",
            callback=self._audio_callback,
        )
        self._stream.start()
        self._poll_timer.start()

    def stop(self) -> Path:
        """Stop capturing and save to a temporary WAV file. Returns the file path."""
        self._poll_timer.stop()
        if self._stream is not None:
            try:
                self._stream.abort()  # abort is non-blocking, stop() can deadlock
                self._stream.close()
            except Exception:
                pass
            self._stream = None

        audio = np.concatenate(self._chunks) if self._chunks else np.zeros((0, 1), dtype="float32")
        self._chunks.clear()

        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        sf.write(tmp.name, audio, self._config.sample_rate)
        return Path(tmp.name)

    def _audio_callback(self, indata: np.ndarray, frames, time_info, status):
        self._chunks.append(indata.copy())
        self._latest_rms = float(np.sqrt(np.mean(indata ** 2)))

    def _emit_amplitude(self):
        self.amplitude.emit(self._latest_rms)
