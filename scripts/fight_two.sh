#!/bin/bash
set -e

usage(){
    echo "Usage: ./fight_two.sh [Game Type] [Board Size] [ResTNet Model 1] [ResTNet Model 2] [ResTNet Conf 1] [ResTNet Conf 2] [GPU List] [Num Games] [Save Folder] [SGF Name]"
}

if [ $# -ne 10 ];
then
    usage
    exit 0
fi


GAME_TYPE=$1
BOARD_SIZE=$2
MODEL1=$3
MODEL2=$4
CONF_FILE1=$5
CONF_FILE2=$6
GPU_LIST=$7
GAMENUM=$8
EVAL_FOLDER=$9
SGFFILE="$9/${10}"

sp_executable_file="/workspace/build/$GAME_TYPE/restnet_$GAME_TYPE"
BLACK="$sp_executable_file -conf_file $CONF_FILE1 -conf_str \"nn_file_name=$MODEL1\""
WHITE="$sp_executable_file -conf_file $CONF_FILE2 -conf_str \"nn_file_name=$MODEL2\""

KOMI=0
if [ $GAME_TYPE == "go" ]; then
    KOMI=7
fi
echo "$KOMI"

if [ -f "$SGFFILE.lock" ] ; then\
    echo "$SGFFILE.lock is existed"
    return
fi

if [ -f "${SGFFILE}-$((${GAMENUM}-1)).sgf" ] ; then\
    echo "is not a clean folder"
    return
fi

if [ ! -f "$MODEL1" ]; then\
    echo "$MODEL1 (MODEL1) is not existed"
    return
fi

if [ ! -f "$MODEL2" ]; then\
    echo "$MODEL2 (MODEL2) is not existed"
    return
fi

if [ ! -d "${EVAL_FOLDER}" ];then
    mkdir -p $EVAL_FOLDER
fi

echo "GPUID: $GPU_LIST, Current players: ${MODEL1}_vs_${MODEL2}, Game num $GAMENUM $BOARD_SIZE"
CUDA_VISIBLE_DEVICES=$GPU_LIST gogui-twogtp -black "$BLACK" -white "$WHITE" -games $GAMENUM -sgffile $SGFFILE -alternate -auto -size $BOARD_SIZE -komi $KOMI -threads 2
