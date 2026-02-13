"""
Genre DNA — 10-Dimensional Genre Vectors

Maps every genre to a normalised 10-float vector that captures its
musical personality.  Supports weighted blending for genre-fusion
prompts and Euclidean distance for nearest-genre lookup.

Dimensions (all 0.0 – 1.0):
    1. rhythmic_density       – note events per beat
    2. swing                  – amount of swing / shuffle
    3. harmonic_complexity    – chord richness & chromaticism
    4. syncopation            – off-beat emphasis
    5. bass_drum_coupling     – how tightly bass locks to kick
    6. repetition_variation   – how much a loop varies over time
    7. register_spread        – pitch range used
    8. timbral_brightness     – spectral centroid proxy
    9. dynamic_range          – velocity range
   10. tension_resolution     – how much tension builds & releases

Integration:
    Wraps / extends the existing ``GenreIntelligence`` class from
    ``multimodal_gen.genre_intelligence`` — it does **not** replace it.
"""

from __future__ import annotations

import logging
import math
import statistics
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Try to import the existing genre_intelligence module for wrapping
try:
    from multimodal_gen.genre_intelligence import GenreIntelligence, GenreTemplate
    _HAS_GENRE_INTELLIGENCE = True
except ImportError:
    _HAS_GENRE_INTELLIGENCE = False
    GenreIntelligence = None  # type: ignore[misc, assignment]
    GenreTemplate = None      # type: ignore[misc, assignment]

# Lazy import — these types live in the same package
from .mpc_corpus import GenreHarmonicProfile, ParsedArpPattern


# ---------------------------------------------------------------------------
# Hand-tuned genre baselines (fallback when no corpus data available)
# Derived from musicological literature and MPC Beats inspection.
# ---------------------------------------------------------------------------

_BASELINE_VECTORS: Dict[str, list] = {
    # genre:  [density, swing, harm_complex, sync, bass_kick, rep_var, register, bright, dyn_range, tension]
    "hip_hop":   [0.55, 0.30, 0.35, 0.60, 0.85, 0.30, 0.45, 0.40, 0.50, 0.35],
    "trap":      [0.70, 0.15, 0.25, 0.75, 0.90, 0.25, 0.50, 0.55, 0.45, 0.30],
    "rnb":       [0.50, 0.40, 0.65, 0.50, 0.60, 0.40, 0.55, 0.50, 0.55, 0.55],
    "jazz":      [0.60, 0.55, 0.85, 0.65, 0.35, 0.70, 0.70, 0.55, 0.70, 0.70],
    "pop":       [0.55, 0.10, 0.35, 0.35, 0.65, 0.35, 0.50, 0.65, 0.40, 0.40],
    "house":     [0.75, 0.05, 0.30, 0.40, 0.80, 0.20, 0.40, 0.60, 0.30, 0.35],
    "edm":       [0.80, 0.05, 0.25, 0.45, 0.85, 0.30, 0.55, 0.75, 0.50, 0.50],
    "lofi":      [0.40, 0.45, 0.50, 0.35, 0.50, 0.25, 0.40, 0.30, 0.35, 0.30],
    "gospel":    [0.55, 0.35, 0.70, 0.45, 0.55, 0.50, 0.60, 0.50, 0.60, 0.65],
    "classical": [0.50, 0.05, 0.75, 0.25, 0.30, 0.65, 0.75, 0.45, 0.75, 0.70],
    "acoustic":  [0.45, 0.15, 0.40, 0.30, 0.40, 0.40, 0.50, 0.45, 0.50, 0.40],
    "reggaeton": [0.65, 0.10, 0.20, 0.70, 0.80, 0.15, 0.35, 0.55, 0.35, 0.25],
    "afrobeats": [0.70, 0.35, 0.35, 0.75, 0.70, 0.35, 0.45, 0.55, 0.45, 0.40],
    "funk":      [0.70, 0.45, 0.45, 0.80, 0.75, 0.45, 0.50, 0.60, 0.55, 0.45],
    "soul":      [0.50, 0.40, 0.55, 0.50, 0.55, 0.40, 0.55, 0.45, 0.55, 0.55],
    "drill":     [0.60, 0.10, 0.20, 0.70, 0.85, 0.20, 0.40, 0.50, 0.40, 0.30],
    "techno":    [0.80, 0.05, 0.20, 0.35, 0.90, 0.15, 0.35, 0.70, 0.25, 0.35],
    "unknown":   [0.50, 0.20, 0.40, 0.40, 0.50, 0.35, 0.50, 0.50, 0.45, 0.40],
}


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class GenreDNAVector:
    """10-dimensional genre fingerprint.  All values normalised 0.0 – 1.0."""
    rhythmic_density: float = 0.5
    swing: float = 0.2
    harmonic_complexity: float = 0.4
    syncopation: float = 0.4
    bass_drum_coupling: float = 0.5
    repetition_variation: float = 0.35
    register_spread: float = 0.5
    timbral_brightness: float = 0.5
    dynamic_range: float = 0.45
    tension_resolution: float = 0.4

    def to_list(self) -> List[float]:
        """Return the 10 dimensions as a flat list."""
        return [
            self.rhythmic_density,
            self.swing,
            self.harmonic_complexity,
            self.syncopation,
            self.bass_drum_coupling,
            self.repetition_variation,
            self.register_spread,
            self.timbral_brightness,
            self.dynamic_range,
            self.tension_resolution,
        ]

    @classmethod
    def from_list(cls, vals: List[float]) -> "GenreDNAVector":
        """Construct from a 10-element list (clamped to 0–1)."""
        clamped = [max(0.0, min(1.0, v)) for v in vals]
        while len(clamped) < 10:
            clamped.append(0.5)
        return cls(*clamped[:10])

    def __repr__(self) -> str:
        dims = ", ".join(f"{v:.2f}" for v in self.to_list())
        return f"GenreDNAVector([{dims}])"


