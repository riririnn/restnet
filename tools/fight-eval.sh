#!/bin/bash
set -e

if [ $# -lt 6 ] || [ $(($# % 2)) -eq 1 ];
then
	./minizero/tools/fight-eval.sh --help
else
	./minizero/tools/fight-eval.sh ${@:1:6} --sp_executable_file build/$1/transformer_$1 ${@:7:$#-6}
fi
