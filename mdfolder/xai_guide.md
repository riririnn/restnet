# XAI (Explainable AI) Guide for ResTNet Shogi

## Overview

`xai_analysis.py` implements three complementary XAI methods to understand what the ResTNet model has learned.

| Method | Question answered | Speed |
|---|---|---|
| **Integrated Gradients (IG)** | Which squares caused this value/move output? | Fast |
| **Perturbation / Occlusion** | Which squares does the output depend on? | Medium (81 forward passes) |
| **Attention Rollout** | Where does the Transformer look across all layers? | Fast |

---

## Quickstart

```bash
# Run all three methods on a random board (for testing)
python xai_analysis.py --model path/to/weight.pt --target all --no-show

# Run on a real game position
python xai_analysis.py \
  --model shogi_9x9_gaz_2R1T2R1T/model/weight_iter_200.pt \
  --conf  configs/9x9_shogi/RRTRRT.cfg \
  --game-type shogi_9x9 \
  --sgf   path/to/game.sgf \
  --target all \
  --source-square 4,4 \
  --out-dir results/
```

---

## Method 1 — Integrated Gradients (IG)

**Paper:** Sundararajan, Taly & Yan — "Axiomatic Attribution for Deep Networks", ICML 2017

### Concept

IG asks: "compared to an empty board, how much did each square contribute to this output?"

```
IG(x) = (x − baseline) × ∫₀¹ ∂F(baseline + α·(x−baseline)) / ∂x dα
```

- **Baseline**: all-zero tensor (empty board = zero information)
- **Red squares**: pushed the output up (e.g., this piece helps win)
- **Blue squares**: pushed the output down (this piece hurts)

### Usage

```bash
# Explain value (win probability)
python xai_analysis.py --model weight.pt --target value

# Explain the top policy action (chosen move)
python xai_analysis.py --model weight.pt --target policy

# Both at once
python xai_analysis.py --model weight.pt --target both

# High quality for paper figures
python xai_analysis.py --model weight.pt --target both --steps 300
```

### `--steps` parameter

| Steps | Speed | Use for |
|---|---|---|
| 20 | Very fast | Quick debugging |
| 50 (default) | Fast | Normal analysis |
| 300 | Slow | Publication figures |

### Output files

| File | Contents |
|---|---|
| `ig_value.png` | 9×9 heatmap: attribution for win probability |
| `ig_policy.png` | 9×9 heatmap: attribution for the chosen move |

### Interpretation example

```
ig_value.png:
  Red at 5e (centre)  → this piece strongly boosts the model's win estimate
  Blue at 1a          → this piece is actually reducing the win estimate
```

---

## Method 2 — Perturbation / Occlusion

### Concept

For each of the 81 squares, all input channels at that position are set to zero ("remove the piece"), and the output change is measured:

```
attribution[r, c] = output(original) − output(board with square (r,c) zeroed)
```

- **Red squares**: removing them hurts the output → piece is important
- **Blue squares**: removing them helps the output → piece was working against the model

### Why use this alongside IG?

IG is gradient-based and very fast, but it can miss non-linear interactions. Perturbation is model-agnostic and directly measures causal influence. Use both to cross-validate each other.

### Usage

```bash
# Explain value and policy via perturbation
python xai_analysis.py --model weight.pt --target perturbation

# All three methods together
python xai_analysis.py --model weight.pt --target all
```

### Output files

| File | Contents |
|---|---|
| `perturb_value.png` | 9×9 heatmap: per-square impact on win probability |
| `perturb_policy.png` | 9×9 heatmap: per-square impact on the chosen move |

### Note on speed

Perturbation runs 81 forward passes (one per square). On CPU this takes a few seconds; on GPU it is near-instant.

---

## Method 3 — Attention Rollout

**Paper:** Abnar & Zuidema — "Quantifying Attention Flow in Transformers", ACL 2020

### Concept

Single-layer attention maps are incomplete because attention flows through residual connections across layers. Rollout chains all T-block attention matrices together:

```
A_rolled = A_rolled × (A_current + Identity)
```

The identity term accounts for the residual skip ("every token always attends to itself a little").

