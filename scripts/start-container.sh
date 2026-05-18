#!/bin/bash
set -e
# ./minizero/scripts/start-container.sh --image yanrudocker/restnet-go $@
./minizero/scripts/start-container-gpu.sh --image myanrudocker/restnet-go $@