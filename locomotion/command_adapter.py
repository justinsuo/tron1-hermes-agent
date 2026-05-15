"""Translate Hermes-level intent into locomotion-level commands.

Two layers of translation:

  1. Hermes tool call (``tron1_walk_command(vx=..., vy=..., yaw_rate=...,
     duration=...)``) becomes a :class:`LocomotionCommand` after clipping
     against :class:`SafetyLimits`.

  2. The locomotion command is then either:
       - normalized into a 3-vector ``[vx, vy, yaw_rate]`` for the
         policy's command input, or
       - passed through to the kinematic backend as a velocity setpoint
         (when running with FakePolicyRunner).

We keep both paths explicit so a future RL-policy swap is just a runner
change, not a command rewrite.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Dict, List, Optional, Tuple


@dataclass(frozen=True)
class SafetyLimits:
    """Hard bounds enforced on every command before execution."""

    max_vx: float = 0.8        # m/s — Tron 1 small wheels; >1.0 visually wrong
    max_vy: float = 0.4        # m/s — lateral motion is harder, cap tighter
    max_yaw_rate: float = 0.8  # rad/s — tipping risk on the real robot
    max_duration: float = 2.0  # seconds — re-read pose between bursts

    def clip(
        self,
        vx: float, vy: float, yaw_rate: float, duration: float
    ) -> Tuple[float, float, float, float, List[str]]:
        """Clamp inputs and report which fields were modified."""
        notes: List[str] = []

        def _clip(name: str, v: float, lo: float, hi: float) -> float:
            if v < lo:
                notes.append(f"{name} clipped {v:+.2f}→{lo:+.2f}")
                return lo
            if v > hi:
                notes.append(f"{name} clipped {v:+.2f}→{hi:+.2f}")
                return hi
            return v

        vx_c = _clip("vx", vx, -self.max_vx, self.max_vx)
        vy_c = _clip("vy", vy, -self.max_vy, self.max_vy)
        yaw_c = _clip("yaw_rate", yaw_rate, -self.max_yaw_rate, self.max_yaw_rate)
        dur_c = _clip("duration", duration, 0.0, self.max_duration)
        return vx_c, vy_c, yaw_c, dur_c, notes


@dataclass(frozen=True)
class LocomotionCommand:
    """Validated movement intent ready for execution."""

    vx: float
    vy: float
    yaw_rate: float
    duration: float
    target_pose: Optional[Tuple[float, float, float]] = None  # optional (x, y, yaw)
    clip_notes: Tuple[str, ...] = ()

    def as_policy_command(self) -> List[float]:
        """3-vector consumed by a LimX-style policy command input."""
        return [float(self.vx), float(self.vy), float(self.yaw_rate)]

    def as_velocity_setpoint(self) -> Dict[str, float]:
        """Velocity setpoint for the kinematic MuJoCo backend.

        Tron 1's existing ``tron1_velocity`` only carries (linear, angular,
        duration). We map vx → linear, yaw_rate → angular, and warn via
        ``clip_notes`` if vy is non-zero (the kinematic backend ignores it).
        """
        return {
            "linear": float(self.vx),
            "angular": float(self.yaw_rate),
            "duration": float(self.duration),
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "vx": self.vx, "vy": self.vy,
            "yaw_rate": self.yaw_rate, "duration": self.duration,
            "target_pose": list(self.target_pose) if self.target_pose else None,
            "clip_notes": list(self.clip_notes),
        }


@dataclass
class CommandAdapter:
    """Validate, clip, and package a raw Hermes-level request."""

    limits: SafetyLimits = field(default_factory=SafetyLimits)

    def build(
        self,
        vx: float = 0.0,
        vy: float = 0.0,
        yaw_rate: float = 0.0,
        duration: float = 1.0,
        target_pose: Optional[Tuple[float, float, float]] = None,
    ) -> LocomotionCommand:
        try:
            vx, vy, yaw_rate, duration = (
                float(vx), float(vy), float(yaw_rate), float(duration)
            )
        except (TypeError, ValueError) as e:
            raise ValueError(f"non-numeric command field: {e}") from e

        for name, val in (
            ("vx", vx), ("vy", vy), ("yaw_rate", yaw_rate), ("duration", duration)
        ):
            if not _isfinite(val):
                raise ValueError(f"{name} is not finite ({val!r})")

        vx_c, vy_c, yaw_c, dur_c, notes = self.limits.clip(vx, vy, yaw_rate, duration)
        return LocomotionCommand(
            vx=vx_c, vy=vy_c, yaw_rate=yaw_c, duration=dur_c,
            target_pose=target_pose,
            clip_notes=tuple(notes),
        )


def _isfinite(v: float) -> bool:
    import math
    return math.isfinite(v)
