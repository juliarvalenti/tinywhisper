"""Dataclass config + YAML loading from ~/.config/tinywhisper/config.yaml."""

from dataclasses import dataclass, field
from pathlib import Path

import yaml
from dacite import from_dict

CONFIG_DIR = Path.home() / ".config" / "tinywhisper"
CONFIG_PATH = CONFIG_DIR / "config.yaml"


@dataclass
class HotkeyConfig:
    modifier: str = "option"
    key: str = "space"


@dataclass
class ParakeetConfig:
    model: str = "mlx-community/parakeet-tdt-0.6b-v3"


@dataclass
class WhisperConfig:
    model: str = "mlx-community/whisper-large-v3-turbo"


@dataclass
class TranscriptionConfig:
    engine: str = "parakeet"
    parakeet: ParakeetConfig = field(default_factory=ParakeetConfig)
    whisper: WhisperConfig = field(default_factory=WhisperConfig)


@dataclass
class RecordingConfig:
    sample_rate: int = 16000
    channels: int = 1
    device: str | None = None  # audio input device name, None = system default


@dataclass
class OverlayConfig:
    enabled: bool = True
    width: int = 300
    height: int = 60
    position: str = "top-center"
    opacity: float = 0.85
    color: str = "#FF6B6B"
    bg_color: str = "#1E1E1E"


@dataclass
class TidierConfig:
    enabled: bool = False
    model: str = "mlx-community/Qwen2.5-0.5B-Instruct-4bit"
    prompt: str = ""  # empty = use default prompt
    max_tokens: int = 512


@dataclass
class AppConfig:
    hotkey: HotkeyConfig = field(default_factory=HotkeyConfig)
    transcription: TranscriptionConfig = field(default_factory=TranscriptionConfig)
    recording: RecordingConfig = field(default_factory=RecordingConfig)
    overlay: OverlayConfig = field(default_factory=OverlayConfig)
    tidier: TidierConfig = field(default_factory=TidierConfig)
    extra_path: list[str] = field(default_factory=lambda: ["/opt/homebrew/bin", "/usr/local/bin"])


def load_config() -> AppConfig:
    """Load config from YAML file, falling back to defaults."""
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH) as f:
            data = yaml.safe_load(f) or {}
        return from_dict(data_class=AppConfig, data=data)
    return AppConfig()