@dataclass
class GenreFusionResult:
    """Result of blending multiple genre DNA vectors."""
    vector: GenreDNAVector
    sources: List[dict]      # [{"genre": str, "weight": float}, ...]
    description: str
    suggested_tempo: float   # BPM


# ---------------------------------------------------------------------------
# Module-level registry (populated lazily)
# ---------------------------------------------------------------------------

_registry: Dict[str, GenreDNAVector] = {}
_initialised: bool = False


def _ensure_registry() -> None:
    """Seed the registry with baseline vectors if not yet populated."""
    global _initialised
    if _initialised:
        return
    for genre, vals in _BASELINE_VECTORS.items():
        _registry[genre] = GenreDNAVector.from_list(vals)
    _initialised = True
    logger.debug("Genre DNA registry seeded with %d baselines", len(_registry))


# ---------------------------------------------------------------------------
# Beat-grid analysis helpers
# ---------------------------------------------------------------------------

def _compute_syncopation_from_analysis(analysis) -> float:
    """Estimate syncopation from arp analysis summary stats."""
    base = 0.0
    # Finer grids imply more off-beat notes
    if analysis.rhythmic_grid >= 32:
        base = 0.7
    elif analysis.rhythmic_grid >= 16:
        base = 0.5
    elif analysis.rhythmic_grid >= 8:
        base = 0.3
    else:
        base = 0.1
    # Swing adds off-beat emphasis
    swing_contribution = analysis.swing_amount * 0.3
    # High density with fine grid = more syncopation opportunity
    density_factor = min(1.0, analysis.density / 8.0) * 0.2
    return min(1.0, base + swing_contribution + density_factor)


def _compute_repetition_variation(analysis) -> float:
    """Estimate variation in arp pattern — higher = more varied."""
    # More unique intervals = more melodic variation
    unique_intervals = len(analysis.interval_distribution)
    interval_score = min(1.0, unique_intervals / 8.0)
    # Velocity variation indicates expressive playing
    vel_std = (
        analysis.velocity_stats.get("std", 0)
        if isinstance(analysis.velocity_stats, dict)
        else getattr(analysis.velocity_stats, "std", 0)
    )
    vel_score = min(1.0, vel_std / 30.0)
    # Wider pitch range = more melodic movement
    pitch_span = getattr(analysis, "pitch_range", {})
    if isinstance(pitch_span, dict):
        span_val = pitch_span.get("span", 12)
    else:
        span_val = getattr(pitch_span, "span", 12)
    span_score = min(1.0, span_val / 24.0)
    return interval_score * 0.4 + vel_score * 0.3 + span_score * 0.3


# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------

def compute_genre_dna_from_corpus(
    profiles: Dict[str, GenreHarmonicProfile],
    arp_patterns: List[ParsedArpPattern],
) -> Dict[str, GenreDNAVector]:
    """Derive genre DNA vectors from corpus analysis data.

    Merges corpus-derived signals with hand-tuned baselines — corpus
    data overrides baselines where available.

    Args:
        profiles: Per-genre harmonic profiles from ``build_genre_profiles``.
        arp_patterns: Parsed arp-pattern list from ``parse_all_arp_patterns``.

    Returns:
        Dict mapping genre name → :class:`GenreDNAVector`.
    """
    _ensure_registry()

    # Aggregate arp data per genre
    arp_by_genre: Dict[str, List[ParsedArpPattern]] = {}
    for ap in arp_patterns:
        arp_by_genre.setdefault(ap.genre, []).append(ap)

    all_genres = set(profiles.keys()) | set(arp_by_genre.keys()) | set(_registry.keys())

    result: Dict[str, GenreDNAVector] = {}
    for genre in all_genres:
        # Start from baseline (or default unknown)
        base = _registry.get(genre, _registry.get("unknown", GenreDNAVector())).to_list()

        profile = profiles.get(genre)
        arps = arp_by_genre.get(genre, [])

        # Override dimensions where we have real data
        if profile:
            # D3: harmonic_complexity — directly from profile
            base[2] = max(0.0, min(1.0, profile.avg_complexity))
            # D7: register_spread — normalise avg voicing spread (36 semitones = 1.0)
            base[6] = max(0.0, min(1.0, profile.avg_voicing_spread / 36.0))
            # D10: tension_resolution — map arc shape
            arc_map = {"rising": 0.6, "falling": 0.4, "arch": 0.7, "flat": 0.3}
            base[9] = arc_map.get(profile.typical_tension_arc, 0.4)

        if arps:
            # D1: rhythmic_density — avg notes per beat, normalise to 8 max
            densities = [a.analysis.density for a in arps]
            base[0] = max(0.0, min(1.0, statistics.mean(densities) / 8.0))

            # D2: swing — average swing from arps
            swings = [a.analysis.swing_amount for a in arps]
            base[1] = statistics.mean(swings)

            # D9: dynamic_range — velocity std / 40 (rough normalisation)
            vel_stds = [a.analysis.velocity_stats.get("std", 0.0) for a in arps]
            base[8] = max(0.0, min(1.0, statistics.mean(vel_stds) / 40.0))

            # D4: syncopation — derived from rhythmic grid, swing, density
            sync_vals = [_compute_syncopation_from_analysis(a.analysis) for a in arps]
            if sync_vals:
                base[3] = statistics.mean(sync_vals)

            # D6: repetition_variation — interval diversity, velocity std, pitch span
            rep_vals = [_compute_repetition_variation(a.analysis) for a in arps]
            if rep_vals:
                base[5] = statistics.mean(rep_vals)

        result[genre] = GenreDNAVector.from_list(base)

    # Merge into registry for subsequent lookups
    _registry.update(result)
    logger.info("Computed genre DNA for %d genres from corpus", len(result))
    return result


def get_genre_dna(genre: str) -> Optional[GenreDNAVector]:
    """Look up the DNA vector for *genre*.

    Falls back to baseline vectors when corpus data has not been
    loaded.

    Args:
        genre: Genre identifier (lowercase, underscore-separated).

    Returns:
        :class:`GenreDNAVector` or ``None`` if genre is unknown.
    """
    _ensure_registry()

    # Direct hit
    if genre in _registry:
        return _registry[genre]

    # Try normalised form
    normalised = genre.lower().replace(" ", "_").replace("-", "_")
    if normalised in _registry:
        return _registry[normalised]

    # Try enriching from GenreIntelligence if available
    if _HAS_GENRE_INTELLIGENCE:
        gi = GenreIntelligence()  # type: ignore[misc]
        template = gi.get_genre_template(normalised)
        if template is not None:
            vec = _vector_from_template(template)
            _registry[normalised] = vec
            return vec

    logger.debug("Genre '%s' not found in DNA registry", genre)
    return None


