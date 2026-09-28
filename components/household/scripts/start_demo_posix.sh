#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
export PYTHONDONTWRITEBYTECODE=1
python3 -m jarvis.cli doctor
python3 -m jarvis.cli --state "$HOME/.local/share/kintsugi-jarvis/demo-3_2" demo --serve
