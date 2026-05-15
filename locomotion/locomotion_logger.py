"""Append-only JSONL log of locomotion commands and outcomes.

Each line is one command attempt. Fields:

    ts                  unix epoch seconds
    command             raw command requested
    clipped_command     command after SafetyLimits.clip
    start_pose          {x, y, z, yaw} before execution
    end_pose            {x, y, z, yaw} after execution
    estimated_distance  euclidean (x, y) between start/end
    yaw_change          radians (wrapped to [-π, π])
    fell                bool (heuristic: base z dropped below threshold)
    collided            bool (placeholder — sim doesn't surface this today)
    success             bool — driver-supplied
    error               str | None
    notes               list of strings (clip notes etc.)

The file is opened ``a+`` per write — robust against concurrent self-play
processes and trivial to ``tail -f``.
"""

from __future__ import annotations

import json
import math
import os
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, Optional


_DEFAULT_LOG = "~/.tron1-locomotion-log.jsonl"


def _wrap_pi(a: float) -> float:
    return (a + math.pi) % (2 * math.pi) - math.pi


class LocomotionLogger:
    """Tiny structured logger.

    Use :py:meth:`log` for one-shot records (already have start+end). Use
    :py:meth:`begin`/:py:meth:`end` when you want the logger to do the
    timing and distance math for you.
    """

    def __init__(self, path: Optional[str] = None, fell_z_threshold: float = 0.45) -> None:
        self._path = Path(os.path.expanduser(path or _DEFAULT_LOG))
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._fell_z = fell_z_threshold

    @property
    def path(self) -> Path:
        return self._path

    # -- one-shot -------------------------------------------------------

    def log(self, record: Dict[str, Any]) -> None:
        record = dict(record)
        record.setdefault("ts", time.time())
        with self._path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, default=str) + "\n")

    # -- begin/end ------------------------------------------------------

    def begin(
        self,
        command: Dict[str, Any],
        clipped_command: Dict[str, Any],
        start_pose: Optional[Dict[str, float]],
    ) -> Dict[str, Any]:
        return {
            "ts": time.time(),
            "command": dict(command),
            "clipped_command": dict(clipped_command),
            "start_pose": dict(start_pose) if start_pose else None,
            "end_pose": None,
            "estimated_distance": None,
            "yaw_change": None,
            "fell": False,
            "collided": False,
            "success": False,
            "error": None,
            "notes": [],
        }

    def end(
        self,
        record: Dict[str, Any],
        end_pose: Optional[Dict[str, float]],
        *,
        success: bool,
        error: Optional[str] = None,
        notes: Optional[list] = None,
        collided: bool = False,
    ) -> Dict[str, Any]:
        record["end_pose"] = dict(end_pose) if end_pose else None
        record["success"] = bool(success)
        record["error"] = error
        record["collided"] = bool(collided)
        if notes:
            record["notes"] = list(record.get("notes", [])) + list(notes)

        sp = record.get("start_pose") or {}
        ep = record.get("end_pose") or {}
        if sp and ep:
            try:
                dx = float(ep.get("x", 0.0)) - float(sp.get("x", 0.0))
                dy = float(ep.get("y", 0.0)) - float(sp.get("y", 0.0))
                record["estimated_distance"] = math.hypot(dx, dy)
            except (TypeError, ValueError):
                record["estimated_distance"] = None
            try:
                record["yaw_change"] = _wrap_pi(
                    float(ep.get("yaw", 0.0)) - float(sp.get("yaw", 0.0))
                )
            except (TypeError, ValueError):
                record["yaw_change"] = None
            try:
                if float(ep.get("z", 1.0)) < self._fell_z:
                    record["fell"] = True
            except (TypeError, ValueError):
                pass

        self.log(record)
        return record
