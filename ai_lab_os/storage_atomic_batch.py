from __future__ import annotations

import hashlib
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


@dataclass(frozen=True)
class AtomicMove:
    source: Path
    destination: Path
    sha256: str


@dataclass(frozen=True)
class AtomicBatchResult:
    ok: bool
    failed_index: int | None
    executed: int
    rolled_back: int
    restored: bool
    message: str


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(1024 * 1024):
            h.update(chunk)
    return h.hexdigest()


def execute_atomic_batch(
    moves: tuple[AtomicMove, ...],
    *,
    before_move: Callable[[int, AtomicMove], None] | None = None,
) -> AtomicBatchResult:
    completed: list[AtomicMove] = []
    try:
        for index, move in enumerate(moves, 1):
            if before_move is not None:
                before_move(index, move)
            if not move.source.is_file():
                raise RuntimeError(f"source missing at item {index}")
            if move.destination.exists():
                raise RuntimeError(f"destination occupied at item {index}")
            if _sha256(move.source) != move.sha256:
                raise RuntimeError(f"source hash mismatch at item {index}")
            move.destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(move.source), str(move.destination))
            if not move.destination.is_file() or _sha256(move.destination) != move.sha256:
                raise RuntimeError(f"post-move verification failed at item {index}")
            completed.append(move)
    except Exception as exc:
        rollback_count = 0
        restored = True
        for move in reversed(completed):
            try:
                if move.source.exists() or not move.destination.is_file() or _sha256(move.destination) != move.sha256:
                    restored = False
                    continue
                move.source.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(move.destination), str(move.source))
                if not move.source.is_file() or _sha256(move.source) != move.sha256:
                    restored = False
                else:
                    rollback_count += 1
            except OSError:
                restored = False
        return AtomicBatchResult(False, len(completed) + 1, len(completed), rollback_count, restored, str(exc))
    return AtomicBatchResult(True, None, len(completed), 0, True, "atomic batch completed")
