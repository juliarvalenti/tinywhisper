"""Copy text to clipboard and simulate Cmd+V to paste at cursor."""

import time

import pyperclip
from pynput.keyboard import Controller, Key


def paste_text(text: str):
    """Copy text to clipboard and simulate Cmd+V."""
    pyperclip.copy(text)
    time.sleep(0.05)
    kb = Controller()
    kb.press(Key.cmd)
    kb.press("v")
    kb.release("v")
    kb.release(Key.cmd)
