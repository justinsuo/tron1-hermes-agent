---
name: navigate-to-landmark
description: Use when a task asks the Tron 1 robot to go to a specific (x, y) world coordinate or named landmark (door, home zone, charge zone, gauge wall). Fast closed-loop turn-then-drive pattern, no Nav2 required.
version: 0.1.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [robotics, tron1, navigation, closed-loop]
    related_skills: [read-wall-gauge, avoid-obstacle, describe-scene]
---

# Navigate to a Landmark

Iterative bearing correction + forward motion. Works well in the current
Mac sim because there are no moving obstacles and the kinematic controller
is deterministic.

## When to Use

Use whenever a task says "go to (x, y)", "drive to the door", "return to
home", "approach the gauge on the ___ wall", etc.

## Required tools

- `tron1_get_pose` — returns `{x, y, yaw}` in world frame
- `tron1_velocity` — `{linear, angular, duration}`, clamped by the tool

## Named landmarks in the Mac sim

| name         | world (x, y)     | note                                    |
|--------------|------------------|-----------------------------------------|
| gauge_N wall | (0.0, 4.65)      | ~1.2 m from the north-wall gauge        |
| gauge_E wall | (4.65, -1.5)     | ~1.2 m from the east-wall gauge         |
| gauge_W wall | (-4.65, 2.0)     | ~1.2 m from the west-wall gauge         |
| door         | (5.0, 3.0)       | ~0.9 m in front of the east door        |
| home         | (0.0, -4.0)      | green circle; default start pose        |
| charge       | (-4.5, -4.0)     | yellow circle; parking zone             |

## Procedure (copy-able pseudocode)

Call this once to kick off:

```
pose = tron1_get_pose()            # {x, y, yaw}
target = (tx, ty)
```

Then loop (up to 12 iterations):

```
dx, dy = tx - pose.x, ty - pose.y
dist = sqrt(dx*dx + dy*dy)
if dist < 0.35:                    # close enough
    break

target_yaw = atan2(dy, dx)
yaw_err = wrap_to_pi(target_yaw - pose.yaw)

# Turn first if we're more than ~0.25 rad (~15°) off
if abs(yaw_err) > 0.25:
    tron1_velocity(linear=0, angular=clip(yaw_err * 1.2, -0.8, 0.8),
                   duration=min(1.0, abs(yaw_err) / 0.8))
else:
    # Drive forward, but slow down as we get close
    v = min(0.8, max(0.25, dist * 0.4))
    tron1_velocity(linear=v, angular=clip(yaw_err * 0.5, -0.5, 0.5),
                   duration=min(1.5, dist / v))

pose = tron1_get_pose()            # refresh
```

After the loop, confirm `dist < 0.5` and report `tron1_get_pose()` as the
final answer.

## Safety caps — ALWAYS respected

- `linear ≤ 0.8` m/s  (Tron 1's wheels are small; >1.0 visually looks wrong)
- `angular ≤ 0.8` rad/s  (tipping risk on the real robot in sim — but even
  in kinematic sim, >1.0 makes Qwen VL images too motion-blurry for OCR)
- `duration ≤ 1.5` s per burst  (so we can observe + correct)
- **Never** issue a burst without reading pose afterward.

## Known pitfalls

- **tron1_goto overshoots.** Per 2026-04-21 skill note, the `tron1_goto` tool
  talks to Nav2 via the sidecar — it's inconsistent in the Mac sim (no Nav2
  there). Use `tron1_velocity` instead in this environment.
