"""
Preference Tracking — Contract C14

Persistent user preference profile that learns from implicit signals
(accept, reject, modify, request, ignore, repeat) using exponential
moving-average (EMA) updates.

Persistence path: ``~/.muse/user-preferences.json``
"""

from __future__ import annotations

import json
import logging
import math
import os
import random
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Signal type → default alpha (learning rate)
# ---------------------------------------------------------------------------

_ALPHA_MAP: Dict[str, float] = {
    "accept": 0.10,
    "reject": 0.10,
    "modify": 0.08,
    "request": 0.12,
    "ignore": 0.05,
    "repeat": 0.15,
}

# Dimension → domain mapping (for convenience helpers)
_DOMAIN_TO_DIMENSION: Dict[str, str] = {
    "harmony": "harmonic_complexity",
    "rhythm": "rhythmic_density",
    "sound": "timbral_brightness",
    "arrangement": "arrangement_density",
    "mix": "production_cleanness",
    "genre": "experimental_tendency",
    "creativity": "experimental_tendency",
}

_DIMENSION_NAMES = [
    "harmonic_complexity",
    "rhythmic_density",
    "timbral_brightness",
    "arrangement_density",
    "experimental_tendency",
    "energy_level",
    "production_cleanness",
]


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class PreferenceDimensions:
    """7 core preference dimensions, normalised 0.0–1.0.

    Defaults to 0.5 on every axis (cold start).
    """

    harmonic_complexity: float = 0.5
    rhythmic_density: float = 0.5
    timbral_brightness: float = 0.5
    arrangement_density: float = 0.5
    experimental_tendency: float = 0.5
    energy_level: float = 0.5
    production_cleanness: float = 0.5

    def to_dict(self) -> Dict[str, float]:
        return {
            "harmonic_complexity": self.harmonic_complexity,
            "rhythmic_density": self.rhythmic_density,
            "timbral_brightness": self.timbral_brightness,
            "arrangement_density": self.arrangement_density,
            "experimental_tendency": self.experimental_tendency,
            "energy_level": self.energy_level,
            "production_cleanness": self.production_cleanness,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> PreferenceDimensions:
        return cls(
            harmonic_complexity=float(data.get("harmonic_complexity", 0.5)),
            rhythmic_density=float(data.get("rhythmic_density", 0.5)),
            timbral_brightness=float(data.get("timbral_brightness", 0.5)),
            arrangement_density=float(data.get("arrangement_density", 0.5)),
            experimental_tendency=float(data.get("experimental_tendency", 0.5)),
            energy_level=float(data.get("energy_level", 0.5)),
            production_cleanness=float(data.get("production_cleanness", 0.5)),
        )


@dataclass
class PreferenceSignal:
    """Implicit preference signal from user interaction."""

    timestamp: str
    signal_type: str  # "accept", "reject", "modify", "request", "ignore", "repeat"
    domain: str  # "harmony", "rhythm", "sound", "arrangement", "mix", "genre", "creativity"
    dimension: str  # key from PreferenceDimensions
    direction: str  # "increase", "decrease", "neutral"
    confidence: float  # 0.0–1.0
    context: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SessionSummary:
    """Summary of a completed generation session."""

    date: str
    duration_minutes: float
    genres_used: List[str]
    average_critic_score: float
    accept_rate: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "date": self.date,
            "duration_minutes": self.duration_minutes,
            "genres_used": list(self.genres_used),
            "average_critic_score": self.average_critic_score,
            "accept_rate": self.accept_rate,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> SessionSummary:
        return cls(
            date=str(data.get("date", "")),
            duration_minutes=float(data.get("duration_minutes", 0.0)),
            genres_used=list(data.get("genres_used", [])),
            average_critic_score=float(data.get("average_critic_score", 0.0)),
            accept_rate=float(data.get("accept_rate", 0.0)),
        )


@dataclass
class UserPreferences:
    """Persistent user preference profile (Contract C14)."""

    version: int = 1
    last_updated: str = ""
    dimensions: PreferenceDimensions = field(default_factory=PreferenceDimensions)
    genre_affinities: Dict[str, float] = field(default_factory=dict)
    tempo_range: Tuple[float, float] = (70.0, 140.0)
    key_preferences: List[str] = field(default_factory=list)
    signal_count: int = 0
    confidence: float = 0.3  # min(1.0, 0.3 + 0.15 * log2(signal_count + 1))
    exploration_budget: float = 0.30  # epsilon-greedy [0.10, 0.30]
    session_history: List[SessionSummary] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "last_updated": self.last_updated,
            "dimensions": self.dimensions.to_dict(),
            "genre_affinities": dict(self.genre_affinities),
            "tempo_range": list(self.tempo_range),
            "key_preferences": list(self.key_preferences),
            "signal_count": self.signal_count,
            "confidence": self.confidence,
            "exploration_budget": self.exploration_budget,
            "session_history": [s.to_dict() for s in self.session_history],
        }

    @classmethod
    def from_dict(cls, data: dict) -> UserPreferences:
        tr = data.get("tempo_range", [70.0, 140.0])
        return cls(
            version=int(data.get("version", 1)),
            last_updated=str(data.get("last_updated", "")),
            dimensions=PreferenceDimensions.from_dict(data.get("dimensions", {})),
            genre_affinities={
                str(k): float(v)
                for k, v in data.get("genre_affinities", {}).items()
            },
            tempo_range=(float(tr[0]), float(tr[1])) if len(tr) >= 2 else (70.0, 140.0),
            key_preferences=list(data.get("key_preferences", [])),
            signal_count=int(data.get("signal_count", 0)),
            confidence=float(data.get("confidence", 0.3)),
            exploration_budget=float(data.get("exploration_budget", 0.30)),
            session_history=[
                SessionSummary.from_dict(s)
                for s in data.get("session_history", [])
            ],
        )


