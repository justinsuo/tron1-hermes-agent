"""Build the policy observation vector from raw sim/robot state.

The layout mirrors LimX's ``pointfoot-legged-gym`` and ``tron1-rl-isaacgym``
locomotion observations:

    [ base_ang_vel (3),
      projected_gravity (3),
      joint_pos_rel (N),    # joint_pos - default_joint_pos
      joint_vel (N),
      last_action (N),
      command (3),
      gait_clock (2, optional) ]

Where ``N`` is the number of actuated joints. For Tron 1 with knees + wheels
the default below is 10. TODO confirm against the URDF you train with.

The exact ordering must match the trained policy. If you change a slot
here you must also re-export the policy or re-train.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence


# Confirmed against robot-description/pointfoot/WF_TRON1A/xml/robot.xml
# (joint definitions, ranges in radians):
#   abad_*  ±0.38 / ±1.40 (hip abduction)
#   hip_*   ±1.01 / ±1.40 (hip pitch)
#   knee_*  ±0.87 / ±1.36 (knee pitch)
#   wheel_* continuous spinning joint (range ±1e6)
# LimX-canonical ordering: left leg first, then right leg, abad → hip →
# knee → wheel within each leg.
JOINT_ORDER: List[str] = [
    "abad_L_Joint", "hip_L_Joint", "knee_L_Joint", "wheel_L_Joint",
    "abad_R_Joint", "hip_R_Joint", "knee_R_Joint", "wheel_R_Joint",
]

# Neutral "standing" pose. The WF_TRON1A spec ships with all hinges at 0
# (the URDF visualizes the robot standing straight) — abad and hip flex
# are bilaterally symmetric. Wheels are continuous joints so their "home"
# position is irrelevant for control; we keep 0.0.
DEFAULT_JOINT_POS: List[float] = [
    0.0, 0.0, 0.0, 0.0,  # left leg
    0.0, 0.0, 0.0, 0.0,  # right leg
]


@dataclass
class ObservationSpec:
    """Describes the observation layout. Used for shape checks and metadata."""
    num_joints: int = len(JOINT_ORDER)
    include_gait_clock: bool = False
    command_dim: int = 3

    @property
    def total_dim(self) -> int:
        d = 3 + 3 + self.num_joints + self.num_joints + self.num_joints + self.command_dim
        if self.include_gait_clock:
            d += 2
        return d


@dataclass
class ObservationBuilder:
    """Assemble policy observations from kwargs.

    Typical usage::

        spec = ObservationSpec()
        builder = ObservationBuilder(spec=spec)
        obs = builder.build(
            base_ang_vel=(0.0, 0.0, 0.0),
            base_quat=(1.0, 0.0, 0.0, 0.0),  # wxyz
            joint_pos=[...],   # len == spec.num_joints
            joint_vel=[...],
            last_action=[...],
            command=(vx, vy, yaw_rate),
            gait_phase=0.0,    # optional, 0..1
        )

    Domain-randomization hook: ``noise_std`` adds gaussian noise to each
    observation slot — set non-zero only during randomized self-play, not
    during real-robot deployment.
    """

    spec: ObservationSpec = field(default_factory=ObservationSpec)
    noise_std: float = 0.0
    rng: random.Random = field(default_factory=random.Random)
    default_joint_pos: List[float] = field(default_factory=lambda: list(DEFAULT_JOINT_POS))

    def __post_init__(self) -> None:
        if len(self.default_joint_pos) != self.spec.num_joints:
            # Pad or trim to match. TODO: surface a louder warning once
            # JOINT_ORDER is finalized for the deployed checkpoint.
            n = self.spec.num_joints
            self.default_joint_pos = (
                list(self.default_joint_pos) + [0.0] * n
            )[:n]

    def build(
        self,
        base_ang_vel: Sequence[float],
        base_quat: Sequence[float],
        joint_pos: Sequence[float],
        joint_vel: Sequence[float],
        last_action: Sequence[float],
        command: Sequence[float],
        gait_phase: Optional[float] = None,
    ) -> List[float]:
        n = self.spec.num_joints
        out: List[float] = []

        out.extend(self._take(base_ang_vel, 3))
        out.extend(self._projected_gravity(base_quat))
        out.extend(
            self._take(joint_pos, n, default=0.0, sub=self.default_joint_pos)
        )
        out.extend(self._take(joint_vel, n))
        out.extend(self._take(last_action, n))
        out.extend(self._take(command, self.spec.command_dim))
        if self.spec.include_gait_clock:
            phase = (gait_phase if gait_phase is not None else 0.0) % 1.0
            out.append(math.sin(2 * math.pi * phase))
            out.append(math.cos(2 * math.pi * phase))

        if self.noise_std > 0.0:
            out = [v + self.rng.gauss(0.0, self.noise_std) for v in out]

        assert len(out) == self.spec.total_dim, (
            f"observation length mismatch: {len(out)} vs {self.spec.total_dim}"
        )
        return out

    # -- helpers --------------------------------------------------------

    @staticmethod
    def _take(
        seq: Sequence[float],
        n: int,
        default: float = 0.0,
        sub: Optional[Sequence[float]] = None,
    ) -> List[float]:
        vals = list(seq)[:n]
        while len(vals) < n:
            vals.append(default)
        if sub is not None:
            sub_list = list(sub)[:n]
            while len(sub_list) < n:
                sub_list.append(0.0)
            vals = [v - s for v, s in zip(vals, sub_list)]
        return [float(v) for v in vals]

    @staticmethod
    def _projected_gravity(quat_wxyz: Sequence[float]) -> List[float]:
        """Gravity in body frame, given world quaternion (w, x, y, z).

        World gravity is ``(0, 0, -1)`` (normalized). Rotating it into the
        body frame gives a 3-vector that tells the policy which way is
        down — the canonical replacement for raw orientation in legged
        locomotion training.
        """
        try:
            w, x, y, z = (float(v) for v in quat_wxyz[:4])
        except (ValueError, TypeError):
            return [0.0, 0.0, -1.0]
        # gravity world = (0, 0, -1)
        # body = R(q)^T @ world. Use the rotation-matrix-by-quaternion
        # formula directly to keep this self-contained.
        gx = -2.0 * (x * z - w * y)
        gy = -2.0 * (y * z + w * x)
        gz = -(1.0 - 2.0 * (x * x + y * y))
        return [gx, gy, gz]


def domain_randomize_defaults(
    builder: ObservationBuilder,
    *,
    joint_pos_std: float = 0.05,
    rng: Optional[random.Random] = None,
) -> None:
    """Perturb the builder's default joint pose by a small amount.

    Cheap stand-in for the full domain-randomization sweep used in Isaac
    Gym training. Real DR also varies mass, friction, motor strength —
    those live on the sim backend, not on the observation builder.
    """
    r = rng or builder.rng
    builder.default_joint_pos = [
        v + r.gauss(0.0, joint_pos_std) for v in builder.default_joint_pos
    ]
