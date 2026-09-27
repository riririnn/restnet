#!/bin/bash
# Kept so existing commands still work; see scripts/train_archs.sh.
exec "$(dirname "$0")/train_archs.sh" dobutsu "$@"
