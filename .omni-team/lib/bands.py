"""
Control bands — deterministic thresholds over production metrics (optional, `project/bands.yaml`).

    version: 1
    metrics:
      error_rate:              # key in the metrics JSON the job collected
        direction: up          # up (default): higher is worse · down: lower is worse
        log: 0.01              # at or beyond → log only
        diagnose: 0.02         # → an agent diagnoses (read-only)
        propose: 0.05          # → an agent proposes a change: `ba` writes the incident spec
        owner: payments-oncall # optional, shown in the report

omni-team collects nothing: a cron or CI job gathers the numbers into a flat JSON object
({"error_rate": 0.031, ...}) and runs `orchestrator.py bands --metrics <file>`, so the LLM is
called only on a breach. A metric missing from the JSON counts as `diagnose` (the collection
itself broke). Stdlib only.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

BANDS = ("normal", "log", "diagnose", "propose")       # ordered by severity
THRESHOLDS = BANDS[1:]
EXIT_BY_BAND = {"normal": 0, "log": 0, "diagnose": 1, "propose": 6}


class BandsError(Exception):
    pass


@dataclass
class Metric:
    name: str
    direction: str
    thresholds: Dict[str, float]
    owner: str = ""


@dataclass
class Result:
    metric: Metric
    value: Optional[float]
    band: str


def parse(spec: Dict[str, Any]) -> List[Metric]:
    raw = spec.get("metrics")
    if not isinstance(raw, dict) or not raw:
        raise BandsError("bands file needs a non-empty `metrics` mapping")
    metrics = []
    for name, entry in raw.items():
        if not isinstance(entry, dict):
            raise BandsError(f"metric {name}: expected a mapping")
        direction = entry.get("direction", "up")
        if direction not in ("up", "down"):
            raise BandsError(f"metric {name}: direction must be up or down, got {direction!r}")
        levels = {band: entry[band] for band in THRESHOLDS if band in entry}
        if not levels:
            raise BandsError(f"metric {name}: set at least one of {', '.join(THRESHOLDS)}")
        if not all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in levels.values()):
            raise BandsError(f"metric {name}: thresholds must be numbers")
        ordered = [levels[b] for b in THRESHOLDS if b in levels]
        if ordered != sorted(ordered, reverse=direction == "down"):
            worse = "higher" if direction == "up" else "lower"
            raise BandsError(f"metric {name}: each band must be {worse} than the one before ({', '.join(THRESHOLDS)})")
        metrics.append(Metric(str(name), direction, {k: float(v) for k, v in levels.items()}, str(entry.get("owner", ""))))
    return metrics


def classify(metric: Metric, value: Optional[float]) -> str:
    if value is None:
        return "diagnose"
    band = "normal"
    for name in THRESHOLDS:
        limit = metric.thresholds.get(name)
        if limit is not None and (value >= limit if metric.direction == "up" else value <= limit):
            band = name
    return band


def load_metrics(text: str) -> Dict[str, Any]:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise BandsError(f"metrics file is not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise BandsError("metrics file must be a JSON object of metric name → number")
    return data


def evaluate(metrics: List[Metric], values: Dict[str, Any]) -> List[Result]:
    results = []
    for m in metrics:
        raw = values.get(m.name)
        value = float(raw) if isinstance(raw, (int, float)) and not isinstance(raw, bool) else None
        results.append(Result(m, value, classify(m, value)))
    return results


def exit_code(results: List[Result]) -> int:
    worst = max((BANDS.index(r.band) for r in results), default=0)
    return EXIT_BY_BAND[BANDS[worst]]


def render(results: List[Result]) -> str:
    icons = {"normal": "✅", "log": "📝", "diagnose": "🔎", "propose": "🚨"}
    lines = []
    for r in results:
        shown = "missing" if r.value is None else f"{r.value:g}"
        limits = ", ".join(f"{k} {'≥' if r.metric.direction == 'up' else '≤'} {v:g}" for k, v in r.metric.thresholds.items())
        owner = f" — owner {r.metric.owner}" if r.metric.owner else ""
        lines.append(f"{icons[r.band]} {r.metric.name} = {shown}: {r.band} ({limits}){owner}")
    worst = BANDS[max((BANDS.index(r.band) for r in results), default=0)]
    lines.append({"normal": "→ nothing to do", "log": "→ log only; no agent needed",
                  "diagnose": "→ diagnose: an agent investigates read-only and reports",
                  "propose": "→ propose: `ba` writes the incident spec in runs/<id>/; the normal flow follows"}[worst])
    return "\n".join(lines)
