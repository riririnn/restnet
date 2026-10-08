#!/bin/bash
set -e

if [ $# -lt 6 ]
then
	./minizero/tools/fight-eval.sh --help
else
	# CONF_FILE2 is optional, so there are six positional arguments or seven.
	# quick-run.sh always passes seven: it fills CONF_FILE2 with CONF_FILE1.
	n=6
	[[ $5 == *.cfg ]] && n=7
	./minizero/tools/fight-eval.sh ${@:1:$n} --sp_executable_file build/$1/restnet_$1 ${@:$((n + 1))}
fi