def _vector_from_template(template: object) -> GenreDNAVector:
    """Derive a rough DNA vector from a GenreIntelligence GenreTemplate.

    This bridges the existing genre_intelligence.py data into the
    DNA system without tight coupling.
    """
    # Access attributes safely
    swing = getattr(getattr(template, "tempo", None), "swing_amount", 0.2)
    brightness = getattr(getattr(template, "spectral_profile", None), "brightness", 0.5)
    vel_var = getattr(getattr(template, "drums", None), "velocity_variation", 0.12)
    hihat_density_str = getattr(getattr(template, "drums", None), "hihat_density", "8th")
    density_map = {"16th": 0.8, "8th": 0.6, "quarter": 0.4}
    density = density_map.get(hihat_density_str, 0.5)

    return GenreDNAVector(
        rhythmic_density=density,
        swing=swing,
        harmonic_complexity=0.4,
        syncopation=0.4,
        bass_drum_coupling=0.6,
        repetition_variation=0.35,
        register_spread=0.5,
        timbral_brightness=brightness,
        dynamic_range=min(1.0, vel_var * 5),
        tension_resolution=0.4,
    )


def blend_genres(sources: List[Tuple[str, float]]) -> GenreFusionResult:
    """Weighted interpolation of multiple genre DNA vectors.

    Args:
        sources: List of ``(genre_name, weight)`` tuples.  Weights are
                 normalised internally so they need not sum to 1.

    Returns:
        :class:`GenreFusionResult` with the blended vector and metadata.

    Raises:
        ValueError: If no valid genre vectors can be resolved.
    """
    _ensure_registry()

    resolved: List[Tuple[GenreDNAVector, str, float]] = []
    for genre, weight in sources:
        vec = get_genre_dna(genre)
        if vec is not None:
            resolved.append((vec, genre, weight))
        else:
            logger.warning("Skipping unknown genre '%s' in blend", genre)

    if not resolved:
        raise ValueError(
            f"No valid genre DNA vectors found for: {[s[0] for s in sources]}"
        )

    total_weight = sum(w for _, _, w in resolved)
    if total_weight <= 0:
        total_weight = 1.0

    # Weighted average per dimension
    blended = [0.0] * 10
    for vec, _, weight in resolved:
        normed_w = weight / total_weight
        for i, v in enumerate(vec.to_list()):
            blended[i] += v * normed_w

    result_vec = GenreDNAVector.from_list(blended)

    # Build source metadata
    source_dicts = [
        {"genre": g, "weight": round(w / total_weight, 3)}
        for _, g, w in resolved
    ]

    # Description
    parts = [f"{d['genre']} ({d['weight']:.0%})" for d in source_dicts]
    description = "Fusion of " + " + ".join(parts)

    # Suggested tempo — weighted average of baseline tempos
    _tempo_map: Dict[str, float] = {
        "hip_hop": 88, "trap": 145, "rnb": 72, "jazz": 120,
        "pop": 118, "house": 124, "edm": 130, "lofi": 80,
        "gospel": 90, "classical": 100, "acoustic": 105,
        "reggaeton": 95, "afrobeats": 108, "funk": 110,
        "soul": 85, "drill": 140, "techno": 132, "unknown": 110,
    }
    tempo = sum(
        _tempo_map.get(g, 110) * (w / total_weight) for _, g, w in resolved
    )

    # If GenreIntelligence is available, try to get more accurate tempos
    # Only override when ALL genres are found in GI templates
    if _HAS_GENRE_INTELLIGENCE:
        try:
            gi = GenreIntelligence()  # type: ignore[misc]
            weighted_tempos = []
            all_found = True
            for _, g, w in resolved:
                tmpl = gi.get_genre_template(g)
                if tmpl is not None:
                    weighted_tempos.append(
                        getattr(tmpl.tempo, "default_bpm", 120) * (w / total_weight)
                    )
                else:
                    all_found = False
            if weighted_tempos and all_found:
                tempo = sum(weighted_tempos)
        except Exception:
            pass  # fall back to hardcoded map

    return GenreFusionResult(
        vector=result_vec,
        sources=source_dicts,
        description=description,
        suggested_tempo=round(tempo, 1),
    )


