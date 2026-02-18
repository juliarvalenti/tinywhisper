"""Transcription engine abstraction + QThread worker."""

from __future__ import annotations

import logging
import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING

from PyQt6.QtCore import QThread, pyqtSignal

from tinywhisper.config import TranscriptionConfig

if TYPE_CHECKING:
    from tinywhisper.tidier import Tidier

log = logging.getLogger(__name__)


class TranscriptionEngine(ABC):
    @abstractmethod
    def load(self):
        """Pre-load the model into memory."""

    @abstractmethod
    def transcribe(self, wav_path: Path) -> str:
        """Transcribe a WAV file and return the text."""


class ParakeetEngine(TranscriptionEngine):
    def __init__(self, model_name: str):
        self._model_name = model_name
        self._model = None

    def load(self):
        import parakeet_mlx

        self._model = parakeet_mlx.from_pretrained(self._model_name)

    def transcribe(self, wav_path: Path) -> str:
        if self._model is None:
            self.load()
        result = self._model.transcribe(wav_path)  # pyright: ignore[reportOptionalMemberAccess]
        return result.text.strip()


class WhisperEngine(TranscriptionEngine):
    def __init__(self, model_name: str):
        self._model_name = model_name

    def load(self):
        import mlx_whisper  # noqa: F401 — ensures package is importable at startup
        # mlx_whisper doesn't expose a separate load API; model is cached on first use

    def transcribe(self, wav_path: Path) -> str:
        import mlx_whisper

        result = mlx_whisper.transcribe(
            str(wav_path),
            path_or_hf_repo=self._model_name,
        )
        return str(result["text"]).strip()


def create_engine(config: TranscriptionConfig) -> TranscriptionEngine:
    if config.engine == "whisper":
        return WhisperEngine(config.whisper.model)
    return ParakeetEngine(config.parakeet.model)


class TranscriptionWorker(QThread):
    """Runs transcription (and optional tidying) in a background thread."""

    finished = pyqtSignal(str)  # final text (tidied if enabled, otherwise raw)
    raw_finished = pyqtSignal(str)  # raw transcription before tidying
    error = pyqtSignal(str)  # error message
    tidying = pyqtSignal()  # emitted when tidying step starts

    def __init__(
        self,
        engine: TranscriptionEngine,
        wav_path: Path,
        tidier: Tidier | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self._engine = engine
        self._wav_path = wav_path
        self._tidier = tidier

    def run(self):
        try:
            import time
            t0 = time.perf_counter()
            text = self._engine.transcribe(self._wav_path)
            elapsed = time.perf_counter() - t0
            log.info("Transcribed in %.2fs: %s", elapsed, text)
            self.raw_finished.emit(str(text) if text else "")

            if text and self._tidier is not None:
                self.tidying.emit()
                t1 = time.perf_counter()
                text = self._tidier.tidy(text)
                log.info("Tidied in %.2fs: %s", time.perf_counter() - t1, text)

            self.finished.emit(str(text) if text else "")
        except Exception as e:
            log.error("Transcription failed: %s", e)
            self.error.emit(str(e))
        finally:
            try:
                os.unlink(self._wav_path)
            except OSError:
                pass
