"""Tests for the uv build pipeline.

Validates that uv sync -> build -> run produces a working artifact.
These are NOT unit tests for tinywhisper's functionality — they validate
that the build toolchain produces a correct .app bundle.
"""

from __future__ import annotations

import plistlib
import subprocess
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
VENV = ROOT / ".venv"
APP = ROOT / "TinyWhisper.app"
BINARY = APP / "Contents" / "MacOS" / "TinyWhisper"
INFO_PLIST = APP / "Contents" / "Info.plist"
SITE_PACKAGES = APP / "Contents" / "Resources" / "site-packages"

build = pytest.mark.build


# ── Quick pipeline tests ─────────────────────────────────────────────


def test_uv_sync_creates_venv() -> None:
    """Venv exists and has a valid pyvenv.cfg."""
    assert VENV.is_dir(), f"Expected .venv/ at {VENV}"
    pyvenv_cfg = VENV / "pyvenv.cfg"
    assert pyvenv_cfg.is_file(), "Missing .venv/pyvenv.cfg"


def test_tinywhisper_importable() -> None:
    """The tinywhisper package can be imported."""
    import tinywhisper  # noqa: F401


def test_tinywhisper_entry_point_exists() -> None:
    """The tinywhisper console script exists in .venv/bin/."""
    script = VENV / "bin" / "tinywhisper"
    assert script.exists(), f"Entry point not found at {script}"


# ── Build tests (compile C launcher + validate bundle) ───────────────


@build
def test_build_app_creates_bundle() -> None:
    """build_app.py produces the expected .app directory structure."""
    subprocess.run(
        ["uv", "run", "build_app.py"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    assert APP.is_dir(), f"Expected {APP} to exist"
    assert BINARY.is_file(), f"Expected binary at {BINARY}"
    assert INFO_PLIST.is_file(), f"Expected Info.plist at {INFO_PLIST}"
    assert (APP / "Contents" / "Resources").is_dir(), "Missing Resources/"


@build
def test_launcher_has_python_prefix() -> None:
    """The compiled binary contains a baked-in cpython path (PYTHON_PREFIX)."""
    assert BINARY.is_file(), "Binary not found — run build tests in order"
    result = subprocess.run(
        ["strings", str(BINARY)],
        capture_output=True,
        text=True,
    )
    assert "cpython" in result.stdout.lower() or "python" in result.stdout.lower(), (
        "Binary does not contain a Python prefix string"
    )


@build
def test_bundle_has_site_packages() -> None:
    """The bundle contains a site-packages directory with key packages."""
    assert SITE_PACKAGES.is_dir(), (
        f"Expected site-packages at {SITE_PACKAGES} — "
        "build_app.py should copy venv site-packages into the bundle"
    )
    for pkg in ("tinywhisper", "PyQt6", "mlx", "sounddevice"):
        matches = list(SITE_PACKAGES.glob(f"{pkg}*"))
        assert matches, f"Expected {pkg} in bundled site-packages"


@build
def test_launcher_runs_without_import_error() -> None:
    """The launcher binary starts without an immediate import crash."""
    assert BINARY.is_file(), "Binary not found — run build tests in order"
    proc = subprocess.Popen(
        [str(BINARY)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    # Give it a few seconds to start up — it will try to create a Qt app
    # which will fail in CI (no display), but it should NOT crash with
    # an import error / non-zero exit immediately
    time.sleep(3)
    poll = proc.poll()
    if poll is None:
        # Still running — that's success, it got past imports
        proc.terminate()
        proc.wait(timeout=5)
    else:
        # Exited — check it wasn't an immediate import failure
        _, stderr = proc.communicate()
        # Exit code 0 is fine; non-zero is only bad if it's an ImportError
        if poll != 0 and b"ImportError" in stderr:
            pytest.fail(
                f"Launcher crashed with ImportError (exit {poll}):\n"
                f"{stderr.decode(errors='replace')}"
            )


@build
def test_info_plist_has_correct_bundle_id() -> None:
    """Info.plist contains the expected bundle identifier."""
    assert INFO_PLIST.is_file(), "Info.plist not found — run build tests in order"
    with open(INFO_PLIST, "rb") as f:
        plist = plistlib.load(f)
    assert plist.get("CFBundleIdentifier") == "com.juliarvalenti.tinywhisper", (
        f"Unexpected bundle ID: {plist.get('CFBundleIdentifier')}"
    )
