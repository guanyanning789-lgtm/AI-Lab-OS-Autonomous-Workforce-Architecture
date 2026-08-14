from __future__ import annotations

import importlib.util
from pathlib import Path

TARGET = Path(r"C:\AI-Lab\worker-v01-smoke\math_ops.py")


def _load_target_module():
    spec = importlib.util.spec_from_file_location("worker_v01_math_ops_task4", TARGET)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_multiply_four_is_available_and_correct():
    module = _load_target_module()
    assert hasattr(module, "multiply_four")
    assert module.multiply_four(2, 3, 4, 5) == 120
