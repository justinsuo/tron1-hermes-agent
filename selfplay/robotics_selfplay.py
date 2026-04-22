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


def _run_hermes(prompt: str, budget_s: int) -> tuple[str, int]:
    """Call `hermes chat -q <prompt> -Q` with the robotics toolsets enabled.

    Returns (transcript, returncode). 124 = timeout, 127 = PATH miss.
    """
    cmd = ["hermes", "chat", "-q", prompt, "-Q",
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
    cmd = ["hermes", "chat", "-q", prompt, "-Q",
           "-t", "skills", "--max-turns", "6"]
    try:
        subprocess.run(cmd, capture_output=True, text=True, timeout=90)
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass


def run_one(backend: str) -> dict:
    task = _sample_task()
    T.reset_robot(task.reset_to)
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


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--rounds", type=int, default=10,
                   help="Episodes to run (0 = infinite).")
    p.add_argument("--delay", type=float, default=2.0,
                   help="Seconds to sleep between episodes.")
    p.add_argument("--backend", default="mujoco-mac")
    args = p.parse_args()

    print(f"self-play on backend={args.backend} — {args.rounds or '∞'} rounds")
    ok, total = 0, 0
    for i in range(args.rounds if args.rounds > 0 else 10**9):
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
