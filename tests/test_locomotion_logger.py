import json
import math
from pathlib import Path

import pytest

from locomotion import LocomotionLogger


def _read_lines(path: Path):
    return [json.loads(l) for l in path.read_text().splitlines() if l.strip()]


def test_log_writes_single_line(tmp_path: Path):
    p = tmp_path / "loco.jsonl"
    logger = LocomotionLogger(path=str(p))
    logger.log({"command": {"vx": 0.4}, "success": True})
    lines = _read_lines(p)
    assert len(lines) == 1
    assert lines[0]["command"]["vx"] == 0.4
    assert "ts" in lines[0]


def test_begin_end_computes_distance(tmp_path: Path):
    p = tmp_path / "loco.jsonl"
    logger = LocomotionLogger(path=str(p))
    rec = logger.begin(
        command={"vx": 0.4, "duration": 1.0},
        clipped_command={"vx": 0.4, "duration": 1.0},
        start_pose={"x": 0.0, "y": 0.0, "z": 0.92, "yaw": 0.0},
    )
    logger.end(rec,
               end_pose={"x": 0.4, "y": 0.0, "z": 0.92, "yaw": 0.0},
               success=True)
    line = _read_lines(p)[0]
    assert line["estimated_distance"] == pytest.approx(0.4)
    assert line["yaw_change"] == pytest.approx(0.0)
    assert line["fell"] is False
    assert line["success"] is True


def test_fell_detected_when_base_z_drops(tmp_path: Path):
    p = tmp_path / "loco.jsonl"
    logger = LocomotionLogger(path=str(p), fell_z_threshold=0.5)
    rec = logger.begin(
        command={}, clipped_command={},
        start_pose={"x": 0, "y": 0, "z": 0.92, "yaw": 0},
    )
    logger.end(rec,
               end_pose={"x": 0.1, "y": 0.0, "z": 0.2, "yaw": 0.0},
               success=False, error="base z dropped")
    line = _read_lines(p)[0]
    assert line["fell"] is True
    assert line["error"] == "base z dropped"


def test_yaw_change_wraps_pi(tmp_path: Path):
    p = tmp_path / "loco.jsonl"
    logger = LocomotionLogger(path=str(p))
    rec = logger.begin(
        command={}, clipped_command={},
        start_pose={"x": 0, "y": 0, "z": 1.0, "yaw": math.pi - 0.1},
    )
    logger.end(rec,
               end_pose={"x": 0, "y": 0, "z": 1.0, "yaw": -math.pi + 0.1},
               success=True)
    line = _read_lines(p)[0]
    # Real angular distance is 0.2 rad, not 2π - 0.2.
    assert abs(line["yaw_change"]) < 0.3


def test_collided_flag_passes_through(tmp_path: Path):
    p = tmp_path / "loco.jsonl"
    logger = LocomotionLogger(path=str(p))
    rec = logger.begin(command={}, clipped_command={},
                       start_pose={"x": 0, "y": 0, "z": 1.0, "yaw": 0})
    logger.end(rec, end_pose={"x": 0, "y": 0, "z": 1.0, "yaw": 0},
               success=False, collided=True, error="bump")
    line = _read_lines(p)[0]
    assert line["collided"] is True


def test_multiple_appends_stay_separate_lines(tmp_path: Path):
    p = tmp_path / "loco.jsonl"
    logger = LocomotionLogger(path=str(p))
    for _ in range(5):
        logger.log({"x": 1})
    assert len(_read_lines(p)) == 5