# ---------------------------------------------------------------------------
# PreferenceTracker
# ---------------------------------------------------------------------------

class PreferenceTracker:
    """Track and update user preferences from implicit signals.

    Persistence: ``~/.muse/user-preferences.json``
    """

    def __init__(self, preferences_path: Optional[str] = None):
        self._path = preferences_path or os.path.expanduser(
            "~/.muse/user-preferences.json"
        )
        self.preferences = self._load()

    # ------------------------------------------------------------------
    # Core methods
    # ------------------------------------------------------------------

    def record_signal(self, signal: PreferenceSignal) -> None:
        """Apply a preference signal via EMA update.

        For each signal the update rule is::

            alpha = _ALPHA_MAP[signal_type] * signal.confidence
            target = 1.0  if direction == "increase"
                     0.0  if direction == "decrease"
                     skip if direction == "neutral"
            dim_new = dim_old * (1 - alpha) + target * alpha

        After the update, ``signal_count`` is incremented and
        ``confidence`` is recomputed.
        """
        prefs = self.preferences

        # Resolve dimension name
        dim_key = signal.dimension
        if dim_key not in _DIMENSION_NAMES:
            # Try domain → dimension fallback
            dim_key = _DOMAIN_TO_DIMENSION.get(signal.domain, "")
        if dim_key not in _DIMENSION_NAMES:
            logger.warning(
                "Unknown preference dimension %r (domain=%r) — skipping",
                signal.dimension,
                signal.domain,
            )
            return

        if signal.direction == "neutral":
            # Still count the signal but don't adjust the dimension
            prefs.signal_count += 1
            prefs.confidence = self.compute_confidence()
            prefs.last_updated = _now_iso()
            return

        alpha_base = _ALPHA_MAP.get(signal.signal_type, 0.10)
        alpha = alpha_base * max(0.0, min(1.0, signal.confidence))
        target = 1.0 if signal.direction == "increase" else 0.0

        current = getattr(prefs.dimensions, dim_key, 0.5)
        new_val = current * (1.0 - alpha) + target * alpha
        new_val = max(0.0, min(1.0, new_val))
        setattr(prefs.dimensions, dim_key, new_val)

        prefs.signal_count += 1
        prefs.confidence = self.compute_confidence()
        prefs.last_updated = _now_iso()

        logger.debug(
            "Preference %s: %.3f → %.3f (signal=%s, dir=%s, α=%.3f)",
            dim_key,
            current,
            new_val,
            signal.signal_type,
            signal.direction,
            alpha,
        )

    def record_generation_accept(
        self, genre: str, bpm: float, key: str
    ) -> None:
        """Convenience: record when user accepts a generation."""
        prefs = self.preferences

        # Boost genre affinity
        old = prefs.genre_affinities.get(genre, 0.5)
        prefs.genre_affinities[genre] = min(1.0, old + 0.05)

        # Widen tempo range toward the accepted BPM
        lo, hi = prefs.tempo_range
        if bpm < lo:
            lo = lo * 0.9 + bpm * 0.1
        elif bpm > hi:
            hi = hi * 0.9 + bpm * 0.1
        prefs.tempo_range = (round(lo, 1), round(hi, 1))

        # Track key preference (keep unique, max 6)
        if key and key not in prefs.key_preferences:
            prefs.key_preferences.append(key)
            if len(prefs.key_preferences) > 6:
                prefs.key_preferences = prefs.key_preferences[-6:]

        # Record as an accept signal on energy_level dimension
        self.record_signal(
            PreferenceSignal(
                timestamp=_now_iso(),
                signal_type="accept",
                domain="arrangement",
                dimension="energy_level",
                direction="neutral",
                confidence=0.8,
                context={"genre": genre, "bpm": bpm, "key": key},
            )
        )

    def record_generation_reject(self, genre: str) -> None:
        """Convenience: record when user rejects/regenerates."""
        prefs = self.preferences

        # Decrease genre affinity
        old = prefs.genre_affinities.get(genre, 0.5)
        prefs.genre_affinities[genre] = max(0.0, old - 0.03)

        self.record_signal(
            PreferenceSignal(
                timestamp=_now_iso(),
                signal_type="reject",
                domain="genre",
                dimension="experimental_tendency",
                direction="neutral",
                confidence=0.6,
                context={"genre": genre},
            )
        )

    def record_session_end(self, summary: SessionSummary) -> None:
        """Record end-of-session summary (last 50 kept)."""
        prefs = self.preferences
        prefs.session_history.append(summary)
        if len(prefs.session_history) > 50:
            prefs.session_history = prefs.session_history[-50:]

        # Decay exploration budget based on accept rate
        if summary.accept_rate > 0.7:
            prefs.exploration_budget = max(0.10, prefs.exploration_budget - 0.02)
        elif summary.accept_rate < 0.3:
            prefs.exploration_budget = min(0.30, prefs.exploration_budget + 0.02)

        prefs.last_updated = _now_iso()
        self.save()

    # ------------------------------------------------------------------
    # Query methods
    # ------------------------------------------------------------------

    def get_preferred_genre(self) -> Optional[str]:
        """Return highest-affinity genre, or ``None``."""
        affinities = self.preferences.genre_affinities
        if not affinities:
            return None
        return max(affinities, key=affinities.get)  # type: ignore[arg-type]

    def get_preferred_tempo_range(self) -> Tuple[float, float]:
        """Return ``(low_bpm, high_bpm)``."""
        return self.preferences.tempo_range

    def should_explore(self) -> bool:
        """Epsilon-greedy exploration decision.

        Returns ``True`` with probability equal to
        ``exploration_budget``.
        """
        return random.random() < self.preferences.exploration_budget

    def get_exploration_suggestion(self) -> Dict[str, Any]:
        """Suggest a dimension to explore (random axis, random direction).

        Returns:
            Dict with ``dimension``, ``direction``, ``current_value``.
        """
        dim_key = random.choice(_DIMENSION_NAMES)
        current = getattr(self.preferences.dimensions, dim_key, 0.5)
        # Push away from current value toward the opposite extreme
        direction = "increase" if current < 0.5 else "decrease"
        return {
            "dimension": dim_key,
            "direction": direction,
            "current_value": round(current, 3),
        }

    def compute_confidence(self) -> float:
        """``min(1.0, 0.3 + 0.15 * log2(signal_count + 1))``"""
        sc = self.preferences.signal_count
        return min(1.0, 0.3 + 0.15 * math.log2(sc + 1))

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save(self) -> None:
        """Write preferences to disk."""
        self.preferences.last_updated = _now_iso()
        dir_path = os.path.dirname(self._path)
        if dir_path:
            os.makedirs(dir_path, exist_ok=True)
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(self.preferences.to_dict(), f, indent=2)
        logger.debug("Preferences saved to %s", self._path)

    def _load(self) -> UserPreferences:
        """Load from disk or create default."""
        if os.path.isfile(self._path):
            try:
                with open(self._path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                logger.debug("Preferences loaded from %s", self._path)
                return UserPreferences.from_dict(data)
            except (json.JSONDecodeError, KeyError, TypeError) as exc:
                logger.warning(
                    "Corrupted preferences file %s — resetting: %s",
                    self._path,
                    exc,
                )
        return UserPreferences()

    def reset(self) -> None:
        """Reset to cold-start defaults."""
        self.preferences = UserPreferences()
        self.save()
        logger.info("Preferences reset to defaults")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    """Return current UTC time as ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()
