from dataclasses import replace
from datetime import datetime, timedelta, timezone

from pyauto.engine import AutomationRule, HardwareAutomationEngine, ResourceSnapshot


class FakeCollector:
    def __init__(self, snapshot: ResourceSnapshot):
        self.snapshot = snapshot

    def collect(self) -> ResourceSnapshot:
        return self.snapshot


def make_snapshot(cpu: float = 0.2, avail_mem: float = 2048) -> ResourceSnapshot:
    return ResourceSnapshot(
        timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
        cpu_load_1m=cpu,
        memory_total_mb=4096,
        memory_available_mb=avail_mem,
        disk_total_mb=102400,
        disk_free_mb=51200,
    )


def test_rule_triggers_when_condition_matches() -> None:
    events: list[str] = []

    rule = AutomationRule(
        name="high_cpu",
        condition=lambda snap: snap.cpu_load_1m > 1.0,
        action=lambda snap: events.append(f"scale:{snap.cpu_load_1m}"),
    )
    engine = HardwareAutomationEngine(FakeCollector(make_snapshot(cpu=2.0)), [rule])

    _snapshot, triggered = engine.run_once()

    assert triggered == ["high_cpu"]
    assert events == ["scale:2.0"]


def test_rule_respects_cooldown() -> None:
    events: list[str] = []
    start = make_snapshot(cpu=2.0)

    rule = AutomationRule(
        name="cooldown_rule",
        condition=lambda snap: True,
        action=lambda snap: events.append("run"),
        cooldown=timedelta(seconds=60),
    )

    assert rule.evaluate(start)
    assert not rule.evaluate(start)

    later = replace(start, timestamp=start.timestamp + timedelta(seconds=61))
    assert rule.evaluate(later)
    assert events == ["run", "run"]
