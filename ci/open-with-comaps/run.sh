#!/usr/bin/env bash
set -euo pipefail
exec python3 "$(cd "$(dirname "$0")" && pwd)/run.py" "${1:?pass the built CoMaps simulator .app path}"
