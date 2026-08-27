"""Typed simulation settings shared by the UI and analysis views."""

from __future__ import annotations

from dataclasses import dataclass
from threading import Event

from ...core.models import DuelRequest


@dataclass(frozen=True, slots=True)
class DuelExecutionSettings:
    """UI-owned values mapped directly to the runtime request contract."""

    simulations: int
    seed: int
    batch_size: int
    maximum_rounds: int

    def __post_init__(self) -> None:
        if min(self.simulations, self.batch_size, self.maximum_rounds) < 1:
            raise ValueError("Simulation count, batch size, and maximum rounds must be positive.")

    def request(self, first, second, cancel_event: Event | None = None) -> DuelRequest:
        return DuelRequest(first, second, self.simulations, self.seed, self.batch_size, self.maximum_rounds, cancel_event)
