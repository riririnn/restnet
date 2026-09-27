#!/bin/bash
# Kept so existing commands still work; see scripts/gen_arch_configs.sh.
exec "$(dirname "$0")/gen_arch_configs.sh" dobutsu "$@"
