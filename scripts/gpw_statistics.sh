#!/bin/bash
# Every statistic behind the GPW 2026 poster (gpw_paper/poster_parts.md).
# Inside the container, from /workspace:  scripts/gpw_statistics.sh [STEP ...]   (no STEP: all)
# Dobutsu runs on the CPU (about 3 minutes per model and draw); the 9x9 part of peaked, shogi, sl_check and ig use the GPU.
# Tables are written as CSV next to their inputs; nothing outside data/ and models/ is written.
set -e -o pipefail
cd "$(dirname "$0")/.."

T=data/dobutsu_tablebase/dobutsu   # Tanaka's complete analysis (not in git)
D=data/dobutsu_all
R=scripts/attention_move_rank.py
PAPER=$(ls models/dobutsu/new/*/model/weight_iter_40000.pt)   # the paper's 11 models (40,000 steps)
REP=$(ls models/dobutsu/old/*_rep/model/weight_iter_110000.pt)  # an earlier, separate run (110,000 steps)
SL9="models/9x9_shogi/fg_10T_weight_iter_150000.pt models/9x9_shogi/fg_R3RRT_weight_iter_150000.pt"
FLOODGATE_TEST=data/floodgate/sgf_2250/test.sgf
SELF9=models/9x9_shogi/eval/R3RRT/model/weight_iter_100000.pt   # the paper's self-play R3(RRT)
RL9="models/9x9_shogi/eval/10T_fg/weight_iter_250000.pt models/9x9_shogi/eval/rl_R3RRT_from_sl/weight_iter_250000.pt"   # self-play from the SL weights

step_records() {   # 100,000 random positions in 4 orientations with every move's outcome, three draws
    [ -x $D/dobutsu_all ] || g++ -O3 -DNDEBUG -fopenmp -Wno-deprecated -I$T scripts/dobutsu_all.cc \
        $T/dobutsu.cc $T/allStateTable.cc $T/winLoseTable.cc -o $D/dobutsu_all
    for s in 1 2 3; do
        [ -e $D/moves_100k_seed$s.bin ] || $D/dobutsu_all $T moves 100000 $s $D/moves_100k_seed$s.bin
    done
}

step_teacher() {   # the teacher's table on the paper's 11 models, each draw
    for s in 1 2 3; do
        python3 $R dobutsu $D/moves_100k_seed$s.bin $D/rank_paper11_seed$s.csv $PAPER
    done
}

step_controls() {   # the same table for 6T with position bias alone, untrained weights, the reverse direction, rollout, and one orientation at a time
    M=models/dobutsu/new/6T/model/weight_iter_40000.pt
    for c in bias untrained reverse rollout; do
        python3 $R dobutsu $D/moves_100k_seed1.bin $D/rank_6T_$c.csv $M --control $c
    done
    for o in 0 1 2 3; do
        python3 $R dobutsu $D/moves_100k_seed1.bin $D/rank_6T_orient$o.csv $M --orient $o
    done
}

step_other_run() {   # the same table for an earlier, separate training run of the 11 architectures
    python3 $R dobutsu $D/moves_100k_seed1.bin $D/rank_rep11_seed1.csv $REP
}

step_training() {   # during the paper's run: 4,000 to 28,000 steps (the 40,000-step models are step_teacher)
    for s in 4000 12000 20000 28000; do
        python3 $R dobutsu $D/moves_100k_seed1.bin $D/rank_mid${s}_seed1.csv $(ls models/dobutsu/midpoints/*/model/weight_iter_$s.pt)
    done
}

step_ablation() {   # make one head's weights uniform at a time: how much the policy and the value results go down
    for a in 6T RRTRRT; do
        python3 $R dobutsu $D/moves_100k_seed1.bin $D/ablate_$a.csv models/dobutsu/new/$a/model/weight_iter_40000.pt --ablate
    done
}

step_splits() {   # the table by kind of position and by kind of moving piece
    python3 $R dobutsu $D/moves_100k_seed1.bin $D/rank_paper11_splits_seed1.csv $PAPER --splits
}

step_peaked() {   # how far each head is from even weights (1 = even): dobutsu on 2,000 inputs, 9x9 on 2,048 positions (GPU)
    python3 $R dobutsu $D/moves_100k_seed1.bin $D/peaked_paper11.csv $PAPER --peaked
    python3 $R dobutsu $D/moves_100k_seed1.bin $D/peaked_rep11.csv $REP --peaked
    python3 $R shogi $FLOODGATE_TEST data/floodgate/peaked_sl.csv $SL9 models/9x9_shogi/eval/R3RRT/model/weight_iter_100000.pt --sample 0.1 --seed 1 --peaked
}

