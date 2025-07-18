#!/bin/bash
set -e

experiments_path="experiments-results/"
mkdir -p ${experiments_path}

model_root_path="release-models/10B-go-19-models"
R3RRT_model_pkl_path="${model_root_path}/R3RRT/model/weight_iter_150000.pkl"
R3RRT_model_cfg_path="${model_root_path}/R3RRT/eval.cfg"

_10R_model_pkl_path="${model_root_path}/10R/model/weight_iter_150000.pkl"
_10R_model_cfg_path="${model_root_path}/10R/eval.cfg"

circular_board_data_path="experiments-datasets/go_19x19_24_circular_patterns"
PYTHONPATH=. python restnet/analysis/circular_board_eval.py ${R3RRT_model_pkl_path} ${R3RRT_model_cfg_path} ${_10R_model_pkl_path} ${_10R_model_cfg_path} ${circular_board_data_path} | tee ${experiments_path}/circular_board_eval.log