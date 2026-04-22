"""Append-only JSONL log for robotics self-play episodes and skill attempts.

Schema:
    {
      "ts": unix_seconds,
      "event": "episode_start" | "episode_end" | "step",
      "episode_id": str,
      "task": str,                         # skill or task name
      "backend": "unity" | "unreal" | "mujoco" | "gazebo" | "real",
      # step-only:
      "step": int,
      "action": { ... },                   # what the agent did
      "obs":    { ... },                   # sensor snapshot (small: pose, detection counts, image path)
      "reward": float,
      "success": bool,
      "reason": str,
      "duration_s": float,
      "evidence": [str],
    }

Adapted from ~/computer-use-agent/training_log.py (queue-write pattern kept,
fields simplified for robot episodes, added reward/action/obs/duration/backend).
"""

from __future__ import annotations

import json
import os
import queue
import threading
import time
import uuid
from typing import Any, Dict, List, Optional

LOG_PATH = os.path.expanduser("~/.tron1-robotics-log.jsonl")

_write_queue: "queue.Queue[dict]" = queue.Queue(maxsize=4000)
_writer_thread: Optional[threading.Thread] = None
_writer_lock = threading.Lock()
_current_episode: Dict[str, Any] = {"id": "", "task": "", "backend": "", "t0": 0.0}


# ── Public API ────────────────────────────────────────────────────────────────

def start_episode(task: str, backend: str = "sim") -> str:
    """Begin a new episode. Returns the episode_id."""
    eid = uuid.uuid4().hex[:10]
    _current_episode.update({"id": eid, "task": task, "backend": backend, "t0": time.time()})
    _log_raw({
        "ts": time.time(),
        "event": "episode_start",
        "episode_id": eid,
        "task": task,
        "backend": backend,
    })
    return eid


def end_episode(success: bool, reward: float = 0.0, reason: str = "",
                evidence: Optional[List[str]] = None) -> None:
    eid = _current_episode.get("id", "")
    if not eid:
        return
    _log_raw({
        "ts": time.time(),
        "event": "episode_end",
        "episode_id": eid,
        "task": _current_episode.get("task", ""),
        "backend": _current_episode.get("backend", ""),
        "success": bool(success),
        "reward": float(reward),
        "reason": reason,
        "duration_s": round(time.time() - _current_episode.get("t0", time.time()), 3),
        "evidence": evidence or [],
    })
    _current_episode.update({"id": "", "task": "", "backend": "", "t0": 0.0})


def record_step(
    action: Dict[str, Any],
    obs: Dict[str, Any],
    reward: float = 0.0,
    success: bool = True,
    reason: str = "",
    step: Optional[int] = None,
) -> None:
    """Record a single step/decision inside an episode."""
    _log_raw({
        "ts": time.time(),
        "event": "step",
        "episode_id": _current_episode.get("id", "orphan"),
        "task": _current_episode.get("task", ""),
        "backend": _current_episode.get("backend", ""),
        "step": int(step) if step is not None else -1,
        "action": _truncate(action),
        "obs": _truncate(obs),
        "reward": float(reward),
        "success": bool(success),
        "reason": reason,
    })


# ── Queries ───────────────────────────────────────────────────────────────────

def _iter_entries(event: Optional[str] = None) -> List[dict]:
    if not os.path.exists(LOG_PATH):
        return []
    out = []
    try:
        with open(LOG_PATH, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    d = json.loads(line)
                    if event is None or d.get("event") == event:
                        out.append(d)
                except json.JSONDecodeError:
                    continue
    except OSError:
        return []
    return out


def summarize_task_accuracy() -> Dict[str, Dict[str, Any]]:
    """Per-task success rate across all episodes."""
    stats: Dict[str, Dict[str, float]] = {}
    for e in _iter_entries("episode_end"):
        task = e.get("task", "unknown")
        s = stats.setdefault(task, {"total": 0, "success": 0, "reward_sum": 0.0})
        s["total"] += 1
        if e.get("success"):
            s["success"] += 1
        s["reward_sum"] += e.get("reward", 0.0)
    for s in stats.values():
        s["rate"] = round(s["success"] / s["total"], 3) if s["total"] else 0.0
        s["avg_reward"] = round(s["reward_sum"] / s["total"], 3) if s["total"] else 0.0
    return stats


def summarize_backends() -> Dict[str, Dict[str, int]]:
    """Episodes per backend (unity/unreal/mujoco/real)."""
    out: Dict[str, Dict[str, int]] = {}
    for e in _iter_entries("episode_end"):
        b = e.get("backend", "unknown")
        s = out.setdefault(b, {"total": 0, "success": 0})
        s["total"] += 1
        if e.get("success"):
            s["success"] += 1
    return out


def recent_failures(task: Optional[str] = None, limit: int = 10) -> List[dict]:
    rows = [e for e in _iter_entries("episode_end") if not e.get("success")]
    if task:
        rows = [e for e in rows if e.get("task") == task]
    return rows[-limit:]


def total_episodes() -> int:
    return sum(1 for _ in _iter_entries("episode_end"))


# ── Internals ─────────────────────────────────────────────────────────────────

def _log_raw(entry: Dict[str, Any]) -> None:
    _ensure_writer()
    try:
        _write_queue.put_nowait(entry)
    except queue.Full:
        # drop oldest by polling once, then retry
        try:
            _write_queue.get_nowait()
        except queue.Empty:
            pass
        try:
            _write_queue.put_nowait(entry)
        except queue.Full:
            pass


def _ensure_writer() -> None:
    global _writer_thread
    with _writer_lock:
        if _writer_thread and _writer_thread.is_alive():
            return
        _writer_thread = threading.Thread(target=_writer_loop, daemon=True, name="robotics-log")
        _writer_thread.start()


def _writer_loop() -> None:
    while True:
        try:
            entry = _write_queue.get(timeout=5.0)
        except queue.Empty:
            continue
        batch = [entry]
        while len(batch) < 50:
            try:
                batch.append(_write_queue.get_nowait())
            except queue.Empty:
                break
        try:
            with open(LOG_PATH, "a") as f:
                for e in batch:
                    f.write(json.dumps(e, separators=(",", ":")) + "\n")
        except OSError:
            pass  # best-effort


def _truncate(d: Dict[str, Any], max_len: int = 2000) -> Dict[str, Any]:
    """Lossy truncation for huge fields — don't bloat the log with images."""
    try:
        s = json.dumps(d, default=str)
        if len(s) <= max_len:
            return d
        return {"__truncated__": True, "preview": s[:max_len] + "..."}
    except (TypeError, ValueError):
        return {"__unserializable__": True, "repr": repr(d)[:max_len]}


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    cmd = sys.argv[1] if len(sys.argv) > 1 else "stats"
    if cmd == "stats":
        print(f"Log: {LOG_PATH}")
        print(f"Total episodes: {total_episodes()}")
        print("\nPer-task:")
        for task, s in summarize_task_accuracy().items():
            print(f"  {task:24s}  {s['success']}/{s['total']}  "
                  f"rate={s['rate']:.0%}  avg_reward={s['avg_reward']:+.2f}")
        print("\nPer-backend:")
        for b, s in summarize_backends().items():
            print(f"  {b:12s}  {s['success']}/{s['total']}")
    elif cmd == "failures":
        for e in recent_failures(limit=20):
            print(f"  {e['task']:20s}  {e.get('reason','')[:80]}")
    elif cmd == "tail":
        import subprocess
        subprocess.run(["tail", "-n", "30", LOG_PATH])
