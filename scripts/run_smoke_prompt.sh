#!/usr/bin/env bash
set -euo pipefail

# Simple bounded smoke runner for MUSE.
# Usage:
#   bash ./scripts/run_smoke_prompt.sh A
#   bash ./scripts/run_smoke_prompt.sh B
#   bash ./scripts/run_smoke_prompt.sh C
#   bash ./scripts/run_smoke_prompt.sh A my_custom_run_id

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_DIR"

PROMPT_KEY="${1:-A}"
RUN_ID="${2:-}"
SEED="4242"
DURATION_BARS="16"
PYTHON_EXE="./.venv/Scripts/python.exe"
EMPTY_INSTRUMENTS_DIR="./output/_smoke_empty_instruments"
LOG_DIR="./output/_smoke/logs"

mkdir -p "$LOG_DIR" "$EMPTY_INSTRUMENTS_DIR"

case "$PROMPT_KEY" in
  A|a)
    RUN_ID="${RUN_ID:-prompt_A_20260404}"
    REFERENCE=""
    PROMPT="authentic neo-soul groove with drums, bass, rhodes, muted guitar lead, warm pad, and FX swells at 88 BPM in D minor. warm, controlled transients, vinyl softness, no harsh top-end. 16 bars."
    ;;
  B|b)
    RUN_ID="${RUN_ID:-prompt_B_20260404}"
    REFERENCE="./output/neo_soul_88bpm_Dminor_20260318_120935.wav"
    PROMPT="authentic neo-soul groove with drums, bass, rhodes, muted guitar lead, warm pad, and FX swells at 88 BPM in D minor. preserve the harmonic feel and musical identity of the reference while generating a fresh arrangement. warm, controlled transients, vinyl softness, no harsh top-end. 16 bars."
    ;;
  C|c)
    RUN_ID="${RUN_ID:-prompt_C_20260404}"
    REFERENCE="./output/lofi_75.0bpm_Aminor_20260121_093316.wav"
    PROMPT="laid-back lofi groove with dusty drums, mellow bass, soft keys, gentle pad, and subtle texture at 75 BPM in A minor. preserve the groove feel of the reference while generating a fresh arrangement. soft transients, rounded top-end, intimate mix. 16 bars."
    ;;
  *)
    echo "Usage: bash ./scripts/run_smoke_prompt.sh [A|B|C] [optional_run_id]" >&2
    exit 1
    ;;
esac

OUT_DIR="./output/_smoke/$RUN_ID"
STDOUT_LOG="$LOG_DIR/$RUN_ID.stdout.log"
STDERR_LOG="$LOG_DIR/$RUN_ID.stderr.log"
mkdir -p "$OUT_DIR"

if [[ ! -f "$PYTHON_EXE" ]]; then
  echo "ERROR: Python not found at $PYTHON_EXE" >&2
  exit 1
fi

ARGS=(
  "./main.py"
  "$PROMPT"
  "--seed" "$SEED"
  "--duration-bars" "$DURATION_BARS"
  "--output" "$OUT_DIR"
  "-v"
  "--no-signals"
  "-i" "$EMPTY_INSTRUMENTS_DIR"
)

if [[ -n "$REFERENCE" ]]; then
  if [[ ! -f "$REFERENCE" ]]; then
    echo "ERROR: Reference file not found: $REFERENCE" >&2
    exit 1
  fi
  ARGS+=("--reference" "$REFERENCE")
fi

"$PYTHON_EXE" "${ARGS[@]}" >"$STDOUT_LOG" 2>"$STDERR_LOG" &
PID=$!

echo "PID=$PID"
echo "RUN_ID=$RUN_ID"
echo "OUT=$OUT_DIR"
echo "STDOUT=$STDOUT_LOG"
echo "STDERR=$STDERR_LOG"
echo
echo "Monitor with:"
echo "  ps -p $PID"
echo "  tail -n 80 -f $STDOUT_LOG"
echo "  tail -n 80 -f $STDERR_LOG"
