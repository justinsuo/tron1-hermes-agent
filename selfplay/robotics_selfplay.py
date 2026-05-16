"""Self-play harness for Tron 1 robotics tasks.

Runs a weighted loop over the task bank in tasks.py. Each episode:
  1. Sample a task (weighted, boosted if recently failing).
  2. Reset the sim.
  3. Invoke Hermes one-shot with the task prompt + tron1/vision toolsets.
  4. Query sim ground truth and grade the transcript.
  5. Log to ~/.tron1-robotics-log.jsonl.

Start:
    ~/.hermes/hermes-agent/venv/bin/python \\
        ~/tron1-selfplay/robotics_selfplay.py --rounds 20 --backend mujoco-mac
"""

from __future__ import annotations

import argparse
import random
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import robotics_log  # noqa: E402
import tasks as T     # noqa: E402


def _sample_task(failure_boost: float = 1.5) -> T.Task:
    fail_counts = {t.id: 0 for t in T.TASKS}
    for e in robotics_log.recent_failures(limit=50):
        tid = e.get("task")
        if tid in fail_counts:
            fail_counts[tid] += 1
    weights = [
        t.weight * (1.0 + failure_boost * fail_counts[t.id] / 10.0)
        for t in T.TASKS
    ]
    return random.choices(T.TASKS, weights=weights, k=1)[0]


HERMES_MODEL = "mlx-community/Qwen3-4B-4bit"
HERMES_PROVIDER = "auto"
# (Historical: claude-opus-4-7 → claude-haiku-4-5 → Qwen 3 30B-A3B (crashed)
#  → 14B (crashed) → 8B (still crashed under sustained sim+chrome GPU load
#  on Apple Silicon) → 4B 4-bit. The crash root cause isn't single-app RAM
#  pressure (48 GB total is plenty) — it's combined VRAM bandwidth from
#  LLM inference + MuJoCo Renderer + WindowServer. 4B cuts the LLM share
#  of that pie roughly in half.)


def _run_hermes(prompt: str, budget_s: int) -> tuple[str, int]:
    """Call `hermes chat -q <prompt> -Q` with the robotics toolsets enabled.

    Returns (transcript, returncode). 124 = timeout, 127 = PATH miss.
    """
    import os as _os
    model = _os.getenv("HERMES_SELFPLAY_MODEL", HERMES_MODEL)
    # Provider is read from ~/.hermes/config.yaml (model.provider=custom +
    # model.base_url=http://127.0.0.1:8080/v1). Passing --provider on the CLI
    # forces a named provider (anthropic/openrouter/…) so we don't set it
    # here — that way config.yaml's "custom" takes effect.
    cmd = ["hermes", "chat", "-q", prompt, "-Q",
           "-m", model,
           "-t", "tron1,vision_local,skills"]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=budget_s)
        return (r.stdout + "\n" + r.stderr, r.returncode)
    except subprocess.TimeoutExpired:
        return ("[timeout]", 124)
    except FileNotFoundError:
        return ("[hermes CLI not found]", 127)


_SKILL_MAP = {
    "read-gauge-N":        "read-wall-gauge",
    "read-any-gauge":      "read-wall-gauge",
    "navigate-home":       "navigate-to-landmark",
    "find-door":           "navigate-to-landmark",
    "navigate-to-charge":  "navigate-to-landmark",
    "count-obstacles":     "describe-scene",
    "describe-scene":      "describe-scene",
}


def _reflect_on_failure(task_id: str, reason: str, transcript_tail: str) -> None:
    """After a failed episode, give the agent one short turn to record what
    it learned into the relevant SKILL.md. Budget 60s, 5 turns max."""
    skill = _SKILL_MAP.get(task_id)
    if not skill:
        return
    prompt = (
        f"A previous run of task '{task_id}' just FAILED (reason: {reason!r}). "
        f"Here is the tail of the transcript (may be empty if timeout):\n"
        f"---\n{transcript_tail[-400:]}\n---\n"
        f"Use skill_manage(action='patch') to append ONE concise bullet to "
        f"~/.hermes/skills/robotics/{skill}/SKILL.md under a 'Lessons' or "
        f"'Failure notes' section (create if missing) that captures a single "
        f"actionable lesson for future runs. Keep it under 2 sentences. "
        f"Reply with just the word 'DONE' when the patch is applied."
    )
    import os as _os
    model = _os.getenv("HERMES_SELFPLAY_MODEL", HERMES_MODEL)
    cmd = ["hermes", "chat", "-q", prompt, "-Q",
           "-m", model,
           "-t", "skills", "--max-turns", "6"]
    try:
        subprocess.run(cmd, capture_output=True, text=True, timeout=90)
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass


