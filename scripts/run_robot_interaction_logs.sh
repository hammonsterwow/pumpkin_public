#!/usr/bin/env bash
set -eo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

# Physical ReSpeaker VAD profile.
# Previous defaults (3500 RMS x 7 consecutive 50 ms blocks = 350 ms) were too
# conservative for quiet/short Korean utterances. Keep the existing 0.4 s
# pre-roll and endpoint detector, but let normal speech start after 200 ms and
# short confirmation replies after 100 ms.
export PUMPKIN_STT_SPEECH_THRESHOLD="${PUMPKIN_STT_SPEECH_THRESHOLD:-2800.0}"
export PUMPKIN_STT_SPEECH_START_BLOCKS="${PUMPKIN_STT_SPEECH_START_BLOCKS:-4}"
export PUMPKIN_STT_CONFIRMATION_SPEECH_START_BLOCKS="${PUMPKIN_STT_CONFIRMATION_SPEECH_START_BLOCKS:-2}"

# Preserve the calibrated endpoint values. This change intentionally makes only
# speech onset more sensitive so sentence endings are not cut more aggressively.
export PUMPKIN_STT_END_THRESHOLD="${PUMPKIN_STT_END_THRESHOLD:-1800.0}"
export PUMPKIN_STT_END_CEILING_RATIO="${PUMPKIN_STT_END_CEILING_RATIO:-0.75}"
export PUMPKIN_STT_SILENCE_DURATION="${PUMPKIN_STT_SILENCE_DURATION:-0.6}"

echo "[VAD] normal: rms>=${PUMPKIN_STT_SPEECH_THRESHOLD} x ${PUMPKIN_STT_SPEECH_START_BLOCKS} blocks"
echo "[VAD] confirmation: rms>=${PUMPKIN_STT_SPEECH_THRESHOLD} x ${PUMPKIN_STT_CONFIRMATION_SPEECH_START_BLOCKS} blocks"
echo "[VAD] end: rms<${PUMPKIN_STT_END_THRESHOLD}, silence=${PUMPKIN_STT_SILENCE_DURATION}s"

bash "${ROOT_DIR}/scripts/stop_robot_interaction_nodes.sh"
exec bash "${ROOT_DIR}/scripts/run_robot_interaction_demo.sh"
