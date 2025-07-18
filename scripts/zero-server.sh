#!/bin/bash
set -e

if [ $# -lt 3 ]
then
	./minizero/scripts/zero-server.sh --help
else
	GAME_TYPE=$1
	CONFIGURE_FILE=$2
	END_ITERATION=$3
	shift 3
	./minizero/scripts/zero-server.sh ${GAME_TYPE} ${CONFIGURE_FILE} ${END_ITERATION} --sp_executable_file build/${GAME_TYPE}/restnet_${GAME_TYPE} --op_executable_file restnet/learner/train.py $@
fi