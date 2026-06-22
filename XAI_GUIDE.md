# XAI (Explainable AI) Guide for ResTNet Shogi

## Overview

This guide explains how to use the two XAI methods implemented in `xai_analysis.py` to understand what the ResTNet model has learned.

The two methods answer different questions:

| Method | Paper | Question answered |
|---|---|---|
| **Integrated Gradients (IG)** | Sundararajan et al., ICML 2017 | Which board squares caused this value/move output? |
| **Attention Rollout** | Abnar & Zuidema, ACL 2020 | Where does each Transformer head look across the board? |

---

## Method 1 — Integrated Gradients (IG)

**Full name:** Integrated Gradients
**Paper:** Sundararajan, Taly & Yan — "Axiomatic Attribution for Deep Networks", ICML 2017

### Concept

IG computes how much each input feature (board square) contributed to the model's output, compared to a **baseline** (empty board = no pieces).

**Formula:**

```
IG(x) = (x - baseline) × average gradient from baseline to x
```

- **Positive (red)** → this square pushed the output higher (e.g., good for winning)
- **Negative (blue)** → this square pushed the output lower

### Why this baseline?

The empty board is the natural reference for a board game — it has zero information. Every non-zero attribution tells you "this piece's presence changed the model's belief."

### Usage

```bash
# Explain value output (win probability)
python xai_analysis.py --model path/to/weight.pt --target value

# Explain the top policy action (move choice)
python xai_analysis.py --model path/to/weight.pt --target policy

# Both at once, high quality (300 steps for paper figures)
python xai_analysis.py --model path/to/weight.pt --target both --steps 300
```

### Output: `ig_value.png`

A 9×9 heatmap. Each square shows how much that board position influenced the **win probability**.

```
Example interpretation:
  Red square at 5e (centre) → model sees this piece as critical to winning
  Blue square at 1a         → this piece is actually hurting the model's value
```

### Output: `ig_policy.png`

Same heatmap, but for the **specific move the model chose** (top policy action). Shows which squares the model "looked at" to decide on that move.

### Steps parameter

| Steps | Speed | Use for |
|---|---|---|
| 20 | Very fast | Quick debugging |
| 50 | Fast | Normal analysis |
| 300 | Slow | Publication figures |

---

## Method 2 — Attention Rollout

**Full name:** Attention Rollout
**Paper:** Abnar & Zuidema — "Quantifying Attention Flow in Transformers", ACL 2020

### Concept

Attention Rollout traces how attention propagates **through all Transformer layers**. Because attention weights flow through residual connections, looking at a single layer's attention map is not enough — rollout chains them together.

**Formula at each Transformer layer:**

```
A_rolled = A_rolled × (A_current + Identity)
```

The identity term accounts for the residual connection ("each token always attends to itself a little").

### Usage

```bash
# Average attention received per square (overview)
python xai_analysis.py --model path/to/weight.pt --target rollout

# Show where a specific square (row=4, col=4 = centre) attends to
python xai_analysis.py --model path/to/weight.pt --target rollout --source-square 4,4

# Both IG and rollout together
python xai_analysis.py --model path/to/weight.pt --target both --source-square 4,4
```

### Output: `rollout_avg.png`

Bright squares = receive the most attention on average from all other squares. This reveals which regions the Transformer considers globally important regardless of position.

### Output: `rollout_r4c4.png`

Shows where the centre square (4,4) distributes its attention after propagating through all T-blocks. Cyan border marks the source square.

### Output: `per_head_r4c4.png`

Grid of `(num_T_layers × num_heads)` small heatmaps. For the 2R1T2R1T architecture this is `2 layers × 4 heads = 8 panels`.

```
Layout example (2R1T2R1T → 2 Transformer layers, 4 heads each):

         Head 1    Head 2    Head 3    Head 4
Layer 1  [map]     [map]     [map]     [map]
Layer 2  [map]     [map]     [map]     [map]
```

This lets you identify **specialised heads**: e.g., one head may focus on diagonal bishop threats while another monitors the king's defenders.

---

## How the two methods complement each other

```
Board position
      │
      ├─── Integrated Gradients ──► "Which pieces matter for this output?"
      │                              (input-space explanation)
      │
      └─── Attention Rollout ──────► "What does the Transformer look at?"
                                     (internal mechanism explanation)
```

For a complete analysis of one board position, run both:

```bash
python xai_analysis.py \
  --model shogi_9x9_gaz_2R1T2R1T_P_TV_n50/model/weight_iter_200.pt \
  --target both \
  --steps 300 \
  --source-square 4,4 \
  --out-dir results/position_A/
```

---

## Using a real board state (replacing the dummy input)

`xai_analysis.py` currently uses `dummy_board_state()` (random tensor). To analyse a real position, replace it with the feature vector from your pipeline.

The input shape must be `(1, 362, 9, 9)` float32 — the same 362-channel tensor that the C++ self-play sends to the network. Extract it from your `.sgf` files or from the data loader.

```python
# Example: load from a saved numpy array
import numpy as np, torch
features = np.load("my_position.npy")          # shape (362, 9, 9)
board_state = torch.from_numpy(features).unsqueeze(0)  # (1, 362, 9, 9)
```

---

## File summary

| File | Role |
|---|---|
| `xai_analysis.py` | All XAI code: IG, rollout, visualisation, CLI |
| `ig_value.png` | IG attribution for value head |
| `ig_policy.png` | IG attribution for top policy action |
| `rollout_avg.png` | Average attention received per board square |
| `rollout_rXcY.png` | Rollout from a specific source square |
| `per_head_rXcY.png` | Per-layer × per-head attention breakdown |
