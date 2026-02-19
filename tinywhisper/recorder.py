"""Audio recording via sounddevice + WAV export."""

import logging
import tempfile
import threading
from pathlib import Path

import numpy as np
import sounddevice as sd
import soundfile as sf
from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from tinywhisper.config import RecordingConfig

log = logging.getLogger(__name__)


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

        # Resolve device: config name -> device index, or None for default
        device = None
        if self._config.device:
            try:
                devices = sd.query_devices()
                for i, d in enumerate(devices):
                    if self._config.device.lower() in d['name'].lower() and d['max_input_channels'] > 0:
                        device = i
                        break
                if device is not None:
                    log.info("Using audio device: %s", devices[device]['name'])
                else:
                    log.warning("Configured device '%s' not found, using default", self._config.device)
            except Exception:
                pass

        if device is None:
            default_dev = sd.query_devices(kind='input')
            log.info("Using default audio device: %s", default_dev['name'])

        # Ensure any previous stream is fully closed
        if self._stream is not None:
            stream = self._stream
            self._stream = None
            t = threading.Thread(target=self._close_stream, args=(stream,), daemon=True)
            t.start()
            t.join(timeout=2.0)

        self._stream = sd.InputStream(
            samplerate=self._config.sample_rate,
            channels=self._config.channels,
            dtype="float32",
            device=device,
            callback=self._audio_callback,
        )
        self._stream.start()
        self._poll_timer.start()

    def stop(self) -> Path:
        """Stop capturing and save to a temporary WAV file. Returns the file path."""
        self._poll_timer.stop()
        if self._stream is not None:
            stream = self._stream
            self._stream = None
            # Close on a helper thread to avoid a CoreAudio mutex deadlock:
            # the main thread calling abort()+close() can deadlock with the
            # IO thread's startStopCallback when both compete for the same
            # HAL mutex.
            t = threading.Thread(target=self._close_stream, args=(stream,), daemon=True)
            t.start()
            t.join(timeout=2.0)

        audio = np.concatenate(self._chunks) if self._chunks else np.zeros((0, 1), dtype="float32")
        self._chunks.clear()

        duration = len(audio) / self._config.sample_rate
        log.info("Recorded %.2fs of audio (%d samples)", duration, len(audio))

        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        sf.write(tmp.name, audio, self._config.sample_rate)
        return Path(tmp.name)

    def _audio_callback(self, indata: np.ndarray, frames, time_info, status):
        if status:
            log.warning("PortAudio status: %s", status)
        self._chunks.append(indata.copy())
        self._latest_rms = float(np.sqrt(np.mean(indata ** 2)))

    @staticmethod
    def _close_stream(stream: sd.InputStream) -> None:
        try:
            stream.abort()
            stream.close()
        except Exception:
            pass

    def _emit_amplitude(self):
        self.amplitude.emit(self._latest_rms)
