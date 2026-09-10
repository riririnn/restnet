#!/bin/bash
set -e

if [ $# -lt 5 ] || [ $(($# % 2)) -eq 0 ];
then
	./minizero/tools/self-eval.sh --help
else
	./minizero/tools/self-eval.sh ${@:1:5} --sp_executable_file build/$1/restnet_$1 ${@:6:$#-5}
fi
