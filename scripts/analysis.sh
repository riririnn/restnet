#!/bin/bash
set -e

usage(){
    echo "Usage: ./analysis.sh [Game Type] [Model File] [Conf File] [SGF File (optional)]"
}

if [ $# -lt 3 ] || [ $# -gt 4 ]; then
    usage
    exit 0
fi

GAME_TYPE=$1
MODEL_FILE=$2
CONF_FILE=$3
SGF_FILE=${4:-}

op_executable_file=restnet/analysis/console.py
PYTHONPATH=. python ${op_executable_file} ${GAME_TYPE} ${MODEL_FILE} ${CONF_FILE} ${SGF_FILE}