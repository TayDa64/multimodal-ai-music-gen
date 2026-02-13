"""
Critics — Quality Gate Metrics for Generated Music

Lightweight, O(n) quality metrics that run **without** an LLM.
Each critic computes a single scalar, compares it against a threshold,
and returns a pass/fail verdict with explanatory detail.

Metrics:
    VLC  — Voice Leading Cost (avg semitone movement per chord change)
    BKAS — Bass-Kick Alignment Score (% of kick hits near a bass note)
    ADC  — Arrangement Density Curve (tension–density correlation)

Usage::

    from multimodal_gen.intelligence.critics import run_all_critics

    report = run_all_critics(
        voicings=[[60, 64, 67], [60, 63, 67]],
        bass_notes=[{"tick": 0}, {"tick": 480}],
        kick_ticks=[0, 480],
        tension_curve=[0.3, 0.5, 0.7, 0.6],
        note_density_per_beat=[2.0, 3.0, 4.5, 3.5],
    )
    print(report.summary)
"""

from __future__ import annotations

import logging
import math
import statistics
from dataclasses import dataclass, field
from typing import List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class CriticResult:
    """Result of a single quality-gate metric."""
    name: str
    value: float
    threshold: float
    passed: bool
    details: str


@dataclass
class CriticReport:
    """Aggregated report from all critics."""
    metrics: List[CriticResult]
    overall_passed: bool
    summary: str


# ---------------------------------------------------------------------------
# VLC — Voice Leading Cost
# ---------------------------------------------------------------------------

def compute_vlc(voicings: List[List[int]]) -> CriticResult:
    """Voice Leading Cost — average semitone movement per chord change.

    For each consecutive pair of voicings, computes the sum of absolute
    pitch differences between aligned notes (shortest list is padded by
    repeating its last note), then divides by the number of notes.
    The final metric is the mean across all transitions.

    Lower is smoother.  *Threshold < 3.0 semitones* per voice on
    average.

    Args:
        voicings: List of voicings, each a list of MIDI note numbers.

    Returns:
        :class:`CriticResult` with ``name="VLC"``.
    """
    threshold = 3.0

    if len(voicings) < 2:
        return CriticResult(
            name="VLC",
            value=0.0,
            threshold=threshold,
            passed=True,
            details="Fewer than 2 voicings — nothing to measure.",
        )

    # Filter out empty voicings to avoid IndexError on a[-1]
    voicings = [v for v in voicings if v]

    if len(voicings) < 2:
        return CriticResult(
            name="VLC",
            value=0.0,
            threshold=threshold,
            passed=True,
            details="Fewer than 2 non-empty voicings — nothing to measure.",
        )

    costs: List[float] = []
    for i in range(1, len(voicings)):
        a = sorted(voicings[i - 1])
        b = sorted(voicings[i])

        # Pad shorter to match longer
        while len(a) < len(b):
            a.append(a[-1] if a else 60)
        while len(b) < len(a):
            b.append(b[-1] if b else 60)

        cost = sum(abs(x - y) for x, y in zip(a, b)) / max(len(a), 1)
        costs.append(cost)

    avg_cost = statistics.mean(costs)
    passed = avg_cost < threshold

    details = (
        f"Avg voice-leading cost: {avg_cost:.2f} semitones/voice over "
        f"{len(costs)} transition(s). "
        f"{'Smooth voice leading.' if passed else 'Large jumps detected — consider closer voicings.'}"
    )

    return CriticResult(
        name="VLC",
        value=round(avg_cost, 4),
        threshold=threshold,
        passed=passed,
        details=details,
    )


# ---------------------------------------------------------------------------
# BKAS — Bass-Kick Alignment Score
# ---------------------------------------------------------------------------

def compute_bkas(
    bass_notes: List[dict],
    kick_ticks: List[int],
    tolerance_ticks: int = 60,
) -> CriticResult:
    """Bass-Kick Alignment Score — fraction of kick hits near a bass note.

    For each kick tick, checks whether any bass note's ``tick`` field is
    within *tolerance_ticks*.  A score of 1.0 means every kick hit
    co-occurs with a bass note.

    *Threshold > 0.70* (70 %).

    Args:
        bass_notes: List of dicts with at least a ``"tick"`` key (int).
        kick_ticks: List of kick-drum event ticks.
        tolerance_ticks: Maximum distance in ticks to count as aligned.
                         Default 60 (≈ 1/8 of a 16th note at 480 PPQ).

    Returns:
        :class:`CriticResult` with ``name="BKAS"``.
    """
    threshold = 0.70

    if not kick_ticks:
        return CriticResult(
            name="BKAS",
            value=1.0,
            threshold=threshold,
            passed=True,
            details="No kick events — nothing to measure.",
        )

    bass_ticks = sorted(bn.get("tick", bn.get("start_tick", 0)) for bn in bass_notes)

    aligned = 0
    for kt in kick_ticks:
        # Binary-style scan is possible but O(n) is fine for typical sizes
        for bt in bass_ticks:
            if abs(kt - bt) <= tolerance_ticks:
                aligned += 1
                break

    score = aligned / len(kick_ticks)
    passed = score >= threshold

    details = (
        f"{aligned}/{len(kick_ticks)} kick hits aligned with bass "
        f"(tolerance ±{tolerance_ticks} ticks). "
        f"Score: {score:.1%}. "
        f"{'Good bass-kick lock.' if passed else 'Bass and kick are misaligned — tighten pocket.'}"
    )

    return CriticResult(
        name="BKAS",
        value=round(score, 4),
        threshold=threshold,
        passed=passed,
        details=details,
    )