step_shogi() {   # 9x9 shogi, SL models, the move played in floodgate as the provisional answer (GPU)
    python3 $R shogi $FLOODGATE_TEST data/floodgate/rank_sl.csv $SL9 --sample 0.1 --seed 1
    python3 $R shogi $FLOODGATE_TEST data/floodgate/rank_sl_bias.csv $SL9 --sample 0.1 --seed 1 --control bias
    python3 $R shogi $FLOODGATE_TEST data/floodgate/ablate_sl.csv $SL9 --sample 0.03 --seed 2 --ablate
}

step_examples() {   # 9x9 SL models: the model's own move, the line of "not even" from the paper's self-play R3(RRT) (GPU); the GUI's sets 'SL の 10T の手' and 'SL の R3(RRT) の手' in the section 手の行き先への Attention
    python3 $R shogi $FLOODGATE_TEST data/floodgate/examples_sl.csv $SL9 models/9x9_shogi/eval/R3RRT/model/weight_iter_100000.pt --sample 0.1 --seed 1 \
        --examples models/9x9_shogi/eval/R3RRT/model/weight_iter_100000.pt
}

step_hand() {   # 9x9 models, the positions and line of step_examples: the model's drops, the change of the weights from the square dropped on when
    # the dropped piece is given away, with two baselines for its agreement (GPU). Until 11-16 only $SL9, as data/floodgate/hand_sl.csv
    python3 $R shogi $FLOODGATE_TEST data/floodgate/hand_9x9.csv $SL9 $SELF9 $RL9 --sample 0.1 --seed 1 --hand $SELF9 | tee data/floodgate/hand_9x9.txt
}

step_shogi_more() {   # 9x9: untrained weights and the reverse direction for the SL models, the RL models from SL, and position bias alone (GPU)
    for c in untrained reverse; do
        python3 $R shogi $FLOODGATE_TEST data/floodgate/rank_sl_$c.csv $SL9 --sample 0.1 --seed 1 --control $c
    done
    python3 $R shogi $FLOODGATE_TEST data/floodgate/rank_rl.csv $RL9 --sample 0.1 --seed 1
    python3 $R shogi $FLOODGATE_TEST data/floodgate/rank_rl_self_bias.csv $RL9 $SELF9 --sample 0.1 --seed 1 --control bias
    python3 $R shogi $FLOODGATE_TEST data/floodgate/peaked_rl.csv $RL9 --sample 0.1 --seed 1 --peaked
}

step_sl_check() {   # are the SL models good enough to start self-play from (the matches: scripts/usi_bridge.py, see the note)
    O=models/9x9_shogi/sl_check
    python3 scripts/sl_model_check.py curves models/9x9_shogi/fg_10T_pretrain.log models/9x9_shogi/fg_R3RRT_pretrain.log models/9x9_shogi/fg_10R_pretrain.log | tee $O/curves.txt
    python3 scripts/sl_model_check.py test $FLOODGATE_TEST $SL9 models/9x9_shogi/fg_10R_weight_iter_150000.pt \
        models/9x9_shogi/eval/R3RRT/model/weight_iter_100000.pt models/9x9_shogi/eval/10R/model/weight_iter_100000.pt --sample 0.1 --seed 1 | tee $O/test_positions.txt
}

step_ig() {   # IG against other attributions on the paper's models (GPU); summaries next to the saved results
    for a in 6T RRTRRT 6R; do
        n=$([ $a = 6T ] && echo 1000 || echo 500)
        python3 scripts/ig_statistics.py run $D/moves_100k_seed1.bin $D/ig_$a.npy models/dobutsu/new/$a/model/weight_iter_40000.pt --positions $n | tee $D/ig_$a.txt
    done
}

# The rebuilt dobutsu environment (v2: 19 planes, the board turned for the second player), on the same position files.
# Start the container without --gpus so that these run on the CPU like the paper's steps.
D2=data/dobutsu_all_v2
V2=$(ls models/dobutsu/v2/*/model/weight_iter_40000.pt)   # the 11 v2 models (40,000 steps)

step_v2_teacher() {   # the teacher's table on the 11 v2 models, each draw
    for s in 1 2 3; do
        python3 $R dobutsu $D/moves_100k_seed$s.bin $D2/rank_v2_seed$s.csv $V2
    done
}

step_v2_controls() {   # as step_controls, for v2 6T
    M=models/dobutsu/v2/6T/model/weight_iter_40000.pt
    for c in bias untrained reverse rollout; do
        python3 $R dobutsu $D/moves_100k_seed1.bin $D2/rank_v2_6T_$c.csv $M --control $c
    done
    for o in 0 1 2 3; do
        python3 $R dobutsu $D/moves_100k_seed1.bin $D2/rank_v2_6T_orient$o.csv $M --orient $o
    done
}

step_v2_training() {   # during the v2 run: the same steps as step_training
    for s in 4000 12000 20000 28000; do
        python3 $R dobutsu $D/moves_100k_seed1.bin $D2/rank_v2_mid${s}_seed1.csv $(ls models/dobutsu/v2/*/model/weight_iter_$s.pt)
    done
}