_REGEN_EVERY_N = 30  # rebuild model+textures every N episodes, not every one
_episode_count = 0


def run_one(backend: str) -> dict:
    global _episode_count
    task = _sample_task()
    _episode_count += 1
    # Regen gauges occasionally so the agent doesn't memorize values, but
    # don't do it every episode — it forces a full MJCF reload and
    # destroys the persistent MuJoCo renderer, which on Apple Silicon
    # accumulates wired GPU memory until the system hangs.
    regen = (_episode_count % _REGEN_EVERY_N == 0)
    T.reset_robot(task.reset_to, regen_gauges=regen)
    eid = robotics_log.start_episode(task.id, backend=backend)
    t0 = time.time()

    transcript, rc = _run_hermes(task.prompt, task.budget_s)

    truth = T.gather_sim_truth()
    if rc == 124:
        success, reward, reason = False, -0.5, "hermes timed out"
    elif rc == 127:
        success, reward, reason = False, -1.0, "hermes CLI not on PATH"
    elif rc != 0:
        success, reward, reason = False, -0.3, f"hermes exit {rc}"
    else:
        success, reward, reason = task.grade(transcript, truth)

    robotics_log.end_episode(
        success=success, reward=reward, reason=reason,
        evidence=[f"rc={rc}", f"len={len(transcript)}", f"task={task.id}"],
    )

    # Reflective pass on failure — bank a lesson into the relevant SKILL.md
    if not success:
        _reflect_on_failure(task.id, reason, transcript)

    # Dump the transcript so the dashboard can link to it.
    tpath = Path.home() / ".tron1-transcripts" / f"{eid}.txt"
    tpath.parent.mkdir(exist_ok=True)
    tpath.write_text(
        f"# Episode {eid}\n"
        f"# Task: {task.id}\n"
        f"# Success: {success}  reward={reward:.2f}  reason={reason}\n"
        f"# Elapsed: {time.time() - t0:.1f}s\n"
        f"# Prompt: {task.prompt}\n\n"
        "=== TRANSCRIPT ===\n" + transcript
    )

    return {
        "episode_id": eid,
        "task": task.id,
        "success": success,
        "reward": reward,
        "reason": reason,
        "elapsed_s": round(time.time() - t0, 1),
        "transcript_path": str(tpath),
    }


def _free_mem_pct() -> int:
    """System-wide free memory %, via macOS `memory_pressure`. Returns
    100 if it can't be read (fail-open — never block on a parse error)."""
    try:
        out = subprocess.run(["memory_pressure"], capture_output=True,
                             text=True, timeout=5).stdout
        import re
        m = re.search(r"(\d+)%", out)
        return int(m.group(1)) if m else 100
    except Exception:
        return 100


def _wait_for_memory(floor: int = 45, max_wait_s: int = 120) -> None:
    """Block until free memory is above `floor`%, or `max_wait_s` elapses.

    Self-play paces itself: a heavy episode can leave the system low, and
    starting the next episode immediately is what historically compounded
    into a machine hang. Waiting for memory to settle (plus the memory
    guardian as the hard backstop) keeps overnight runs safe.
    """
    waited = 0
    while waited < max_wait_s:
        if _free_mem_pct() >= floor:
            return
        time.sleep(5)
        waited += 5
    # Timed out — proceed anyway; the memory guardian will cull the
    # episode if it actually runs the machine low.


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--rounds", type=int, default=10,
                   help="Episodes to run (0 = infinite).")
    p.add_argument("--delay", type=float, default=2.0,
                   help="Seconds to sleep between episodes.")
    p.add_argument("--backend", default="mujoco-mac")
    p.add_argument("--mem-floor", type=int, default=45,
                   help="Wait for this %% free memory before each episode.")
    args = p.parse_args()

    print(f"self-play on backend={args.backend} — {args.rounds or '∞'} rounds")
    ok, total = 0, 0
    for i in range(args.rounds if args.rounds > 0 else 10**9):
        # Pace by memory: don't start an episode while the system is still
        # recovering from the previous one.
        _wait_for_memory(floor=args.mem_floor)
        result = run_one(args.backend)
        total += 1
        if result["success"]:
            ok += 1
        tag = "✓" if result["success"] else "✗"
        print(f"[{i+1:3d}] {tag} {result['task']:18s} "
              f"r={result['reward']:+.2f}  {result['elapsed_s']:5.1f}s  "
              f"{result['reason']}")
        print(f"      → {result['transcript_path']}")
        if args.delay > 0 and i < (args.rounds - 1 if args.rounds else 10**9):
            time.sleep(args.delay)
    print(f"\ndone. {ok}/{total} succeeded.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