def genre_distance(a: GenreDNAVector, b: GenreDNAVector) -> float:
    """Euclidean distance between two genre DNA vectors.

    The maximum possible distance is ``sqrt(10) ≈ 3.162`` (all
    dimensions differ by 1.0).

    Args:
        a: First vector.
        b: Second vector.

    Returns:
        Non-negative float distance.
    """
    return math.sqrt(
        sum((x - y) ** 2 for x, y in zip(a.to_list(), b.to_list()))
    )


# ---------------------------------------------------------------------------
# Named genre fusion presets
# ---------------------------------------------------------------------------

NAMED_FUSIONS: Dict[str, List[Tuple[str, float]]] = {
    "lo_fi_jazz_hop": [("jazz", 0.6), ("hip_hop", 0.4)],
    "electronic_soul": [("rnb", 0.5), ("edm", 0.5)],
    "trap_classical": [("classical", 0.4), ("trap", 0.6)],
    "gospel_trap": [("gospel", 0.5), ("trap", 0.5)],
    "ethio_jazz": [("jazz", 0.6), ("afrobeats", 0.4)],
    "funk_house": [("funk", 0.5), ("house", 0.5)],
    "neo_soul_lofi": [("soul", 0.5), ("lofi", 0.5)],
    "drill_classical": [("classical", 0.3), ("drill", 0.7)],
}


def get_named_fusion(name: str) -> Optional[GenreFusionResult]:
    """Look up a named fusion preset and return the blended result.

    Args:
        name: Key in :data:`NAMED_FUSIONS`.

    Returns:
        Blended :class:`GenreFusionResult`, or ``None`` if *name*
        is not a recognised preset.
    """
    preset = NAMED_FUSIONS.get(name)
    if preset is None:
        return None
    return blend_genres(preset)


def nearest_genre(
    vector: GenreDNAVector, exclude: Optional[List[str]] = None
) -> Tuple[str, float]:
    """Find the nearest genre in the registry to the given vector.

    Args:
        vector: Target DNA vector.
        exclude: Genre names to skip.

    Returns:
        ``(genre_name, distance)`` of the closest match.

    Raises:
        ValueError: If the registry is empty after exclusions.
    """
    _ensure_registry()
    exclude_set = set(exclude or [])
    best_name: Optional[str] = None
    best_dist = float("inf")
    for genre, dna in _registry.items():
        if genre in exclude_set:
            continue
        d = genre_distance(vector, dna)
        if d < best_dist:
            best_dist = d
            best_name = genre
    if best_name is None:
        raise ValueError("No genres available in registry after exclusions")
    return best_name, best_dist


def classify_blend_distance(sources: List[Tuple[str, float]]) -> str:
    """Classify the distance between blend sources.

    Computes the maximum pairwise distance among the source genres
    and returns a qualitative label.

    Returns:
        ``"close"`` (< 0.5), ``"medium"`` (0.5–1.0), ``"far"`` (> 1.0).
        Close: subtle.  Medium: interesting.  Far: extreme/experimental.
    """
    _ensure_registry()
    genre_names = [g for g, _ in sources]
    vectors = []
    for g in genre_names:
        dna = get_genre_dna(g)
        if dna is not None:
            vectors.append(dna)
    if len(vectors) < 2:
        return "close"
    max_dist = 0.0
    for i in range(len(vectors)):
        for j in range(i + 1, len(vectors)):
            d = genre_distance(vectors[i], vectors[j])
            if d > max_dist:
                max_dist = d
    if max_dist < 0.5:
        return "close"
    if max_dist <= 1.0:
        return "medium"
    return "far"


def list_genres() -> List[str]:
    """Return all genres in the DNA registry.

    Returns:
        Sorted list of genre name strings.
    """
    _ensure_registry()
    return sorted(_registry.keys())
