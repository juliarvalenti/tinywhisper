#!/usr/bin/env python3
"""Build TinyWhisper.app — native macOS .app with embedded Python.

Compiles a small C launcher that loads Python in-process, so macOS sees
the running binary as 'TinyWhisper' and grants Input Monitoring / Accessibility
permissions to it directly (no need to whitelist Python or your terminal).

Usage:
    uv run build_app.py
    open TinyWhisper.app
    cp -r TinyWhisper.app /Applications/   # optional
"""

import shutil
import site
import subprocess
import sys
import sysconfig
import time
from pathlib import Path

APP_NAME = "TinyWhisper"
BUNDLE_ID = "app.tinywhisper"
VERSION = "0.1.0"

ROOT = Path(__file__).parent
APP = ROOT / f"{APP_NAME}.app"
CONTENTS = APP / "Contents"
MACOS = CONTENTS / "MacOS"
RESOURCES = CONTENTS / "Resources"

INFO_PLIST = f"""\
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleName</key>
    <string>{APP_NAME}</string>
    <key>CFBundleDisplayName</key>
    <string>{APP_NAME}</string>
    <key>CFBundleIdentifier</key>
    <string>{BUNDLE_ID}</string>
    <key>CFBundleVersion</key>
    <string>{VERSION}</string>
    <key>CFBundleShortVersionString</key>
    <string>{VERSION}</string>
    <key>CFBundleExecutable</key>
    <string>{APP_NAME}</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>LSMinimumSystemVersion</key>
    <string>13.0</string>
    <key>LSUIElement</key>
    <true/>
    <key>NSHighResolutionCapable</key>
    <true/>
    <key>CFBundleIconFile</key>
    <string>TinyWhisper</string>
    <key>NSMicrophoneUsageDescription</key>
    <string>TinyWhisper needs microphone access to record and transcribe your voice.</string>
</dict>
</plist>
"""


def build():
    # Clean previous build
    if APP.exists():
        shutil.rmtree(APP)

    # Create structure
    MACOS.mkdir(parents=True)
    RESOURCES.mkdir(parents=True)

    # Write Info.plist
    (CONTENTS / "Info.plist").write_text(INFO_PLIST)

    # Copy app icon
    icns = ROOT / "TinyWhisper.icns"
    if icns.exists():
        shutil.copy2(icns, RESOURCES / "TinyWhisper.icns")

    # Compile native launcher
    inc = sysconfig.get_path("include")
    framework = Path(inc).parent.parent  # e.g. .../Python.framework/Versions/3.12
    lib_dir = framework / "lib"
    ver = sysconfig.get_python_version()  # e.g. "3.12"

    launcher_c = ROOT / "launcher.c"
    launcher_bin = MACOS / APP_NAME

    # Python prefix — use installed_base so we always get the real Python
    # (not the venv), which is what PYTHONHOME needs for stdlib access
    prefix = sysconfig.get_config_var("installed_base")

    clang_args = [
        "clang",
        "-arch", "arm64",
        "-o", str(launcher_bin),
        f"-I{inc}",
        f"-L{lib_dir}",
        f"-lpython{ver}",
        f'-DPYTHON_PREFIX="{prefix}"',
        "-framework", "CoreFoundation",
        "-Wno-deprecated-declarations",
        str(launcher_c),
    ]

    # Detect venv site-packages for bundling
    in_venv = sys.prefix != sys.base_prefix
    if in_venv:
        venv_site_packages = site.getsitepackages()[0]
        print(f"  Venv detected: {sys.prefix}")
        print(f"  Site-packages: {venv_site_packages}")

    subprocess.run(clang_args, check=True)

    # Copy site-packages into bundle so the .app is self-contained
    # (avoids TCC Documents prompt when repo lives under ~/Documents/)
    if in_venv:
        dest = RESOURCES / "site-packages"
        print(f"  Copying site-packages into bundle...")
        t0 = time.monotonic()
        shutil.copytree(
            venv_site_packages,
            dest,
            ignore=shutil.ignore_patterns(
                "__pycache__", "*.pyc", "*.pth", "_virtualenv.*",
            ),
        )
        elapsed = time.monotonic() - t0
        size_mb = sum(f.stat().st_size for f in dest.rglob("*") if f.is_file()) / 1e6
        print(f"  Copied site-packages ({size_mb:.0f} MB) in {elapsed:.1f}s")

    # Ad-hoc codesign
    subprocess.run(
        ["codesign", "--force", "--deep", "--sign", "-", str(APP)],
        check=True,
    )

    # Reset TCC permissions so the fresh build gets clean permission prompts
    # (macOS only — tccutil doesn't exist on Linux/CI, ignore failure)
    subprocess.run(["tccutil", "reset", "All", BUNDLE_ID], check=False)

    print(f"Built {APP}")
    print(f"  Python: {framework}")
    if in_venv:
        print("  Site-packages bundled into Resources/")
    print()
    print("To launch:")
    print(f"  open {APP}")
    print()
    print("To install to /Applications:")
    print(f"  cp -r {APP} /Applications/")


if __name__ == "__main__":
    build()