step_v2_ablation() {   # as step_ablation, for v2
    for a in 6T RRTRRT; do
        python3 $R dobutsu $D/moves_100k_seed1.bin $D2/ablate_v2_$a.csv models/dobutsu/v2/$a/model/weight_iter_40000.pt --ablate
    done
}

step_v2_splits() {   # as step_splits, for v2
    python3 $R dobutsu $D/moves_100k_seed1.bin $D2/rank_v2_splits_seed1.csv $V2 --splits
}

step_v2_hand() {   # the model's drops in v2: the change of the weights from the square dropped on when the dropped piece is given away, with two baselines
    python3 $R dobutsu $D/moves_100k_seed1.bin $D2/hand_v2.csv $V2 --hand | tee $D2/hand_v2.txt
}

step_v2_ig() {   # as step_ig, for v2 (positions as the paper: 6T 1,000, RRTRRT and 6R 500), and the per-plane table (Czech et al.'s figure 5)
    for a in 6T RRTRRT 6R; do
        n=$([ $a = 6T ] && echo 1000 || echo 500)
        python3 scripts/ig_statistics.py run $D/moves_100k_seed1.bin $D2/ig_v2_$a.npy models/dobutsu/v2/$a/model/weight_iter_40000.pt --positions $n | tee $D2/ig_v2_$a.txt
        python3 scripts/ig_statistics.py planes $D2/ig_v2_$a.npy | tee $D2/ig_planes_v2_$a.txt
    done
}

step_ig9() {   # 9x9: IG from the all-zero input and from the pieces removed, on the 500 positions of 11-16, and the per-plane table (GPU)
    for tm in SL_10T:models/9x9_shogi/fg_10T_weight_iter_150000.pt SL_R3RRT:models/9x9_shogi/fg_R3RRT_weight_iter_150000.pt \
              SL_10R:models/9x9_shogi/fg_10R_weight_iter_150000.pt RL_10T_from_SL:models/9x9_shogi/eval/10T_fg/weight_iter_250000.pt \
              RL_R3RRT_from_SL:models/9x9_shogi/eval/rl_R3RRT_from_sl/weight_iter_250000.pt \
              selfplay_R3RRT:$SELF9 selfplay_10R:models/9x9_shogi/eval/10R/model/weight_iter_100000.pt; do
        t=${tm%%:*}; m=${tm#*:}
        python3 scripts/ig_statistics.py shogi $FLOODGATE_TEST data/floodgate/ig_zr_$t.npy $m --positions 500 --baselines zero,removed | tee data/floodgate/ig_zr_$t.txt
        python3 scripts/ig_statistics.py planes data/floodgate/ig_zr_$t.npy | tee data/floodgate/ig_planes_$t.txt
    done
}

step_v2_agreement() {   # agreement with the complete analysis over every position, both orientations (GPU; full was made on 11-11)
    for o in full full_o2; do
        python3 scripts/dobutsu_all_agreement.py full $D2/$o | tee $D2/$o.log
    done
}

step_v2_presets() {   # the v2 viewer's files: the lost wins of 10,000 random positions (as the 10-17 check of the paper's models), then the presets (CPU)
    [ -e $D2/sample_10k_seed1.bin ] || $D/dobutsu_all $T sample 10000 1 $D2/sample_10k_seed1.bin
    python3 scripts/dobutsu_all_agreement.py check $D2/sample_10k_seed1.bin --device cpu | tee $D2/sample_10k_seed1.txt
    PYTHONPATH=build/dobutsu python3 scripts/attention_presets.py dobutsu
}

step_v2_peaked() {   # as the dobutsu part of step_peaked, for v2
    python3 $R dobutsu $D/moves_100k_seed1.bin $D2/peaked_v2.csv $V2 --peaked
}

step_v2_lion() {   # the paper's figure 5 for v2 (from the lion, 6T block 5 head 3) and its simple baselines on seeds 5-8 (CPU)
    PYTHONPATH=build/dobutsu python3 -c "import sys; sys.path.insert(0, 'scripts'); import dobutsu_viewer as V; print(V.head_statistics()[1]); print(V.lion_controls())" | tee $D2/lion_controls_v2.txt
}

steps=${@:-records teacher controls other_run training ablation splits peaked shogi examples hand sl_check ig v2_teacher v2_controls v2_training v2_ablation v2_splits v2_peaked v2_hand v2_ig v2_presets v2_lion}
for s in $steps; do
    echo "===== $s ====="
    step_$s
done
