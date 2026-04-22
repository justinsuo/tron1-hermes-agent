"""One-shot dashboard for the robotics self-play log.

Usage:
    python3 ~/tron1-selfplay/dashboard.py            # default stats view
    python3 ~/tron1-selfplay/dashboard.py --recent   # last 20 episodes
    python3 ~/tron1-selfplay/dashboard.py --watch    # refresh every 5s
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import robotics_log  # noqa: E402


def _bar(rate: float, width: int = 20) -> str:
    filled = int(round(rate * width))
    return "█" * filled + "░" * (width - filled)


def render() -> str:
    lines = []
    total = robotics_log.total_episodes()
    lines.append(f"Robotics Self-Play Dashboard")
    lines.append(f"Log: {robotics_log.LOG_PATH}")
    lines.append(f"Total episodes: {total}")
    lines.append("")

    per_task = robotics_log.summarize_task_accuracy()
    if not per_task:
        lines.append("(no episodes yet — run `python3 robotics_selfplay.py --rounds 5`)")
        return "\n".join(lines)

    lines.append("Per-task success rate:")
    for task, s in sorted(per_task.items(), key=lambda kv: kv[1]["rate"]):
        bar = _bar(s["rate"])
        lines.append(
            f"  {task:24s}  {bar}  {int(s['rate']*100):3d}%   "
            f"{s['success']}/{s['total']}  avg_r={s['avg_reward']:+.2f}"
        )

    lines.append("")
    lines.append("Per-backend:")
    for b, s in robotics_log.summarize_backends().items():
        rate = s["success"] / s["total"] if s["total"] else 0.0
        lines.append(f"  {b:12s}  {s['success']}/{s['total']}  {rate:.0%}")

    lines.append("")
    lines.append("Recent failures (top 5):")
    for e in robotics_log.recent_failures(limit=5):
        lines.append(f"  {e['task']:24s}  {e.get('reason','')[:70]}")

    return "\n".join(lines)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--recent", action="store_true")
    p.add_argument("--watch", action="store_true")
    p.add_argument("--interval", type=float, default=5.0)
    args = p.parse_args()

    if args.recent:
        for e in robotics_log._iter_entries("episode_end")[-20:]:
            tag = "OK " if e.get("success") else "FAIL"
            print(f"  {tag}  {e['task']:20s}  r={e.get('reward',0):+.2f}  "
                  f"{e.get('reason','')[:60]}")
        return 0

    if args.watch:
        try:
            while True:
                os.system("clear")
                print(render())
                time.sleep(args.interval)
        except KeyboardInterrupt:
            pass
        return 0

    print(render())
    return 0


if __name__ == "__main__":
    sys.exit(main())
