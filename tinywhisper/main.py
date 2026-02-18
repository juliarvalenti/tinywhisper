"""Entry point for TinyWhisper."""

import sys
import traceback

from PyQt6.QtWidgets import QApplication

from tinywhisper.config import load_config
from tinywhisper.app import TinyWhisperApp


def main():
    try:
        config = load_config()
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
