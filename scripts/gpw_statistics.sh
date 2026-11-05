#!/bin/bash
# Every statistic behind the GPW 2026 poster (gpw_paper/poster_parts.md).
# Inside the container, from /workspace:  scripts/gpw_statistics.sh [STEP ...]   (no STEP: all)
# Dobutsu runs on the CPU (about 3 minutes per model and draw); the 9x9 part of peaked, shogi, sl_check and ig want the GPU.
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

step_controls() {   # what 0.77 is not: position bias alone, untrained weights, reverse direction, one orientation
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

step_ablation() {   # switch one head off at a time: what the policy and the value lose
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

steps=${@:-records teacher controls other_run training ablation splits peaked shogi sl_check ig}
for s in $steps; do
    echo "===== $s ====="
    step_$s
done