# ---------------------------------------------------------------------------
# ADC — Arrangement Density Curve
# ---------------------------------------------------------------------------

def _pearson_correlation(xs: List[float], ys: List[float]) -> float:
    """Pearson correlation coefficient.  Returns 0.0 on degenerate input."""
    n = min(len(xs), len(ys))
    if n < 2:
        return 0.0

    xs, ys = xs[:n], ys[:n]
    mean_x = statistics.mean(xs)
    mean_y = statistics.mean(ys)

    num = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    den_x = math.sqrt(sum((x - mean_x) ** 2 for x in xs))
    den_y = math.sqrt(sum((y - mean_y) ** 2 for y in ys))

    if den_x == 0.0 or den_y == 0.0:
        return 0.0
    return num / (den_x * den_y)


def compute_adc(
    tension_curve: List[float],
    note_density_per_beat: List[float],
) -> CriticResult:
    """Arrangement Density Curve — tension–density correlation.

    A well-arranged piece should show positive correlation between the
    intended tension curve and the actual note density per beat.

    *Threshold > 0.6* (Pearson r).

    Args:
        tension_curve: Per-beat or per-bar tension values (0–1).
        note_density_per_beat: Notes-per-beat in matching time slices.

    Returns:
        :class:`CriticResult` with ``name="ADC"``.
    """
    threshold = 0.6

    n = min(len(tension_curve), len(note_density_per_beat))
    if n < 2:
        return CriticResult(
            name="ADC",
            value=0.0,
            threshold=threshold,
            passed=False,
            details="Not enough data points to compute correlation.",
        )

    r = _pearson_correlation(tension_curve[:n], note_density_per_beat[:n])
    passed = r >= threshold

    details = (
        f"Pearson r between tension and density over {n} time-slices: "
        f"{r:.3f}. "
        f"{'Density follows tension well.' if passed else 'Density is decoupled from tension — revise arrangement.'}"
    )

    return CriticResult(
        name="ADC",
        value=round(r, 4),
        threshold=threshold,
        passed=passed,
        details=details,
    )


# ---------------------------------------------------------------------------
# Aggregate runner
# ---------------------------------------------------------------------------

def run_all_critics(
    voicings: Optional[List[List[int]]] = None,
    bass_notes: Optional[List[dict]] = None,
    kick_ticks: Optional[List[int]] = None,
    tolerance_ticks: int = 60,
    tension_curve: Optional[List[float]] = None,
    note_density_per_beat: Optional[List[float]] = None,
) -> CriticReport:
    """Run all quality-gate critics and return a unified report.

    Any input that is ``None`` or empty will still produce a
    :class:`CriticResult` (generally a trivial pass), so callers need
    not guard against missing data.

    Args:
        voicings: Chord voicings for VLC.
        bass_notes: Bass note dicts for BKAS.
        kick_ticks: Kick event ticks for BKAS.
        tolerance_ticks: BKAS alignment tolerance (default 60).
        tension_curve: Tension values for ADC.
        note_density_per_beat: Note density for ADC.

    Returns:
        :class:`CriticReport` with all metrics and an overall verdict.
    """
    metrics: List[CriticResult] = []

    vlc = compute_vlc(voicings or [])
    metrics.append(vlc)

    bkas = compute_bkas(bass_notes or [], kick_ticks or [], tolerance_ticks)
    metrics.append(bkas)

    adc = compute_adc(tension_curve or [], note_density_per_beat or [])
    metrics.append(adc)

    overall = all(m.passed for m in metrics)
    passed_count = sum(1 for m in metrics if m.passed)
    total = len(metrics)

    lines = [f"  {m.name}: {'PASS' if m.passed else 'FAIL'} ({m.value:.3f})" for m in metrics]
    summary = (
        f"Quality gate: {passed_count}/{total} critics passed"
        f" — {'ALL PASS' if overall else 'GATE FAILED'}.\n"
        + "\n".join(lines)
    )

    logger.info("Critics report: %d/%d passed", passed_count, total)
    return CriticReport(metrics=metrics, overall_passed=overall, summary=summary)
