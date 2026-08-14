from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_target_module():
    repository = Path(r"C:\AI-Lab\worker-v01-smoke")
    source = repository / "math_ops.py"
    spec = importlib.util.spec_from_file_location("worker_v01_math_ops_task8", source)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_quadratic_mean_is_available_and_correct():
    module = _load_target_module()
    assert hasattr(module, "quadratic_mean")
    assert module.quadratic_mean([3, 4]) == 5 / (2 ** 0.5)
