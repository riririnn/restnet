#!/bin/bash
set -e

usage(){
    echo "Usage: ./playing-performance-go.sh [Game Type] [Board Size] [Model File] [Configuration File] [Opponent's Command] [GPU List] [Num Games] [Save Folder]"
}


echo $9

if [ $# -ne 8 ];
then
    usage
    exit 0
fi


GAME_TYPE=$1
BOARD_SIZE=$2
MODEL1=$3
CONF_FILE1=$4
OPPONENT_CMD=$5
GPU_LIST=$6
GAMENUM=$7
EVAL_FOLDER=$8
SGFFILE="$8/fight"

sp_executable_file="/workspace/build/$GAME_TYPE/restnet_$GAME_TYPE"
BLACK="$sp_executable_file -conf_file $CONF_FILE1 -conf_str \"nn_file_name=$MODEL1\""
WHITE="$OPPONENT_CMD"

KOMI=0
if [ $GAME_TYPE == "go" ]; then
    KOMI=7
fi

if [ -f "$SGFFILE.lock" ] ; then\
    echo "$SGFFILE.lock is existed"
    return
fi

if [ -f "${SGFFILE}-$((${GAMENUM}-1)).sgf" ] ; then\
    echo "is not a clean folder"
    return
fi

if [ ! -f "$MODEL1" ]; then\
    echo "${MODEL1}"
    echo "(MODEL1) is not existed"
    return
fi

if [ ! -d "${EVAL_FOLDER}" ];then
    mkdir -p $EVAL_FOLDER
fi

echo "GPUID: $GPU_LIST, Current players: ${MODEL1}, Game num $GAMENUM $BOARD_SIZE"
CUDA_VISIBLE_DEVICES=$GPU_LIST gogui-twogtp -black "$BLACK" -white "$WHITE" -games $GAMENUM -sgffile $SGFFILE -alternate -auto -size $BOARD_SIZE -komi $KOMI -threads 2
