# Tron 1 Self-Play — Robotics Training System

Self-play harness and training infrastructure for the Hermes-driven Tron 1
robotics agent. Adapted from `~/computer-use-agent/`, retargeted for robot
episodes, sim/real backends, and vision-model fine-tuning.

## Layout

```
~/tron1-selfplay/
├── robotics_log.py              # append-only JSONL of every episode + step
├── robotics_selfplay.py         # weighted task loop (episode driver)
├── dashboard.py                 # one-shot + --watch stats view
├── training/
│   ├── gen_gauge_dataset.py     # procedural synthetic gauge generator
│   ├── finetune_gauge.py        # LoRA fine-tune of Qwen 2.5 VL (MLX)
│   ├── gauges/                  # generated dataset (image + label.json pairs)
│   └── scenes/                  # reserved for Unity/Unreal sim captures
├── adapters/
│   └── qwen25vl-gauge/
│       └── adapters.safetensors # trained LoRA adapter
└── gauge_samples/               # real-world gauge photos captured during use
```

## Two-layer self-improvement

Layer A — **Hermes skill creation/refinement** (procedural memory).
  When Hermes solves a novel task well it calls `skill_manage(create|patch)`
  and a new or improved `SKILL.md` appears under `~/.hermes/skills/robotics/`.

Layer B — **Vision model fine-tuning** (parametric memory).
  Periodically the `finetune_gauge.py` (and later `finetune_scene.py`)
  scripts update a LoRA adapter on Qwen 2.5 VL. The `qwen_vl_local` Hermes
  tool loads the adapter automatically when `HERMES_QWEN_VL_ADAPTER` is set.

Log drives both: `robotics_log.py` records every attempt. Weighted sampling
in `robotics_selfplay.py` biases future practice toward recently-failing tasks.

## Typical session

```bash
# 1. Generate or refresh synthetic gauge data (fast, no sim needed)
python3 ~/tron1-selfplay/training/gen_gauge_dataset.py --count 2000

# 2. Fine-tune Qwen VL on gauges — ~15 min on M-series Mac at batch 2
~/.hermes/hermes-agent/venv/bin/python \
    ~/tron1-selfplay/training/finetune_gauge.py \
    --iters 400 --batch 2 --lr 2e-5

# 3. Tell Hermes to use the adapter
export HERMES_QWEN_VL_ADAPTER=~/tron1-selfplay/adapters/qwen25vl-gauge/adapters.safetensors

# 4. Run self-play against whatever backend is up
python3 ~/tron1-selfplay/robotics_selfplay.py --rounds 50 --backend sim

# 5. Watch progress
python3 ~/tron1-selfplay/dashboard.py --watch
```

## Log schema

`~/.tron1-robotics-log.jsonl` — one JSON object per line.

```json
{"event":"episode_end","episode_id":"...","task":"read-visible-gauge",
 "backend":"unity","success":true,"reward":0.7,
 "reason":"parsed JSON with value=83.1 °C","duration_s":4.12}
```

Events:
- `episode_start` — begins a task attempt
- `step` — one tool call within an episode
- `episode_end` — outcome + reward

## Reading the dashboard

```
Per-task success rate:
  read-visible-gauge        ███████░░░░░░░░░░░░░   35%  21/60  avg_r=+0.18
  navigate-forward-2m       ██████████████████░░   92%  55/60  avg_r=+0.88
```

A task stuck below 50% after 30 episodes is a candidate for:
1. A new or improved `SKILL.md` in `~/.hermes/skills/robotics/`.
2. Adding more training data (synthetic or captured) and retraining the
   gauge/scene adapter.
3. Dropping it from the task bank if the robot doesn't need to do it.

## Backends

The self-play loop invokes `hermes --one-shot "<task prompt>"` and grades the
transcript. The backend string (`unity`, `unreal`, `mujoco`, `gazebo`, `real`)
is metadata only — the loop doesn't care which sim is running, so long as the
ROS 2 topics are published somewhere the sidecar can see.

Today (real hardware off, MuJoCo sim available in the VM):
```bash
python3 robotics_selfplay.py --rounds 10 --backend mujoco
```

Later (Unity built):
```bash
python3 robotics_selfplay.py --rounds 50 --backend unity
```

## Known limits

- The grader is heuristic. A proper grader would parse the transcript JSON or
  call Claude/Qwen as a judge. TODO after the first 100 episodes.
- `run_one()` assumes `hermes` is on PATH and supports `--one-shot`. If the
  CLI flag name differs, update `_run_agent_one_shot()` in `robotics_selfplay.py`.
- **Gauge fine-tune note (2026-04):** the training pipeline runs cleanly and
  converges (val loss 8.9 → 0.72), but on synthetic gauges the *baseline*
  Qwen 2.5 VL 3B already achieves ~2.6% mean error — fine-tuning on purely
  synthetic data doesn't help. The adapter plateau + an mlx-vlm chat-template
  edge case mean the current adapter slightly regresses output format.
  Treat the synthetic pipeline as a dry run: the real win comes when you feed
  it **actual Tron 1 camera captures of real gauges**, labeled either
  manually or via the existing Claude Vision API. See `gauge_samples/`.
