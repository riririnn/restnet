#!/bin/bash
set -e

usage(){
    echo "Usage: ./defending-cyclic-adversary-go.sh [Game Type] [Board Size] [Model File] [Configuration File] [Opponent's Command] [Opening Dir] [ResTNet's Color (black/white)] [GPU List] [Num Games] [Save Folder]"
}

if [ $# -ne 10 ];
then
    usage
    exit 0
fi


GAME_TYPE=$1
BOARD_SIZE=$2
MODEL1=$3
CONF_FILE1=$4
OPPONENT_CMD=$5
OPENING_DIR=$6
VICTIM_COLOR=$7
GPU_LIST=$8
GAMENUM=$9
EVAL_FOLDER=${10}
SGFFILE="${10}/fight"

sp_executable_file="/workspace/build/$GAME_TYPE/restnet_$GAME_TYPE"
restnet_command="$sp_executable_file -conf_file $CONF_FILE1 -conf_str \"nn_file_name=$MODEL1\""
opponent_command="$OPPONENT_CMD"

VICTIM_COLOR=$(echo $VICTIM_COLOR | tr '[:upper:]' '[:lower:]')
if [ "$VICTIM_COLOR" == "black" ]; then
    echo "VICTIM IS BLACK"
    BLACK="$restnet_command"
    WHITE="$opponent_command"
elif [ "$VICTIM_COLOR" == "white" ]; then
    echo "VICTIM IS WHITE"
    BLACK="$opponent_command"
    WHITE="$restnet_command"
else
    echo "Invalid victim color: $VICTIM_COLOR. Use 'Black' or 'White'."
    exit 1
fi

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
    echo "${MODEL1}"
    ehco "(MODEL1) is not existed"
    return
fi

if [ ! -d "${EVAL_FOLDER}" ];then
    mkdir -p $EVAL_FOLDER
fi

echo "GPUID: $GPU_LIST, Current players: ${MODEL1}, Game num $GAMENUM $BOARD_SIZE"
CUDA_VISIBLE_DEVICES=$GPU_LIST gogui-twogtp -black "$BLACK" -white "$WHITE" -games $GAMENUM -sgffile $SGFFILE -alternate -auto -size $BOARD_SIZE -komi $KOMI -openings $OPENING_DIR -threads 2
