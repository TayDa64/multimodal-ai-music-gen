"""
Harmonic Brain - Voice Leading & Voicing Engine

This module provides intelligent voice leading and harmonic analysis
for the MUSE multimodal music generation system.

Core capabilities:
    - Voice leading between chords using 5 classical rules
    - Chord symbol parsing (triads through 13ths, slash chords)
    - Roman numeral analysis relative to a key
    - Tension computation (roughness + stability + surprise)
    - Corpus-based voicing lookup
    - Full progression voice-leading

The HarmonicBrain is designed to be injected into performer agents
(e.g. KeyboardistAgent) to upgrade their voicing intelligence when
the intelligence module is available, while agents remain functional
without it via their existing VoiceLeader fallback.

Usage:
    from multimodal_gen.intelligence.harmonic_brain import (
        HarmonicBrain, VoicingConstraints, VoicedChord,
    )

    brain = HarmonicBrain()
    constraints = VoicingConstraints(voicing_style="open")

    voiced = brain.voice_lead(
        previous_voicing=[60, 64, 67],
        chord_symbol="Dm7",
        key="C",
        constraints=constraints,
    )
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Set
import itertools
import json
import logging

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Pitch-class names (sharp convention)
_NOTE_NAMES = {
    "C": 0, "C#": 1, "Db": 1,
    "D": 2, "D#": 3, "Eb": 3,
    "E": 4, "Fb": 4,
    "F": 5, "F#": 6, "Gb": 6,
    "G": 7, "G#": 8, "Ab": 8,
    "A": 9, "A#": 10, "Bb": 10,
    "B": 11, "Cb": 11,
}

_PC_TO_NAME = ["C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]

# Chord quality → interval sets (pitch classes relative to root)
_CHORD_INTERVALS: Dict[str, List[int]] = {
    # Triads
    "":      [0, 4, 7],
    "m":     [0, 3, 7],
    "dim":   [0, 3, 6],
    "aug":   [0, 4, 8],
    "sus4":  [0, 5, 7],
    "sus2":  [0, 2, 7],
    # Seventh
    "7":     [0, 4, 7, 10],
    "maj7":  [0, 4, 7, 11],
    "m7":    [0, 3, 7, 10],
    "dim7":  [0, 3, 6, 9],
    "m7b5":  [0, 3, 6, 10],
    # Extended
    "9":     [0, 4, 7, 10, 14],
    "m9":    [0, 3, 7, 10, 14],
    "maj9":  [0, 4, 7, 11, 14],
    "11":    [0, 4, 7, 10, 14, 17],
    "13":    [0, 4, 7, 10, 14, 17, 21],
}

# Scale interval patterns (semitones from root)
_SCALE_INTERVALS: Dict[str, List[int]] = {
    "major":            [0, 2, 4, 5, 7, 9, 11],
    "minor":            [0, 2, 3, 5, 7, 8, 10],
    "natural_minor":    [0, 2, 3, 5, 7, 8, 10],
    "harmonic_minor":   [0, 2, 3, 5, 7, 8, 11],
    "melodic_minor":    [0, 2, 3, 5, 7, 9, 11],
    "dorian":           [0, 2, 3, 5, 7, 9, 10],
    "mixolydian":       [0, 2, 4, 5, 7, 9, 10],
    "phrygian":         [0, 1, 3, 5, 7, 8, 10],
    "lydian":           [0, 2, 4, 6, 7, 9, 11],
    "locrian":          [0, 1, 3, 5, 6, 8, 10],
    "pentatonic_major": [0, 2, 4, 7, 9],
    "pentatonic_minor": [0, 3, 5, 7, 10],
}

# Roman numeral labels for major-scale degrees
_MAJOR_NUMERALS = ["I", "bII", "II", "bIII", "III", "IV", "#IV/bV",
                   "V", "bVI", "VI", "bVII", "VII"]

# Dissonance roughness weights per interval class (0-11)
_INTERVAL_ROUGHNESS = [0.0, 1.0, 0.8, 0.3, 0.2, 0.1, 0.9,
                       0.05, 0.2, 0.3, 0.6, 0.7]


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class VoicingConstraints:
    """
    Parameters that control how HarmonicBrain voices chords.

    Attributes:
        min_pitch: Lowest allowable MIDI note (default C3 = 48).
        max_pitch: Highest allowable MIDI note (default C6 = 84).
        max_voice_movement: Maximum semitones a single voice may move.
        prefer_common_tones: Retain shared notes between consecutive chords.
        avoid_parallel_fifths: Penalise parallel perfect fifths / octaves.
        voicing_style: ``"close"`` keeps voices within an octave,
            ``"open"`` spreads them, ``"drop2"`` uses drop-2 layout.
    """
    min_pitch: int = 48
    max_pitch: int = 84
    max_voice_movement: int = 7
    prefer_common_tones: bool = True
    avoid_parallel_fifths: bool = True
    voicing_style: str = "close"


@dataclass
class VoicedChord:
    """
    A single chord realised as concrete MIDI pitches with metadata.

    Attributes:
        midi_notes: Ordered list of MIDI note numbers (low → high).
        chord_symbol: Original chord symbol (e.g. ``"Dm7"``).
        voice_leading_cost: Aggregate cost of the transition from
            the preceding voicing (lower ⇒ smoother).
        common_tones_retained: Number of pitches shared with
            the preceding chord (higher ⇒ smoother).
    """
    midi_notes: List[int] = field(default_factory=list)
    chord_symbol: str = ""
    voice_leading_cost: float = 0.0
    common_tones_retained: int = 0


# ---------------------------------------------------------------------------
# Chord symbol parser
# ---------------------------------------------------------------------------

def _note_name_to_pc(name: str) -> int:
    """Convert a note name (e.g. ``"Eb"``) to a pitch class 0-11."""
    pc = _NOTE_NAMES.get(name)
    if pc is not None:
        return pc
    # Try upper-casing first char
    canonical = name[0].upper() + name[1:] if len(name) > 1 else name.upper()
    pc = _NOTE_NAMES.get(canonical)
    if pc is not None:
        return pc
    raise ValueError(f"Unknown note name: {name!r}")


def parse_chord_symbol(chord_symbol: str) -> Tuple[int, List[int], Optional[int]]:
    """
    Parse a chord symbol into (root_pc, pitch_classes, bass_pc).

    Handles: C, Cm, C7, Cmaj7, Cm7, Cdim, Caug, Csus4, Csus2,
             C9, Cm9, Cmaj9, C11, C13, Cm7b5, Cdim7, and
             slash chords like ``C/E``.

    Args:
        chord_symbol: A chord symbol string.

    Returns:
        A tuple of (root pitch-class 0-11,
                     list of pitch-classes for the chord,
                     optional bass pitch-class for slash chords).

    Raises:
        ValueError: If the root note cannot be identified.
    """
    if not chord_symbol or not chord_symbol.strip():
        raise ValueError("Empty chord symbol")

    symbol = chord_symbol.strip()

    # --- slash chord ---
    bass_pc: Optional[int] = None
    if "/" in symbol:
        parts = symbol.split("/", 1)
        symbol = parts[0]
        bass_name = parts[1].strip()
        if bass_name:
            bass_pc = _note_name_to_pc(bass_name)

    # --- root note ---
    idx = 1
    if len(symbol) > 1 and symbol[1] in "#b":
        idx = 2
    root_name = symbol[:idx]
    quality_str = symbol[idx:]

    root_pc = _note_name_to_pc(root_name)

    # --- quality ---
    quality_key = _normalise_quality(quality_str)
    intervals = _CHORD_INTERVALS.get(quality_key, _CHORD_INTERVALS[""])
    pcs = [(root_pc + iv) % 12 for iv in intervals]

    return root_pc, pcs, bass_pc


def _normalise_quality(raw: str) -> str:
    """Map a quality suffix to a key in ``_CHORD_INTERVALS``."""
    q = raw.strip()

    # Direct hit
    if q in _CHORD_INTERVALS:
        return q

    low = q.lower()

    alias_map = {
        "": "",
        "maj": "",
        "major": "",
        "min": "m",
        "minor": "m",
        "-": "m",
        "+": "aug",
        "aug": "aug",
        "dim": "dim",
        "o": "dim",
        "ø": "m7b5",
        "sus": "sus4",
        "sus4": "sus4",
        "sus2": "sus2",
        "7": "7",
        "dom7": "7",
        "maj7": "maj7",
        "delta": "maj7",
        "Δ": "maj7",
        "Δ7": "maj7",
        "m7": "m7",
        "min7": "m7",
        "-7": "m7",
        "dim7": "dim7",
        "o7": "dim7",
        "m7b5": "m7b5",
        "ø7": "m7b5",
        "9": "9",
        "dom9": "9",
        "m9": "m9",
        "min9": "m9",
        "maj9": "maj9",
        "11": "11",
        "13": "13",
        # Extended aliases for corpus edge cases
        "aug7": "7",
        "add9": "9",
        "6": "",
        "m6": "m",
        "69": "9",
    }

    if low in alias_map:
        return alias_map[low]
    if q in alias_map:
        return alias_map[q]

    # Fallback – treat as major triad
    logger.debug("Unknown chord quality %r, falling back to major triad", raw)
    return ""


# ---------------------------------------------------------------------------
# Voicing corpus JSON persistence
# ---------------------------------------------------------------------------

_DEFAULT_CORPUS_PATH = str(
    Path(__file__).parent.parent.parent / "assets" / "voicing_corpus.json"
)


def save_voicing_corpus(
    templates: Dict[str, List[List[int]]],
    filepath: str = None,
) -> str:
    """Save voicing templates to JSON file for fast loading.

    Args:
        templates: Quality string → list of MIDI note arrays.
        filepath: Output path. Defaults to ``assets/voicing_corpus.json``.

    Returns:
        Path to saved file.
    """
    if filepath is None:
        filepath = _DEFAULT_CORPUS_PATH

    data = {
        "version": "1.0",
        "generated_from": "MPC Beats corpus",
        "template_count": sum(len(v) for v in templates.values()),
        "quality_count": len(templates),
        "templates": templates,
    }

    Path(filepath).parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w") as f:
        json.dump(data, f, indent=2)
    logger.info("Saved voicing corpus (%d qualities) to %s", len(templates), filepath)
    return filepath


def load_voicing_corpus(
    filepath: str = None,
) -> Optional[Dict[str, List[List[int]]]]:
    """Load voicing templates from JSON file.

    Returns ``None`` if the file doesn't exist so the caller can fall
    back to full corpus parsing.
    """
    if filepath is None:
        filepath = _DEFAULT_CORPUS_PATH

    fpath = Path(filepath)
    if not fpath.exists():
        return None

    try:
        with open(fpath, "r") as f:
            data = json.load(f)
        templates = data.get("templates", {})
        logger.info("Loaded voicing corpus (%d qualities) from %s", len(templates), filepath)
        return templates
    except (json.JSONDecodeError, IOError) as exc:
        logger.warning("Failed to load voicing corpus from %s: %s", filepath, exc)
        return None


# ---------------------------------------------------------------------------
# Corpus loader (cached via JSON)
# ---------------------------------------------------------------------------

def load_voicing_templates_from_corpus() -> Dict[str, List[List[int]]]:
    """Load voicing templates.  Uses cached JSON if available, falls back to corpus."""
    # Fast path: pre-built JSON
    cached = load_voicing_corpus()
    if cached is not None:
        return cached

    # Slow path: full MPC corpus parse
    try:
        from .mpc_corpus import load_corpus
        corpus = load_corpus()
        templates = corpus.voicing_templates

        # Persist for next time (non-critical)
        if templates:
            try:
                save_voicing_corpus(templates)
            except Exception:
                pass

        return templates
    except Exception as e:
        logger.warning("Could not load voicing templates from corpus: %s", e)
        return {}


# ---------------------------------------------------------------------------
# HarmonicBrain
# ---------------------------------------------------------------------------

class HarmonicBrain:
    """
    Voice-leading and harmonic analysis engine.

    Implements five classical voice-leading rules and provides
    utilities for tension analysis, roman-numeral labelling,
    and progression generation.

    Args:
        voicing_templates: Optional corpus of known-good voicings
            keyed by chord symbol (e.g. ``{"Cm7": [[48, 55, 58, 63], …]}``).
    """

    def __init__(
        self,
        voicing_templates: Optional[Dict[str, List[List[int]]]] = None,
        auto_load_corpus: bool = False,
    ) -> None:
        if voicing_templates is None and auto_load_corpus:
            voicing_templates = load_voicing_templates_from_corpus()
        self._templates: Dict[str, List[List[int]]] = voicing_templates or {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def voice_lead(
        self,
        previous_voicing: Optional[List[int]],
        chord_symbol: str,
        key: str,
        constraints: Optional[VoicingConstraints] = None,
    ) -> List[int]:
        """
        Voice-lead *chord_symbol* from *previous_voicing*.

        Five rules are applied:
            1. **Common-tone retention** – pitches shared between the
               previous voicing and the target chord stay in place.
            2. **Stepwise motion** – non-common voices prefer movement
               of ≤ 2 semitones.
            3. **Contrary motion to bass** – when the bass moves up,
               at least one upper voice moves down, and vice-versa.
            4. **Tendency-tone resolution** – chord 7ths resolve
               downward, leading tones resolve upward.
            5. **Spacing constraints** – ≤ octave between adjacent
               upper voices; no voice crossing.

        Args:
            previous_voicing: MIDI notes of the preceding chord,
                or ``None`` for the first chord (root-position default).
            chord_symbol: Target chord symbol (e.g. ``"Dm7"``).
            key: Current key (e.g. ``"C"``).
            constraints: Optional voicing constraints.

        Returns:
            A list of MIDI note numbers representing the best voicing.
        """
        if constraints is None:
            constraints = VoicingConstraints()

        root_pc, target_pcs, bass_pc = parse_chord_symbol(chord_symbol)

        # ---- first chord: seed with root-position voicing ----
        if previous_voicing is None or len(previous_voicing) == 0:
            voicing = self._seed_voicing(root_pc, target_pcs, bass_pc, constraints)
            return voicing

        # ---- generate candidates and score ----
        candidates = self._generate_candidates(
            previous_voicing, root_pc, target_pcs, bass_pc, constraints
        )

        if not candidates:
            # Fallback: simple closest transposition
            return self._seed_voicing(root_pc, target_pcs, bass_pc, constraints)

        best = min(candidates, key=lambda c: self._score_candidate(
            previous_voicing, c, root_pc, target_pcs, key, constraints
        ))
        return best

    def compute_tension(
        self,
        chord_notes: List[int],
        key: str,
        previous_chord: Optional[List[int]] = None,
    ) -> float:
        """
        Compute a 0–1 tension value for *chord_notes* in *key*.

        The tension score combines three factors:
            - **Roughness** – intervallic dissonance within the chord.
            - **Key stability** – how many chord tones fall outside
              the diatonic scale of *key*.
            - **Contextual surprise** – pitch-class distance from the
              previous chord (harmonic distance).

        Args:
            chord_notes: MIDI note numbers of the chord.
            key: Current key name (e.g. ``"Eb"``).
            previous_chord: Optional previous chord MIDI notes.

        Returns:
            A float in ``[0.0, 1.0]`` where 1.0 is maximum tension.
        """
        if not chord_notes:
            return 0.0

        # --- roughness ---
        roughness = self._interval_roughness(chord_notes)

        # --- key stability ---
        key_pc = _note_name_to_pc(key)
        scale_pcs = set((key_pc + s) % 12 for s in _SCALE_INTERVALS["major"])
        chord_pcs = set(n % 12 for n in chord_notes)
        out_of_key = len(chord_pcs - scale_pcs)
        stability_penalty = out_of_key / max(len(chord_pcs), 1)

        # --- contextual surprise ---
        surprise = 0.0
        if previous_chord:
            prev_pcs = set(n % 12 for n in previous_chord)
            common = len(chord_pcs & prev_pcs)
            surprise = 1.0 - (common / max(len(chord_pcs), 1))

        raw = 0.4 * roughness + 0.35 * stability_penalty + 0.25 * surprise
        return max(0.0, min(1.0, raw))

    def analyze_roman_numeral(self, chord_symbol: str, key: str) -> str:
        """
        Return the roman-numeral label of *chord_symbol* in *key*.

        Examples::

            >>> brain.analyze_roman_numeral("Am", "C")
            'vi'
            >>> brain.analyze_roman_numeral("G7", "C")
            'V7'

        Args:
            chord_symbol: Chord symbol (e.g. ``"Dm7"``).
            key: Key name (e.g. ``"C"``).

        Returns:
            Roman-numeral string (e.g. ``"ii7"``, ``"IV"``, ``"V7"``).
        """
        root_pc, pcs, _ = parse_chord_symbol(chord_symbol)
        key_pc = _note_name_to_pc(key)
        degree = (root_pc - key_pc) % 12
        numeral = _MAJOR_NUMERALS[degree]

        # Determine quality suffix
        quality_str = chord_symbol.lstrip("ABCDEFG#b")
        if "/" in quality_str:
            quality_str = quality_str.split("/")[0]
        quality_key = _normalise_quality(quality_str)

        is_minor = quality_key in ("m", "m7", "m9", "dim", "dim7", "m7b5")
        if is_minor:
            numeral = numeral.lower()

        # Append extension indicator
        ext = ""
        if "7" in quality_key or quality_key in ("maj7",):
            ext = "7"
        elif "9" in quality_key:
            ext = "9"
        elif "11" in quality_key:
            ext = "11"
        elif "13" in quality_key:
            ext = "13"

        if quality_key == "dim":
            ext = "°"
        elif quality_key == "dim7":
            ext = "°7"
        elif quality_key == "aug":
            ext = "+"
        elif quality_key == "m7b5":
            ext = "ø7"
        elif quality_key == "maj7":
            ext = "Δ7"

        return f"{numeral}{ext}"

    def generate_progression(
        self,
        key: str,
        scale: str = "major",
        genre_dna: Optional[Any] = None,
        length: int = 4,
    ) -> List[str]:
        """
        Generate a chord-symbol progression in *key*.

        A simple rule-based generator producing diatonic progressions
        with optional genre colouring via *genre_dna*.

        Args:
            key: Root key (e.g. ``"Eb"``).
            scale: Scale type (``"major"``, ``"minor"``, etc.).
            genre_dna: Optional genre DNA dictionary for style hints.
            length: Number of chords to generate.

        Returns:
            A list of chord symbol strings.
        """
        key_pc = _note_name_to_pc(key)
        intervals = _SCALE_INTERVALS.get(scale, _SCALE_INTERVALS["major"])

        # Build diatonic triads
        diatonic_roots = [(key_pc + iv) % 12 for iv in intervals]
        # quality per degree (major scale pattern)
        if scale in ("minor", "natural_minor"):
            qualities = ["m", "", "", "m", "m", "", ""]
        else:
            qualities = ["", "m", "m", "", "", "m", "dim"]

        templates = self._progression_templates(scale, genre_dna)
        template = templates[0] if templates else [0, 3, 4, 0]
        # Ensure requested length
        while len(template) < length:
            template = template + template
        template = template[:length]

        chords: List[str] = []
        for deg in template:
            deg_idx = deg % len(diatonic_roots)
            root = diatonic_roots[deg_idx]
            quality = qualities[deg_idx] if deg_idx < len(qualities) else ""
            name = _PC_TO_NAME[root]
            chords.append(f"{name}{quality}")

        return chords

    def voice_lead_progression(
        self,
        chord_symbols: List[str],
        key: str,
        constraints: Optional[VoicingConstraints] = None,
    ) -> List[VoicedChord]:
        """
        Voice-lead an entire chord progression.

        Iterates through *chord_symbols*, calling :meth:`voice_lead`
        sequentially so each chord is smoothly connected to its
        predecessor.

        Args:
            chord_symbols: List of chord symbols.
            key: Key context for the progression.
            constraints: Optional voicing constraints.

        Returns:
            A list of :class:`VoicedChord` objects.
        """
        if not chord_symbols:
            return []

        results: List[VoicedChord] = []
        prev_voicing: Optional[List[int]] = None

        for symbol in chord_symbols:
            notes = self.voice_lead(prev_voicing, symbol, key, constraints)
            cost = self._total_movement(prev_voicing, notes) if prev_voicing else 0.0
            common = self._count_common_tones(prev_voicing, notes) if prev_voicing else 0

            results.append(VoicedChord(
                midi_notes=notes,
                chord_symbol=symbol,
                voice_leading_cost=cost,
                common_tones_retained=common,
            ))
            prev_voicing = notes

        return results

    def get_voicing_from_corpus(
        self, chord_symbol: str
    ) -> Optional[List[int]]:
        """
        Look up a pre-existing voicing in the corpus templates.

        Args:
            chord_symbol: Chord symbol to look up.

        Returns:
            A list of MIDI notes if found, otherwise ``None``.
        """
        entries = self._templates.get(chord_symbol)
        if entries:
            return list(entries[0])  # Return a copy of the first template
        return None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _seed_voicing(
        self,
        root_pc: int,
        target_pcs: List[int],
        bass_pc: Optional[int],
        constraints: VoicingConstraints,
    ) -> List[int]:
        """Create an initial root-position voicing within constraints."""
        mid = (constraints.min_pitch + constraints.max_pitch) // 2
        # Place root near center of range
        root_midi = mid - (mid % 12) + root_pc
        if root_midi < constraints.min_pitch:
            root_midi += 12
        if root_midi > constraints.max_pitch:
            root_midi -= 12

        notes: List[int] = []
        for pc in target_pcs:
            note = root_midi - (root_midi % 12) + pc
            # Ensure note is above root (except bass override)
            while note < root_midi and pc != root_pc:
                note += 12
            # Clamp to range
            while note < constraints.min_pitch:
                note += 12
            while note > constraints.max_pitch:
                note -= 12
            notes.append(note)

        # Handle slash chord bass
        if bass_pc is not None:
            bass_note = constraints.min_pitch - (constraints.min_pitch % 12) + bass_pc
            while bass_note < constraints.min_pitch:
                bass_note += 12
            # Make sure bass is lowest
            if notes and bass_note >= min(notes):
                bass_note = min(notes) - 12 + bass_pc - (min(notes) % 12)
                if bass_note < 36:  # absolute floor
                    bass_note += 12
            notes = [bass_note] + [n for n in notes if n % 12 != bass_pc]

        notes = sorted(set(notes))
        return notes

    def _generate_candidates(
        self,
        prev: List[int],
        root_pc: int,
        target_pcs: List[int],
        bass_pc: Optional[int],
        constraints: VoicingConstraints,
    ) -> List[List[int]]:
        """Generate candidate voicings for scoring."""
        candidates: List[List[int]] = []
        num_voices = len(prev)

        # Strategy 1: closest mapping – assign each target PC to the
        # nearest previous voice.
        for octave_shift in range(-1, 2):
            candidate: List[int] = []
            used_prev: Set[int] = set()

            # Build pool of concrete pitches for target PCs
            pool: List[int] = []
            for pc in target_pcs:
                for oct in range(constraints.min_pitch // 12, constraints.max_pitch // 12 + 2):
                    midi = oct * 12 + pc
                    if constraints.min_pitch <= midi <= constraints.max_pitch:
                        pool.append(midi)

            if not pool:
                continue

            # For each previous voice find the closest available target pitch
            assigned: List[int] = []
            pool_used: Set[int] = set()
            for pv in sorted(prev):
                shifted = pv + octave_shift
                best_note = min(pool, key=lambda n: abs(n - shifted))
                assigned.append(best_note)

            # Deduplicate while keeping voice count
            seen: Set[int] = set()
            deduped: List[int] = []
            for n in assigned:
                while n in seen and n + 12 <= constraints.max_pitch:
                    n += 12
                if n not in seen:
                    deduped.append(n)
                    seen.add(n)

            if deduped:
                candidates.append(sorted(deduped))

        # Strategy 2: common-tone anchored
        if constraints.prefer_common_tones:
            prev_pcs = {n % 12: n for n in prev}
            anchored: List[int] = []
            for pc in target_pcs:
                if pc in prev_pcs:
                    anchored.append(prev_pcs[pc])  # Keep in place
                else:
                    # Find closest previous voice
                    best = min(prev, key=lambda p: min(
                        abs(p - (p - p % 12 + pc)),
                        abs(p - (p - p % 12 + pc + 12)),
                        abs(p - (p - p % 12 + pc - 12)),
                    ))
                    note = best - (best % 12) + pc
                    if abs(note - best) > 6:
                        note = note + 12 if note < best else note - 12
                    # Clamp
                    while note < constraints.min_pitch:
                        note += 12
                    while note > constraints.max_pitch:
                        note -= 12
                    anchored.append(note)

            anchored = sorted(set(anchored))
            if anchored:
                candidates.append(anchored)

        # Strategy 3: seed voicing (fresh, for diversity)
        seed = self._seed_voicing(root_pc, target_pcs, bass_pc, constraints)
        if seed:
            candidates.append(seed)

        # Strategy 4: corpus lookup
        corpus = self.get_voicing_from_corpus(
            f"{_PC_TO_NAME[root_pc]}{_quality_label_for_pcs(root_pc, target_pcs)}"
        )
        if corpus:
            candidates.append(corpus)

        return candidates

    def _score_candidate(
        self,
        prev: List[int],
        candidate: List[int],
        root_pc: int,
        target_pcs: List[int],
        key: str,
        constraints: VoicingConstraints,
    ) -> float:
        """
        Score a candidate voicing (lower is better).

        Applies the five voice-leading rules as penalty terms.
        """
        score = 0.0

        # Rule 1 – Common-tone retention (reward)
        common = self._count_common_tones(prev, candidate)
        if constraints.prefer_common_tones:
            score -= common * 3.0

        # Rule 2 – Stepwise motion (penalise large jumps)
        movements = self._voice_movements(prev, candidate)
        for mv in movements:
            if mv <= 2:
                score += mv * 0.5      # Small step – cheap
            elif mv <= constraints.max_voice_movement:
                score += mv * 1.5      # Moderate – acceptable
            else:
                score += mv * 4.0      # Too large – heavy penalty

        # Rule 3 – Contrary motion to bass
        if len(prev) >= 2 and len(candidate) >= 2:
            bass_motion = candidate[0] - prev[0]
            upper_motions = [c - p for p, c in zip(prev[1:], candidate[1:])]
            if bass_motion != 0 and upper_motions:
                contrary = any(
                    (m * bass_motion) < 0 for m in upper_motions if m != 0
                )
                if not contrary:
                    score += 2.0  # Penalty for all-parallel motion

        # Rule 4 – Tendency tone resolution
        score += self._tendency_penalty(prev, candidate, key)

        # Rule 5 – Spacing constraints
        score += self._spacing_penalty(candidate, constraints)

        # Parallel-fifths penalty
        if constraints.avoid_parallel_fifths:
            score += self._parallel_fifths_penalty(prev, candidate)

        return score

    def _voice_movements(
        self, prev: List[int], curr: List[int]
    ) -> List[int]:
        """Calculate absolute semitone movements between matched voices."""
        movements: List[int] = []
        # Match by nearest neighbour
        used: Set[int] = set()
        for p in sorted(prev):
            available = [c for i, c in enumerate(sorted(curr)) if i not in used]
            if not available:
                break
            best_idx = min(
                range(len(sorted(curr))),
                key=lambda i: abs(sorted(curr)[i] - p) if i not in used else 9999,
            )
            movements.append(abs(sorted(curr)[best_idx] - p))
            used.add(best_idx)
        return movements

    def _count_common_tones(
        self,
        a: Optional[List[int]],
        b: Optional[List[int]],
    ) -> int:
        """Count MIDI pitches common to both chords."""
        if not a or not b:
            return 0
        return len(set(a) & set(b))

    def _total_movement(
        self,
        prev: Optional[List[int]],
        curr: List[int],
    ) -> float:
        """Sum of absolute semitone movements."""
        if not prev:
            return 0.0
        return float(sum(self._voice_movements(prev, curr)))

    def _tendency_penalty(
        self, prev: List[int], curr: List[int], key: str
    ) -> float:
        """Penalise unresolved tendency tones."""
        penalty = 0.0
        key_pc = _note_name_to_pc(key)

        for p in prev:
            pc = p % 12
            rel = (pc - key_pc) % 12

            # Leading tone (major 7th of key) should resolve up
            if rel == 11:
                resolved_up = any(c == p + 1 for c in curr)
                common = p in curr
                if not resolved_up and not common:
                    penalty += 1.5

            # Chord 7ths tend to resolve down
            if rel == 10:
                resolved_down = any(c == p - 1 or c == p - 2 for c in curr)
                common = p in curr
                if not resolved_down and not common:
                    penalty += 1.0

        return penalty

    def _spacing_penalty(
        self, candidate: List[int], constraints: VoicingConstraints
    ) -> float:
        """Penalise voice spacing violations."""
        penalty = 0.0
        s = sorted(candidate)

        for i in range(1, len(s)):
            gap = s[i] - s[i - 1]
            # Adjacent upper voices > octave apart
            if i >= 1 and gap > 12:
                penalty += (gap - 12) * 0.5

        # Voice crossing
        for i in range(len(s) - 1):
            if s[i] > s[i + 1]:
                penalty += 3.0

        # Out of range
        for n in s:
            if n < constraints.min_pitch:
                penalty += (constraints.min_pitch - n) * 0.8
            if n > constraints.max_pitch:
                penalty += (n - constraints.max_pitch) * 0.8

        return penalty

    def _parallel_fifths_penalty(
        self, prev: List[int], curr: List[int]
    ) -> float:
        """Penalise parallel perfect fifths/octaves between voice pairs."""
        penalty = 0.0
        sp = sorted(prev)
        sc = sorted(curr)
        n = min(len(sp), len(sc))

        for i in range(n):
            for j in range(i + 1, n):
                prev_interval = abs(sp[j] - sp[i]) % 12
                curr_interval = abs(sc[j] - sc[i]) % 12
                # Both are P5 (7) or P8 (0) and both voices move
                if prev_interval == curr_interval and prev_interval in (0, 7):
                    if sp[i] != sc[i] and sp[j] != sc[j]:
                        penalty += 2.0

        return penalty

    def _interval_roughness(self, notes: List[int]) -> float:
        """Compute average interval-class roughness for a chord."""
        if len(notes) < 2:
            return 0.0
        total = 0.0
        count = 0
        for i in range(len(notes)):
            for j in range(i + 1, len(notes)):
                ic = abs(notes[j] - notes[i]) % 12
                total += _INTERVAL_ROUGHNESS[ic]
                count += 1
        return total / count if count else 0.0

    def _progression_templates(
        self, scale: str, genre_dna: Optional[Any] = None
    ) -> List[List[int]]:
        """Return degree-index templates for common progressions."""
        if scale in ("minor", "natural_minor"):
            templates = [
                [0, 5, 6, 4],   # i-VI-VII-v
                [0, 3, 5, 6],   # i-iv-VI-VII
                [0, 6, 5, 3],   # i-VII-VI-iv
                [0, 2, 5, 6],   # i-III-VI-VII
            ]
        else:
            templates = [
                [0, 3, 4, 0],   # I-IV-V-I
                [0, 5, 3, 4],   # I-vi-IV-V
                [0, 4, 5, 3],   # I-V-vi-IV
                [0, 3, 1, 4],   # I-IV-ii-V
            ]

        # If genre_dna hints at jazz, prefer richer templates
        if genre_dna and isinstance(genre_dna, dict):
            jazz = genre_dna.get("jazz", 0.0)
            if jazz > 0.5:
                templates.insert(0, [1, 4, 0, 3])  # ii-V-I-IV

        return templates


# ---------------------------------------------------------------------------
# Module-level utility
# ---------------------------------------------------------------------------

def _quality_label_for_pcs(root_pc: int, pcs: List[int]) -> str:
    """Derive a short quality label from pitch classes relative to root."""
    rel = sorted(set((pc - root_pc) % 12 for pc in pcs))

    lookup = {
        (0, 3, 7): "m",
        (0, 4, 7): "",
        (0, 3, 6): "dim",
        (0, 4, 8): "aug",
        (0, 2, 7): "sus2",
        (0, 5, 7): "sus4",
        (0, 3, 7, 10): "m7",
        (0, 4, 7, 10): "7",
        (0, 4, 7, 11): "maj7",
        (0, 3, 6, 9): "dim7",
        (0, 3, 6, 10): "m7b5",
    }
    return lookup.get(tuple(rel), "")
