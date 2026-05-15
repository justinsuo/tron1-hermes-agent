"""Locomotion layer for the Tron 1 Hermes agent.

This package sits between Hermes (high-level cognition) and the low-level
robot interface (MuJoCo sim today, RL policy + real robot later).

Public surface:

    from locomotion import (
        PolicyInterface, FakePolicyRunner, PolicyRunner,
        ObservationBuilder, CommandAdapter, LocomotionLogger,
    )

Everything else is internal.
"""

from .command_adapter import CommandAdapter, LocomotionCommand, SafetyLimits
from .fake_policy_runner import FakePolicyRunner
from .locomotion_logger import LocomotionLogger
from .observation_builder import ObservationBuilder, ObservationSpec
from .policy_interface import PolicyInterface
from .policy_runner import PolicyRunner, PolicyLoadError

__all__ = [
    "PolicyInterface",
    "FakePolicyRunner",
    "PolicyRunner",
    "PolicyLoadError",
    "ObservationBuilder",
    "ObservationSpec",
    "CommandAdapter",
    "LocomotionCommand",
    "SafetyLimits",
    "LocomotionLogger",
]
