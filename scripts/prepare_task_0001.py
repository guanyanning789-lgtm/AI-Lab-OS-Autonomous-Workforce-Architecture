from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


WORKSPACE = Path(r"C:\AI-Lab\worker-v01-smoke")


def run(*args: str) -> None:
    subprocess.run(
        list(args),
        cwd=str(WORKSPACE),
        check=True,
        capture_output=True,
        text=True,
    )


def main() -> int:
    if WORKSPACE.exists():
        shutil.rmtree(WORKSPACE)

    WORKSPACE.mkdir(parents=True)

    (WORKSPACE / "math_ops.py").write_text(
        "def multiply(a, b):\n"
        "    return a + b\n",
        encoding="utf-8",
    )

    (WORKSPACE / "test_math_ops.py").write_text(
        "from math_ops import multiply\n\n\n"
        "def test_multiply():\n"
        "    assert multiply(6, 7) == 42\n",
        encoding="utf-8",
    )

    run("git", "init")
    run("git", "checkout", "-b", "main")
    run("git", "config", "user.email", "ai-lab-worker@local")
    run("git", "config", "user.name", "AI Lab Local Worker")
    run("git", "add", "math_ops.py", "test_math_ops.py")
    run("git", "commit", "-m", "test: seed failing worker smoke task")

    print(f"WORKSPACE = {WORKSPACE}")
    print("BRANCH = main")
    print("INITIAL STATE = intentionally failing")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
