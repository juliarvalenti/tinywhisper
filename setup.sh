#!/usr/bin/env bash
# setup.sh — Install, build, and launch TinyWhisper with animated progress.
set -euo pipefail

# ── Config ────────────────────────────────────────────────────────────
LOG_DIR="$HOME/.config/tinywhisper"
LOG_FILE="$LOG_DIR/tinywhisper.log"
READY_TIMEOUT=90          # seconds to wait for model load
FRAME_DELAY=0.08

# Audio-wave frames — vertical bars that ripple like a waveform visualizer.
# Uses Unicode block elements: ▁▂▃▅▆▇█ (ascending height).
WAVE_FRAMES=(
    "▁▂▃▅█▅▃▂▁"
    "▂▃▅█▇▃▂▁▂"
    "▃▅█▇▅▂▁▂▃"
    "▅█▇▅▃▁▂▃▅"
    "█▇▅▃▂▂▃▅█"
    "▇▅▃▂▁▃▅█▇"
    "▅▃▂▁▂▅█▇▅"
    "▃▂▁▂▃█▇▅▃"
    "▂▁▂▃▅▇▅▃▂"
    "▁▂▃▅▇▅▃▂▁"
)

# ── Colors ────────────────────────────────────────────────────────────
BOLD="\033[1m"
DIM="\033[2m"
GREEN="\033[32m"
RED="\033[31m"
YELLOW="\033[33m"
CYAN="\033[36m"
RESET="\033[0m"

# ── Helpers ───────────────────────────────────────────────────────────

spin() {
    # Usage: spin PID "message"
    local pid=$1 msg=$2 i=0
    local n=${#WAVE_FRAMES[@]}
    while kill -0 "$pid" 2>/dev/null; do
        printf "\r  ${CYAN}${WAVE_FRAMES[$((i % n))]}${RESET}  %s" "$msg"
        sleep "$FRAME_DELAY"
        i=$((i + 1))
    done
    wait "$pid"
    return $?
}

pass() { printf "\r  ${GREEN}✓${RESET}  %s\n" "$1"; }
fail() { printf "\r  ${RED}✗${RESET}  %s\n" "$1"; }
info() { printf "  ${DIM}%s${RESET}\n" "$1"; }

# ── Banner ────────────────────────────────────────────────────────────

printf "\n${BOLD}  TinyWhisper Setup${RESET}\n"
printf "  ─────────────────\n\n"

# ── Phase 1: Install dependencies ────────────────────────────────────

if ! command -v uv &>/dev/null; then
    fail "uv is not installed"
    info "Install it: https://docs.astral.sh/uv/getting-started/installation/"
    exit 1
fi

uv sync --no-editable &>/dev/null &
spin $! "Installing dependencies..."
pass "Dependencies installed"

# ── Phase 2: Build .app bundle ───────────────────────────────────────

uv run --no-sync build_app.py &>/dev/null &
spin $! "Building TinyWhisper.app..."
pass "TinyWhisper.app built"

# ── Phase 3: Launch and wait for ready ───────────────────────────────

# Quit any running instance so the new build can start fresh.
# The app uses a single-instance lock — a second launch just exits silently,
# so we'd never see "Model loaded." if the old process stayed alive.
if pgrep -f "TinyWhisper" &>/dev/null; then
    pkill -f "TinyWhisper" 2>/dev/null || true
    sleep 1
fi

# Ensure log directory exists and note the current log position.
mkdir -p "$LOG_DIR"
touch "$LOG_FILE"
log_offset=$(wc -c < "$LOG_FILE" | tr -d ' ')

open "$(dirname "$0")/TinyWhisper.app"

elapsed=0
i=0
ready=false

while (( elapsed < READY_TIMEOUT )); do
    printf "\r  ${CYAN}${WAVE_FRAMES[$((i % ${#WAVE_FRAMES[@]}))]}${RESET}  Launching TinyWhisper..."
    sleep "$FRAME_DELAY"
    i=$((i + 1))

    # Only check the log every ~1 second (every 13 frames at 0.08s each).
    if (( i % 13 == 0 )); then
        elapsed=$((elapsed + 1))

        # Check for the ready signal in new log output.
        if tail -c +"$((log_offset + 1))" "$LOG_FILE" 2>/dev/null | grep -q "Model loaded\."; then
            ready=true
            break
        fi

        # Check if the app process crashed (give it a few seconds to start).
        if (( elapsed > 5 )) && ! pgrep -f "TinyWhisper" &>/dev/null; then
            fail "Launching TinyWhisper..."
            printf "\n  ${RED}TinyWhisper appears to have crashed.${RESET}\n"
            info "Check the log: $LOG_FILE"
            exit 1
        fi
    fi
done

if $ready; then
    pass "TinyWhisper is ready!"
    printf "\n  ${GREEN}${BOLD}🎙  Press Option+Space to start recording${RESET}\n\n"
else
    printf "\r  ${YELLOW}⏳${RESET}  TinyWhisper is still loading...\n"
    info "The model is taking longer than expected."
    info "It should be ready soon — check the tray icon."
    info "Log: $LOG_FILE"
    printf "\n"
fi
