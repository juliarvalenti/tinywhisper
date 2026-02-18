"""Entry point for TinyWhisper."""

import logging
import sys
import traceback
from pathlib import Path

from PyQt6.QtWidgets import QApplication

from tinywhisper.config import load_config
from tinywhisper.app import TinyWhisperApp


LOG_PATH = Path.home() / ".config" / "tinywhisper" / "tinywhisper.log"

log = logging.getLogger("tinywhisper")


def main():
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[logging.FileHandler(LOG_PATH), logging.StreamHandler()],
    )
    # Redirect print() to log file (captures library output)
    sys.stdout = open(LOG_PATH, "a")
    sys.stderr = sys.stdout
    try:
        import os
        config = load_config()

        # Extend PATH for .app bundles that don't inherit shell PATH
        if config.extra_path:
            current = os.environ.get("PATH", "")
            extra = os.pathsep.join(p for p in config.extra_path if p not in current)
            if extra:
                os.environ["PATH"] = extra + os.pathsep + current

        qt_app = QApplication(sys.argv)
        qt_app.setQuitOnLastWindowClosed(False)

        app = TinyWhisperApp(config)
        app.start()

        sys.exit(qt_app.exec())
    except Exception:
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
