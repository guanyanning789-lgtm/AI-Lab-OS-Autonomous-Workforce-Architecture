from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable

from ai_lab_os.product_runtime import ProductRuntime, ProductRuntimeTick


RuntimeFactory = Callable[[], ProductRuntime]


@dataclass(frozen=True)
class ProductServiceHealth:
    running: bool
    generation: int
    started_at: str | None
    last_recovery_tick: int | None


class ProductServiceHost:
    """Lifecycle host for the final ProductRuntime.

    A host start creates a fresh runtime instance from a caller-supplied factory.
    Durable state lives outside the runtime (for example in JsonGoalStore), so a
    stop/restart can discard process-local runtime state without losing goals.
    start(recover=True) performs one bounded recovery tick immediately, allowing
    unfinished durable goals to continue after a process/service restart.
    """

    def __init__(self, runtime_factory: RuntimeFactory) -> None:
        self._runtime_factory = runtime_factory
        self._runtime: ProductRuntime | None = None
        self._generation = 0
        self._started_at: str | None = None
        self._last_tick: ProductRuntimeTick | None = None

    @property
    def runtime(self) -> ProductRuntime:
        if self._runtime is None:
            raise RuntimeError("product service is not running")
        return self._runtime

    def start(self, *, recover: bool = True) -> ProductServiceHealth:
        if self._runtime is not None:
            raise RuntimeError("product service is already running")
        self._runtime = self._runtime_factory()
        self._generation += 1
        self._started_at = datetime.now(timezone.utc).isoformat()
        self._last_tick = self._runtime.tick() if recover else None
        return self.health()

    def stop(self) -> ProductServiceHealth:
        if self._runtime is None:
            raise RuntimeError("product service is not running")
        self._runtime = None
        self._started_at = None
        return self.health()

    def restart(self, *, recover: bool = True) -> ProductServiceHealth:
        if self._runtime is not None:
            self.stop()
        return self.start(recover=recover)

    def health(self) -> ProductServiceHealth:
        return ProductServiceHealth(
            running=self._runtime is not None,
            generation=self._generation,
            started_at=self._started_at,
            last_recovery_tick=None if self._last_tick is None else self._last_tick.tick_number,
        )
