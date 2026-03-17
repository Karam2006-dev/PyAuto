# PyAuto

PyAuto is a Python library for automating hardware resources with a policy engine.

Instead of writing low-level C/C++ control loops, PyAuto gives you:
- **Fast iteration** with concise Python rule definitions.
- **Safer automation** through typed, testable policy objects.
- **Portable host metrics** from a standard-library collector.

## Install (local)

```bash
pip install -e .
```

## Quick start

```python
from datetime import timedelta

from pyauto import AutomationRule, HardwareAutomationEngine, LocalResourceCollector


def scale_down_workers(snapshot):
    print(f"High CPU: {snapshot.cpu_load_1m:.2f}, scaling down workers")


collector = LocalResourceCollector("/")
engine = HardwareAutomationEngine(collector)
engine.add_rule(
    AutomationRule(
        name="high_cpu_guard",
        condition=lambda snap: snap.cpu_load_1m > 2.0,
        action=scale_down_workers,
        cooldown=timedelta(seconds=30),
    )
)

snapshot, triggered = engine.run_once()
print(snapshot)
print(triggered)
```

## What it automates

`LocalResourceCollector` snapshots:
- 1-minute CPU load average.
- Total and available memory (Linux `/proc/meminfo`).
- Disk total/free space for a path.

`HardwareAutomationEngine` evaluates all rules each cycle and runs matched actions.