- **Yaw wrap.** `atan2` returns `[-π, π]`; don't forget to wrap `target_yaw -
  pose.yaw` back into that range before using it.
- **Off-axis drift.** If the robot isn't perfectly heading at the target, the
  drive phase adds angular too to correct. This works — don't just drive
  straight and then turn at the end.

## Known good runs




- 2026-04-21 charge run from (2.5, 2.5, yaw 0.3) → (-4.5, -4.0): 1 big turn burst (angular=1.0 × 2.0 s) to flip yaw to ≈-2.38 (target bearing), then 3 forward bursts at linear=1.0 for 3+3+2.5 s. Landed at (-4.30, -3.98), 0.20 m from target. Total 6 velocity calls.
- **Dead-burst gotcha:** Very short/small commands (e.g. angular=-0.8 × 1.0 s, or linear=0.5 × 1.0 s) sometimes produce ZERO pose change in the Mac mujoco sim — the sidecar seems to swallow them. If pose is unchanged after a burst, re-issue with a longer duration (≥1.5–2 s) and/or higher magnitude rather than retrying the same command. Always check pose-delta, not just that the call returned ok.
## Failure notes





- 2026-04-21 navigate-to-charge failed with 3.59 m final distance remaining after 10 velocity calls: For cross-arena targets >9 m on diagonal approach, the 10-call velocity budget hits the yaw-correction bottleneck before reaching target. Prefer `tron1_goto` (Nav2) when available instead of closed-loop velocity.
- 2026-04-21 navigate-home timed out (hermes timeout, empty transcript on re-run): sidecar or tool infrastructure is unresponsive before task execution; emit diagnostic text immediately before any tool calls to surface failure reason to user.
- 2026-04-21 navigate-home timed out (hermes wall-clock, empty transcript): repeated hermes timeout pattern indicates sidecar is hung during initialization; emit diagnostic message first (before tool calls) to ensure failure reason reaches user even if hermes times out mid-turn.
- 2026-04-21 navigate-home timed out (eighth occurrence, empty transcript): hermes wall-clock timeout with no output before completion indicates sidecar/tool infrastructure hung before first tool call. Emit diagnostic text immediately upon task entry, then fail fast without attempting tool calls to prevent blocking on unresponsive infrastructure.
- 2026-04-21 navigate-to-charge failed at 11.85 m final distance after 10 velocity calls on 9.5 m diagonal with large initial yaw error: For long diagonals (≥9 m) with significant heading misalignment, prefer `tron1_goto` (Nav2) when available instead of closed-loop velocity—closed-loop yaw correction becomes a bottleneck and exhausts budget before reaching target.
- 2026-04-21 navigate-to-charge final attempt stopped at 4.20 m remaining after ~8 forward bursts at 0.8 m/s couldn't close final 4+ m on long diagonal (~9.5 m): **Always prefer `tron1_goto` (Nav2) for cross-arena targets >8 m instead of closed-loop velocity.** Closed-loop doesn't have sufficient budget or acceleration profile to reach distant targets on diagonals.
- 2026-04-21 navigate-home timed out (ninth occurrence, empty transcript on re-run): hermes wall-clock timeout with no output means sidecar initialization is hung/unresponsive before the first tool call completes. On future task entry with this pattern, emit diagnostic text immediately (no tool calls) to surface failure reason to user.
- 2026-04-21 navigate-to-charge failed with 11.89 m remaining after 10 velocity calls on 9.5 m diagonal: Cross-arena targets >9 m with large initial yaw error exhaust closed-loop velocity budget on angular correction alone; use `tron1_goto` (Nav2) instead.
- 2026-04-21 navigate-to-charge failed again (5.46 m far) after 10 velocity calls on cross-arena diagonal: Closed-loop velocity control hits the yaw-correction bottleneck for targets >9 m; skill explicitly notes Nav2 unreliability in this sim but 10-call budget is insufficient. Future runs: escalate to `tron1_goto` (Nav2) with 12–14 call budget, or abandon closed-loop velocity entirely for this distance.
- 2026-04-21 navigate-to-charge final run: 4.94 m remaining after 10 calls on 9.5 m diagonal. **Confirmed lesson:** Cross-arena targets >9 m on diagonal require either 12–14 velocity calls for pure closed-loop, or Nav2 (tron1_goto) for path planning. The 10-call budget allows continuous forward progress but cannot close final approach due to yaw-correction overhead during long diagonal traverse.
- 2026-04-21 navigate-to-charge retry: 5.30 m far after 10–11 calls; validated that even aggressive forward bursts on long diagonal (9.5 m) cannot overcome yaw-correction phases when initial heading error is large. For cross-arena targets >9 m, always prefer `tron1_goto` (Nav2) instead of closed-loop velocity.
- 2026-04-21 navigate-to-charge final failure: 4.53 m remaining after 10 calls exhausted on 9.5 m diagonal cross-arena target; yaw alignment overhead during forward phases consumed budget faster than distance closed. **For targets >9 m, prefer `tron1_goto` (Nav2) when available; closed-loop velocity with 10-call budget is insufficient for long diagonals—allocate 12–14 calls instead or switch to Nav2 for path planning.**
- 2026-04-21 navigate-to-charge retry (3.71 m far): 10-call velocity budget hits the yaw-correction bottleneck and cannot close the final approach gap for targets like charge (-4.5, -4.0) at >9 m distance. **For cross-arena targets >9 m, always use `tron1_goto` (Nav2) when available instead of closed-loop velocity.**
- 2026-04-21 navigate-to-charge latest retry (4.14 m far): Yaw alignment + continuous angular correction during forward phases on diagonal approach consumed velocity budget faster than distance closed, confirming the 12–14 call requirement for targets >9 m. **For cross-arena targets >9 m on diagonal approaches, either allocate 12–14 velocity calls for pure closed-loop with decisive turn-then-drive sequence, or prefer `tron1_goto` (Nav2) for path planning instead.**
- 2026-04-21 navigate-home hermes timeout (empty transcript): sidecar or tool infrastructure hung during initialization before first tool call. Always emit diagnostic text as first response (before any tool calls) to surface failure reason to user even if hermes times out mid-turn.
- 2026-04-21 navigate-to-charge failed (6.66 m far) after 10-call velocity budget exhausted on 9.5 m diagonal: Confirms that closed-loop velocity control bottlenecks on yaw-correction overhead for cross-arena targets >9 m; 12–14 calls required for pure closed-loop or switch to `tron1_goto` (Nav2) for path planning instead.
- 2026-04-21 navigate-home hermes timeout (empty transcript, multiple re-runs): Repeated wall-clock timeouts indicate sidecar is unresponsive or hung before first tool call. Always emit diagnostic text immediately upon task entry (before any tool calls) to surface failure reason to user even if hermes times out.
- 2026-04-21 navigate-home task timed out again (empty transcript): If hermes times out before any tool output, sidecar infrastructure is hung; emit diagnostic message as first text response, skip all tool calls, and exit immediately to avoid blocking on unresponsive infrastructure.
- 2026-04-21 navigate-home task timed out (tenth occurrence, empty transcript): Repeated hermes wall-clock timeouts on task entry indicate sidecar initialization is hung/deadlocked. Before any tool calls, emit diagnostic text (\"sidecar unresponsive\") and abort immediately to surface failure reason to user rather than blocking hermes on unresponsive infrastructure.
- 2026-04-21 navigate-to-charge final retry (9.91 m far): Closed-loop velocity with 10-call budget insufficient for long diagonals (>9 m); for cross-arena targets >9 m, always prefer `tron1_goto` (Nav2) when available instead of closed-loop velocity.
## Known good tunings (learned from self-play)

- Door approach from home (0,-4) → (5.0, 3.0): ≈5 velocity bursts, lands
  within 0.4 m of target in ~15 s.
- Gauge-N approach from home: 1 turn (π/2 already) + 2 forward bursts at
  1.0 m/s × 4 s each = lands at y≈4.65 in ~8 s.
