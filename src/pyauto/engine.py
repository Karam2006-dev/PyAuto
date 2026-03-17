"""Policy-based hardware resource automation.

This module provides a high-level automation engine that can monitor host
resources (CPU, memory and disk) and trigger user-defined actions when
conditions are met.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from shutil import disk_usage
from threading import Event
from time import sleep
from typing import Callable, Iterable, Protocol
import os


@dataclass(slots=True, frozen=True)
class ResourceSnapshot:
    """Current host resource metrics."""

    timestamp: datetime
    cpu_load_1m: float
    memory_total_mb: float
    memory_available_mb: float
    disk_total_mb: float
    disk_free_mb: float


class Collector(Protocol):
    """Interface for collecting resource snapshots."""

    def collect(self) -> ResourceSnapshot:
        """Collect current host resource metrics."""


class Action(Protocol):
    """Interface for automation actions."""

    def __call__(self, snapshot: ResourceSnapshot) -> None:
        """Execute a side effect based on a resource snapshot."""


Condition = Callable[[ResourceSnapshot], bool]


@dataclass(slots=True)
class AutomationRule:
    """Condition + action pair with optional cooldown and a name."""

    name: str
    condition: Condition
    action: Action
    cooldown: timedelta = field(default=timedelta(0))
    _last_triggered_at: datetime | None = field(default=None, init=False, repr=False)

    def evaluate(self, snapshot: ResourceSnapshot) -> bool:
        """Evaluate and trigger the action when allowed.

        Returns True when the action was executed.
        """

        if not self.condition(snapshot):
            return False

        if self._last_triggered_at is not None:
            elapsed = snapshot.timestamp - self._last_triggered_at
            if elapsed < self.cooldown:
                return False

        self.action(snapshot)
        self._last_triggered_at = snapshot.timestamp
        return True


class LocalResourceCollector:
    """Collect host metrics using the Python standard library.

    The collector reads:
    - CPU load: 1-minute load average where available.
    - Memory: from /proc/meminfo (Linux) when present.
    - Disk: filesystem stats for a configurable path.
    """

    def __init__(self, disk_path: str | Path = "/") -> None:
        self.disk_path = Path(disk_path)

    def collect(self) -> ResourceSnapshot:
        now = datetime.now(timezone.utc)

        try:
            cpu_load_1m = os.getloadavg()[0]
        except (AttributeError, OSError):
            cpu_load_1m = 0.0

        memory_total_mb, memory_available_mb = _read_memory_from_proc()

        disk = disk_usage(self.disk_path)
        disk_total_mb = disk.total / (1024 * 1024)
        disk_free_mb = disk.free / (1024 * 1024)

        return ResourceSnapshot(
            timestamp=now,
            cpu_load_1m=cpu_load_1m,
            memory_total_mb=memory_total_mb,
            memory_available_mb=memory_available_mb,
            disk_total_mb=disk_total_mb,
            disk_free_mb=disk_free_mb,
        )


class HardwareAutomationEngine:
    """Main loop that evaluates rules against fresh snapshots."""

    def __init__(self, collector: Collector, rules: Iterable[AutomationRule] | None = None) -> None:
        self.collector = collector
        self.rules: list[AutomationRule] = list(rules or [])

    def add_rule(self, rule: AutomationRule) -> None:
        self.rules.append(rule)

    def run_once(self) -> tuple[ResourceSnapshot, list[str]]:
        snapshot = self.collector.collect()
        triggered = [rule.name for rule in self.rules if rule.evaluate(snapshot)]
        return snapshot, triggered

    def run_forever(self, interval_seconds: float = 1.0, stop_event: Event | None = None) -> None:
        gate = stop_event or Event()
        while not gate.is_set():
            self.run_once()
            sleep(interval_seconds)


def _read_memory_from_proc() -> tuple[float, float]:
    meminfo_path = Path("/proc/meminfo")
    if not meminfo_path.exists():
        return 0.0, 0.0

    values_kb: dict[str, int] = {}
    for line in meminfo_path.read_text(encoding="utf-8").splitlines():
        if ":" not in line:
            continue
        key, remainder = line.split(":", 1)
        parts = remainder.strip().split()
        if not parts:
            continue
        try:
            values_kb[key] = int(parts[0])
        except ValueError:
            continue

    total_mb = values_kb.get("MemTotal", 0) / 1024
    available_mb = values_kb.get("MemAvailable", values_kb.get("MemFree", 0)) / 1024
    return total_mb, available_mb