### Usage

```bash
# Average attention received per square (overview map)
python xai_analysis.py --model weight.pt --target rollout

# Where does the centre square (row=4, col=4) attend to?
python xai_analysis.py --model weight.pt --target rollout --source-square 4,4

# Combined with IG
python xai_analysis.py --model weight.pt --target all --source-square 4,4
```

### Source square coordinates

Coordinates are `row,col` with **0-indexed, top-left origin**:

```
(0,0) (0,1) … (0,8)   ← row a (rank 9…1 in shogi notation)
(1,0) (1,1) … (1,8)   ← row b
…
(8,0) (8,1) … (8,8)   ← row i
```

Centre of the board = `4,4`.

### Output files

| File | Contents |
|---|---|
| `rollout_avg.png` | Average attention received per square across all positions |
| `rollout_r4c4.png` | Where square (4,4) sends its attention after full rollout |
| `per_head_r4c4.png` | Grid of `num_T_layers × num_heads` individual attention maps |

### Per-head layout (2R1T2R1T architecture)

```
         Head 1    Head 2    Head 3    Head 4
Layer 1  [map]     [map]     [map]     [map]
Layer 2  [map]     [map]     [map]     [map]
```

Specialised heads often emerge: one head may focus on diagonal bishop threats while another monitors the king's defenders.

---

## Loading a Real Board Position

By default `xai_analysis.py` uses a random tensor. For meaningful analysis, load a real position from an SGF file:

```bash
python xai_analysis.py \
  --model  shogi_9x9_gaz_2R1T2R1T/model/weight_iter_200.pt \
  --conf   configs/9x9_shogi/RRTRRT.cfg \
  --game-type shogi_9x9 \
  --sgf    path/to/game.sgf \
  --target all \
  --out-dir results/position_A/
```

This plays through all moves in the SGF and loads the feature tensor at the **final position**. The shape must match `(1, 362, 9, 9)` — same 362-channel tensor the C++ self-play sends to the network.

You can also load a saved numpy array directly in Python:

```python
import numpy as np, torch
features = np.load("my_position.npy")          # shape (362, 9, 9)
board_state = torch.from_numpy(features).unsqueeze(0).float()  # (1, 362, 9, 9)
```

---

## How the Three Methods Complement Each Other

```
Board position
      │
      ├── Integrated Gradients ──► "Which squares mattered, via gradient?"
      │                             Fast. Can miss non-linear effects.
      │
      ├── Perturbation ──────────► "Which squares mattered, causally?"
      │                             Slower. Model-agnostic ground truth.
      │
      └── Attention Rollout ─────► "What does the Transformer look at internally?"
                                    Not attribution — explains internal mechanism.
```

For a complete analysis, run `--target all` and compare `ig_value.png` with `perturb_value.png`. Agreement between the two gradient-free and gradient-based methods builds confidence in the attribution.

---

## Full CLI Reference

```
python xai_analysis.py
  --model        PATH      Path to weight_iter_N.pt (required)
  --target       STR       value | policy | both | rollout | perturbation | all
  --steps        INT       IG Riemann steps: 20=fast, 50=default, 300=paper
  --source-square R,C      Rollout source square, e.g. 4,4 for centre
  --sgf          PATH      SGF file for real board state
  --conf         PATH      Config .cfg file (required with --sgf)
  --game-type    STR       Build target, default: shogi_9x9
  --out-dir      PATH      Output directory for saved figures (default: .)
  --no-show                Skip plt.show() (useful for headless servers)
```

---

## Output File Summary

| File | Method | Contents |
|---|---|---|
| `ig_value.png` | IG | Attribution for win probability |
| `ig_policy.png` | IG | Attribution for chosen move |
| `perturb_value.png` | Perturbation | Causal impact per square on win probability |
| `perturb_policy.png` | Perturbation | Causal impact per square on chosen move |
| `rollout_avg.png` | Attention Rollout | Average attention received per square |
| `rollout_rXcY.png` | Attention Rollout | Rollout from source square (X,Y) |
| `per_head_rXcY.png` | Attention Rollout | Per-layer × per-head breakdown |
