#!/bin/bash
set -e

experiments_path="experiments-results/"
mkdir -p ${experiments_path}

model_root_path="release-models/10B-go-19-models"
R3RRT_model_pkl_path="${model_root_path}/ladder-models/R3RRT/ll_weight_iter_300000.pkl"
_10R_model_pkl_path="${model_root_path}/ladder-models/10R/ll_weight_iter_300000.pkl"
R3RRT_model_cfg_path="${model_root_path}/ladder-models/R3RRT/eval.cfg"
_10R_model_cfg_path="${model_root_path}/ladder-models/10R/eval.cfg"
ladder_data_path="experiments-datasets/small_test_ladder_data.sgf"
PYTHONPATH=. python restnet/analysis/ladder_eval.py \
  "${R3RRT_model_pkl_path}" "${R3RRT_model_cfg_path}" \
  "${_10R_model_pkl_path}" "${_10R_model_cfg_path}" \
  "${ladder_data_path}" 0.5 \
  | tee "${experiments_path}/ladder_eval.log"
