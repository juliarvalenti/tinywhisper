"""Entry point for TinyWhisper."""

import fcntl
import logging
import sys
import traceback
from pathlib import Path

from PyQt6.QtWidgets import QApplication

from tinywhisper.config import load_config
from tinywhisper.app import TinyWhisperApp


LOG_PATH = Path.home() / ".config" / "tinywhisper" / "tinywhisper.log"
LOCK_PATH = Path.home() / ".config" / "tinywhisper" / "tinywhisper.lock"

log = logging.getLogger("tinywhisper")


def main():
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

    # Single-instance guard — exit silently if already running
    lock_file = open(LOCK_PATH, "w")
    try:
        fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        sys.exit(0)

    # Use line-buffered UTF-8 writes so tracebacks are flushed before abort()
    log_file = open(LOG_PATH, "a", buffering=1, encoding="utf-8")

    # When launched from Finder (.app), sys.stdout/stderr may be None.
    # Redirect BEFORE any logging or print() calls.
    sys.stdout = log_file
    sys.stderr = log_file

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[logging.FileHandler(LOG_PATH, encoding="utf-8")],
    )
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
