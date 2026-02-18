#!/usr/bin/env python3
"""Build TinyWhisper.app — native macOS .app with embedded Python.

Compiles a small C launcher that loads Python in-process, so macOS sees
the running binary as 'TinyWhisper' and grants Input Monitoring / Accessibility
permissions to it directly (no need to whitelist Python or your terminal).

Usage:
    python3 build_app.py
    open TinyWhisper.app
    cp -r TinyWhisper.app /Applications/   # optional
"""

import argparse
import shutil
import subprocess
import sysconfig
from pathlib import Path

APP_NAME = "TinyWhisper"
BUNDLE_ID = "com.juliarvalenti.tinywhisper"
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

    # Python prefix (e.g. .../Python.framework/Versions/3.12 or .pyenv/versions/3.12.0)
    prefix = sysconfig.get_config_var("prefix")

    subprocess.run(
        [
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
        ],
        check=True,
    )

    # Ad-hoc codesign
    subprocess.run(
        ["codesign", "--force", "--deep", "--sign", "-", str(APP)],
        check=True,
    )

    print(f"Built {APP}")
    print(f"  Python: {framework}")
    print()
    print("To launch:")
    print(f"  open {APP}")
    print()
    print("To install to /Applications:")
    print(f"  cp -r {APP} /Applications/")


def reset_permissions():
    subprocess.run(["tccutil", "reset", "All", BUNDLE_ID], check=True)
    print(f"Permissions reset for {BUNDLE_ID}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset-perms", action="store_true",
                        help="Reset macOS TCC permissions for the app bundle")
    args = parser.parse_args()

    if args.reset_perms:
        reset_permissions()
    else:
        build()
