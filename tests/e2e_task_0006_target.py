from __future__ import annotations

import importlib.util
import os
from pathlib import Path


def _target_path() -> Path:
    repository = os.environ.get("AI_LAB_TASK_REPOSITORY")
    if repository:
        return Path(repository) / "math_ops.py"
    return Path(r"C:\AI-Lab\worker-v01-smoke\math_ops.py")


def _load_target_module():
    target = _target_path()
    spec = importlib.util.spec_from_file_location("worker_v01_math_ops_task6", target)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_geometric_mean_is_available_and_correct():
    module = _load_target_module()
    assert hasattr(module, "geometric_mean")
    assert module.geometric_mean([1, 4, 16]) == 4
