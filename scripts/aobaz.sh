#!/bin/bash
# AobaZero (aobaz) as a USI engine for usi_bridge.py, which starts engines
# without arguments: the weights and playouts come from the environment.
#
#   AOBAZ          path to aobaz (built with CPU_ONLY = 1)
#   AOBAZ_WEIGHTS  weight file, e.g. .../w000000000050.txt (unpacked from .xz)
#   AOBAZ_PLAYOUTS playouts per move (default 800, as on the AobaZero page)
#
# One thread and no -n / -m, so aobaz plays the same move in the same position.
exec "${AOBAZ:?}" -q -i -t 1 -p "${AOBAZ_PLAYOUTS:-800}" -w "${AOBAZ_WEIGHTS:?}"
