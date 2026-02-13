"""
MPC Beats Corpus Parser & Harmonic Analyzer

Parses MPC Beats .progression (JSON) and .mid (arp pattern) files from the
local MPC Beats installation, enriches them with harmonic analysis, and
builds per-genre harmonic profiles for downstream use by the intelligence
layer.

Environment:
    MPC_BEATS_PATH  – override for the MPC Beats installation root.
                      Default: ``c:\\dev\\MPC Beats``

Requires:
    mido  (already in requirements.txt)
"""

from __future__ import annotations

import json
import logging
import math
import os
import re
import statistics
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import mido

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_DEFAULT_MPC_PATH = r"c:\dev\MPC Beats"

# Chromatic pitch-class names (sharps only for canonical form)
_PC_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

# Enharmonic normalisation  –  map flat spellings → sharp equivalents
_ENHARMONIC: Dict[str, str] = {
    "Db": "C#", "Eb": "D#", "Fb": "E", "Gb": "F#",
    "Ab": "G#", "Bb": "A#", "Cb": "B",
}

# Interval semitone counts from root for major/minor scale construction
_MAJOR_INTERVALS = [0, 2, 4, 5, 7, 9, 11]
_MINOR_INTERVALS = [0, 2, 3, 5, 7, 8, 10]

# Roman numeral labels (major/minor scale degree)
_ROMAN_MAJOR = ["I", "ii", "iii", "IV", "V", "vi", "vii°"]
_ROMAN_MINOR = ["i", "ii°", "III", "iv", "v", "VI", "VII"]

# Dissonance/roughness weights by interval class (0-6 semitones)
# Values inspired by Plomp-Levelt roughness curves
_ROUGHNESS: Dict[int, float] = {
    0: 0.0, 1: 1.0, 2: 0.8, 3: 0.4, 4: 0.2, 5: 0.1, 6: 0.55,
}

# Genre keywords extracted from MPC Beats file naming conventions
_GENRE_KEYWORDS: Dict[str, List[str]] = {
    "rnb":        ["RnB", "R&B", "Neo Soul", "Soul", "Ballad", "Rhodes"],
    "house":      ["House", "Deep House", "Classic House", "Tech House"],
    "jazz":       ["Jazz", "Jazzy", "Bossa", "Swing"],
    "pop":        ["Pop", "Billboard", "Radio"],
    "hip_hop":    ["HipHop", "Hip Hop", "Trap", "Boom Bap", "BoomBap"],
    "gospel":     ["Praise", "Godly", "Church", "Worship"],
    "acoustic":   ["Guitar", "Acoustic"],
    "classical":  ["Canon", "Classic", "Classical"],
    "electronic": ["Dance", "EDM", "Synth", "Trance", "Electro", "Techno"],
    "ambient":    ["Chill", "Chill Out", "Ambient", "Downtempo", "Lounge"],
    "reggae":     ["Dub", "Reggae", "Ska", "Dancehall"],
    "funk":       ["Funk", "Funky", "Disco"],
    "latin":      ["Latin", "Salsa", "Bossa Nova", "Samba", "Rumba"],
    "world":      ["African", "Afrobeat", "Ethiopian", "World"],
    "rock":       ["Rock", "Metal", "Punk", "Grunge", "Alternative"],
    "neo_soul":   ["Neo Soul", "NeoSoul"],
    "lo_fi":      ["Lo-Fi", "LoFi", "Lo Fi"],
}


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class RawChord:
    """A single chord from an MPC Beats .progression file."""
    name: str
    role: str
    notes: List[int]


@dataclass
class RawProgression:
    """Parsed (but unenriched) MPC Beats progression."""
    name: str
    root_note: str
    scale: str
    recording_octave: int
    chords: List[RawChord]


@dataclass
class KeyCenter:
    """Detected key/mode with confidence score."""
    root: str
    mode: str          # "major" | "minor"
    confidence: float  # 0.0 – 1.0


@dataclass
class HarmonicAnalysis:
    """Full harmonic analysis of a chord progression."""
    roman_numerals: List[str]
    key_center: KeyCenter
    voice_leading_distances: List[float]
    common_tone_retention: List[int]
    tension_values: List[float]
    genre_associations: List[str]
    complexity: float       # 0.0 – 1.0
    chromaticism: float     # 0.0 – 1.0
    average_voicing_spread: float  # semitones


@dataclass
class EnrichedProgression:
    """A progression enriched with harmonic analysis."""
    raw: RawProgression
    file_path: str
    genre: str
    display_name: str
    analysis: HarmonicAnalysis


@dataclass
class ArpAnalysis:
    """Quantitative analysis of an MPC arp MIDI pattern."""
    duration_ticks: int
    duration_beats: float
    note_count: int
    pitch_range: Dict[str, int]      # {"min": int, "max": int, "span": int}
    density: float                    # notes per beat
    velocity_stats: Dict[str, float]  # {"min", "max", "mean", "std"}
    rhythmic_grid: int                # finest grid division in ticks
    swing_amount: float               # 0.0 – 1.0 estimated swing
    interval_distribution: Dict[int, int]  # semitone → count
    polyphony: str                    # "mono" | "poly"
    max_polyphony: int


@dataclass
class ParsedArpPattern:
    """A parsed MPC Beats arp .mid pattern."""
    file_name: str
    file_path: str
    category: str
    sub_category: str
    genre: str
    notes: list  # list of dicts with pitch, start, dur, vel
    analysis: ArpAnalysis


@dataclass
class GenreHarmonicProfile:
    """Aggregated harmonic statistics for a genre."""
    genre: str
    avg_complexity: float
    avg_chromaticism: float
    avg_voicing_spread: float
    avg_voice_leading_distance: float
    common_chord_qualities: List[str]
    typical_tension_arc: str   # "rising" | "falling" | "arch" | "flat"
    progression_count: int


@dataclass
class CorpusData:
    """Top-level container returned by ``load_corpus``."""
    progressions: List[RawProgression]
    enriched: List[EnrichedProgression]
    arp_patterns: List[ParsedArpPattern]
    genre_profiles: Dict[str, GenreHarmonicProfile]
    voicing_templates: Dict[str, List[List[int]]]


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

def get_mpc_beats_path() -> Path:
    """Return the root MPC Beats installation path.

    Reads ``MPC_BEATS_PATH`` from the environment, falling back to
    the default Windows location.
    """
    raw = os.environ.get("MPC_BEATS_PATH", _DEFAULT_MPC_PATH)
    p = Path(raw)
    if not p.exists():
        logger.warning("MPC Beats path does not exist: %s", p)
    return p


# ---------------------------------------------------------------------------
# Pitch / theory helpers (self-contained, no external music-theory lib)
# ---------------------------------------------------------------------------

def _normalise_root(name: str) -> str:
    """Normalise a note name to sharp spelling (e.g. 'Bb' → 'A#')."""
    if len(name) == 2 and name[1] == "b":
        return _ENHARMONIC.get(name, name)
    return name


def _root_pc(name: str) -> int:
    """Return pitch class (0-11) for a note name."""
    n = _normalise_root(name)
    try:
        return _PC_NAMES.index(n)
    except ValueError:
        logger.debug("Unknown note name '%s', defaulting to C", name)
        return 0


def _build_scale(root_pc: int, mode: str) -> List[int]:
    """Return list of 7 pitch classes for a scale rooted at *root_pc*."""
    intervals = _MAJOR_INTERVALS if mode == "major" else _MINOR_INTERVALS
    return [(root_pc + i) % 12 for i in intervals]


def _chord_name_root(chord_name: str) -> str:
    """Extract root note name from an MPC chord label like 'F#m7b5' or 'G/B'."""
    slash = chord_name.find("/")
    base = chord_name if slash == -1 else chord_name[:slash]
    if not base:
        return "C"
    # root is first letter + optional accidental
    root = base[0]
    if len(base) > 1 and base[1] in ("#", "b"):
        root += base[1]
    return root


def _chord_quality(chord_name: str) -> str:
    """Extract quality suffix (e.g. 'maj7', 'm', 'aug7', 'dim') from name."""
    slash = chord_name.find("/")
    base = chord_name if slash == -1 else chord_name[:slash]
    # strip root
    root = _chord_name_root(chord_name)
    quality = base[len(root):]
    return quality if quality else "maj"


def _detect_key(chords: List[RawChord], declared_root: str) -> KeyCenter:
    """Heuristic key detection from chords and the declared root note.

    Tries major and minor scales for the declared root and picks the
    one that covers the most pitch classes present in the progression.
    """
    if not chords:
        return KeyCenter(root=declared_root, mode="major", confidence=0.0)

    root_pc = _root_pc(declared_root)
    all_pcs: set = set()
    for c in chords:
        for n in c.notes:
            all_pcs.add(n % 12)

    best_mode = "major"
    best_coverage = 0.0
    for mode in ("major", "minor"):
        scale = set(_build_scale(root_pc, mode))
        if not all_pcs:
            coverage = 0.0
        else:
            coverage = len(all_pcs & scale) / len(all_pcs)
        if coverage > best_coverage:
            best_coverage = coverage
            best_mode = mode

    # If declared root coverage is low, try all 12 roots
    if best_coverage < 0.6:
        for try_pc in range(12):
            for mode in ("major", "minor"):
                scale = set(_build_scale(try_pc, mode))
                coverage = len(all_pcs & scale) / len(all_pcs) if all_pcs else 0.0
                if coverage > best_coverage:
                    best_coverage = coverage
                    best_mode = mode
                    root_pc = try_pc

    root_name = _PC_NAMES[root_pc]
    return KeyCenter(root=root_name, mode=best_mode, confidence=round(best_coverage, 3))


def _roman_numeral(chord: RawChord, key: KeyCenter) -> str:
    """Derive a roman numeral label for *chord* relative to *key*.

    Uses pitch-class of the chord root compared against scale degrees.
    Falls back to chromatic notation (e.g. '#IV') when no exact match.
    """
    chord_root_pc = _root_pc(_chord_name_root(chord.name))
    key_root_pc = _root_pc(key.root)
    scale = _build_scale(key_root_pc, key.mode)
    romans = _ROMAN_MAJOR if key.mode == "major" else _ROMAN_MINOR

    interval = (chord_root_pc - key_root_pc) % 12
    if interval in [s % 12 for s in (_MAJOR_INTERVALS if key.mode == "major" else _MINOR_INTERVALS)]:
        idx = [s % 12 for s in (_MAJOR_INTERVALS if key.mode == "major" else _MINOR_INTERVALS)].index(interval)
        base = romans[idx]
    else:
        # Chromatic – use the interval in semitones
        base = f"#{interval}"

    # Append quality if not plain triad
    quality = _chord_quality(chord.name)

    # Normalize quality suffixes to standard notation
    _QUALITY_DISPLAY = {
        "dim": "°", "dim7": "°7",
        "aug": "+", "aug7": "+7",
        "m7b5": "ø7",
        "maj7": "Δ7", "maj9": "Δ9",
        "7": "7", "9": "9", "11": "11", "13": "13",
        "m7": "7", "m9": "9",  # minor roman already lowercase
        "sus4": "sus4", "sus2": "sus2",
        "add9": "add9",
        "m": "",  # case already handled by roman numeral case
        "maj": "",  # major quality already built into uppercase numeral
        "": "",
    }
    quality_display = _QUALITY_DISPLAY.get(quality, quality)

    if quality_display:
        base += quality_display
    return base


def _voice_leading_distance(a: List[int], b: List[int]) -> float:
    """Minimal aggregate semitone movement between two voicings.

    If voicings differ in size, the extra notes are treated as having
    moved from/to the nearest note in the other chord.
    """
    if not a or not b:
        return 0.0
    sa, sb = sorted(a), sorted(b)
    # Pad shorter list by duplicating nearest note
    while len(sa) < len(sb):
        sa.append(sa[-1])
    while len(sb) < len(sa):
        sb.append(sb[-1])
    total = sum(abs(x - y) for x, y in zip(sa, sb))
    return total / max(len(sa), 1)


def _common_tones(a: List[int], b: List[int]) -> int:
    """Count common pitch classes between two voicings."""
    pcs_a = {n % 12 for n in a}
    pcs_b = {n % 12 for n in b}
    return len(pcs_a & pcs_b)


def _chord_roughness(notes: List[int]) -> float:
    """Compute normalised roughness from interval content of a chord.

    Based on simplified Plomp-Levelt roughness for interval classes 0-6.
    Returns 0.0 (consonant) to 1.0 (dissonant).
    """
    if len(notes) < 2:
        return 0.0
    pcs = sorted({n % 12 for n in notes})
    intervals = []
    for i in range(len(pcs)):
        for j in range(i + 1, len(pcs)):
            ic = (pcs[j] - pcs[i]) % 12
            if ic > 6:
                ic = 12 - ic
            intervals.append(ic)
    if not intervals:
        return 0.0
    raw = sum(_ROUGHNESS.get(ic, 0.5) for ic in intervals) / len(intervals)
    return min(raw, 1.0)


def _chord_stability(notes: List[int]) -> float:
    """Stability heuristic (1.0 = very stable, 0.0 = unstable).

    Major/minor triads score highest; more extensions / altered tones
    reduce stability.
    """
    pcs = sorted({n % 12 for n in notes})
    unique = len(pcs)
    if unique <= 3:
        return 0.9
    if unique == 4:
        return 0.65
    if unique == 5:
        return 0.45
    return max(0.2, 1.0 - unique * 0.1)


def _tension_value(
    chord: RawChord,
    prev_chord: Optional[RawChord],
    beat_position: int,
    total_beats: int,
) -> float:
    """Compute tension for a single chord.

    T = 0.25*roughness + 0.25*(1-stability) + 0.25*density + 0.25*contextual
    """
    roughness = _chord_roughness(chord.notes)
    stability = _chord_stability(chord.notes)
    # Density as fraction of 7 notes (7-note voicing = 1.0)
    density = min(len(chord.notes) / 7.0, 1.0)
    # Contextual: voice-leading jump from previous chord
    contextual = 0.5  # default mid-tension
    if prev_chord is not None:
        vl = _voice_leading_distance(prev_chord.notes, chord.notes)
        contextual = min(vl / 12.0, 1.0)  # normalise to 12-semitone max

    t = 0.25 * roughness + 0.25 * (1.0 - stability) + 0.25 * density + 0.25 * contextual
    return round(min(max(t, 0.0), 1.0), 4)


def _voicing_spread(notes: List[int]) -> float:
    """Spread of a voicing in semitones (max - min)."""
    if len(notes) < 2:
        return 0.0
    return float(max(notes) - min(notes))


def _chromaticism_score(chords: List[RawChord], key: KeyCenter) -> float:
    """Fraction of pitch classes outside the detected scale."""
    scale_pcs = set(_build_scale(_root_pc(key.root), key.mode))
    all_pcs: set = set()
    for c in chords:
        for n in c.notes:
            all_pcs.add(n % 12)
    if not all_pcs:
        return 0.0
    outside = len(all_pcs - scale_pcs)
    return round(outside / len(all_pcs), 4)


def _complexity_score(analysis_partial: dict) -> float:
    """Overall harmonic complexity 0.0-1.0.

    Combines chromaticism, average tension, voicing spread, and number
    of unique roman numerals into a single scalar.
    """
    chroma = analysis_partial.get("chromaticism", 0.0)
    avg_tension = (
        statistics.mean(analysis_partial["tension_values"])
        if analysis_partial["tension_values"]
        else 0.0
    )
    spread_norm = min(analysis_partial.get("average_voicing_spread", 0.0) / 36.0, 1.0)
    unique_rn = len(set(analysis_partial.get("roman_numerals", []))) / max(
        len(analysis_partial.get("roman_numerals", [1])), 1
    )
    c = 0.3 * chroma + 0.3 * avg_tension + 0.2 * spread_norm + 0.2 * unique_rn
    return round(min(max(c, 0.0), 1.0), 4)


def _detect_genre_from_name(name: str, file_path: str) -> str:
    """Best-effort genre detection from file/progression name."""
    combined = f"{name} {Path(file_path).stem}"
    for genre, keywords in _GENRE_KEYWORDS.items():
        for kw in keywords:
            if kw.lower() in combined.lower():
                return genre
    return "unknown"


def _detect_genre_associations(chords: List[RawChord], key: KeyCenter) -> List[str]:
    """Return genre tags that match common harmonic signatures."""
    associations: List[str] = []
    qualities = [_chord_quality(c.name) for c in chords]
    has_7ths = any(q for q in qualities if "7" in q or "9" in q)
    has_aug = any("aug" in q for q in qualities)
    has_dim = any("dim" in q or "°" in q for q in qualities)

    if has_7ths:
        associations.append("jazz")
        associations.append("rnb")
    if has_aug:
        associations.append("jazz")
    if has_dim:
        associations.append("classical")
    if key.mode == "minor" and not has_7ths:
        associations.append("hip_hop")
    if key.mode == "major" and not has_7ths:
        associations.append("pop")
    return associations


# ---------------------------------------------------------------------------
# Parsing functions
# ---------------------------------------------------------------------------

def parse_progression(file_path: str) -> RawProgression:
    """Parse a single MPC Beats ``.progression`` JSON file.

    Args:
        file_path: Absolute or relative path to the ``.progression`` file.

    Returns:
        A :class:`RawProgression` dataclass.

    Raises:
        FileNotFoundError: If the file does not exist.
        json.JSONDecodeError: If the file is not valid JSON.
    """
    p = Path(file_path)
    logger.debug("Parsing progression: %s", p)
    with open(p, "r", encoding="utf-8") as f:
        data = json.load(f)

    prog = data.get("progression", data)  # handle both wrapped & flat
    chords = [
        RawChord(
            name=c.get("name", "?"),
            role=c.get("role", "Normal"),
            notes=c.get("notes", []),
        )
        for c in prog.get("chords", [])
    ]
    return RawProgression(
        name=prog.get("name", p.stem),
        root_note=prog.get("rootNote", "C"),
        scale=prog.get("scale", "Chromatic"),
        recording_octave=prog.get("recordingOctave", 2),
        chords=chords,
    )


def parse_all_progressions() -> Tuple[List[RawProgression], Dict[str, str]]:
    """Parse every ``.progression`` file in the MPC Beats Progressions dir.

    Returns:
        Tuple of (list of :class:`RawProgression`, name→filepath mapping),
        skipping any files that fail to parse.
    """
    prog_dir = get_mpc_beats_path() / "Progressions"
    if not prog_dir.exists():
        logger.warning("Progressions directory not found: %s", prog_dir)
        return [], {}

    results: List[RawProgression] = []
    name_to_path: Dict[str, str] = {}
    for fp in sorted(prog_dir.glob("*.progression")):
        try:
            prog = parse_progression(str(fp))
            results.append(prog)
            name_to_path[prog.name] = str(fp)
        except Exception:
            logger.exception("Failed to parse %s", fp)
    logger.info("Parsed %d progressions from %s", len(results), prog_dir)
    return results, name_to_path


def enrich_progression(raw: RawProgression, file_path: str) -> EnrichedProgression:
    """Compute full harmonic analysis for a raw progression.

    Args:
        raw: The parsed progression.
        file_path: Original file path (used for genre detection).

    Returns:
        An :class:`EnrichedProgression` with analysis attached.
    """
    key = _detect_key(raw.chords, raw.root_note)
    romans = [_roman_numeral(c, key) for c in raw.chords]

    # Voice-leading & common-tone arrays (between consecutive chords)
    vl_dists: List[float] = []
    ct_retain: List[int] = []
    for i in range(1, len(raw.chords)):
        vl_dists.append(round(_voice_leading_distance(raw.chords[i - 1].notes, raw.chords[i].notes), 4))
        ct_retain.append(_common_tones(raw.chords[i - 1].notes, raw.chords[i].notes))

    # Tension
    total = len(raw.chords) or 1
    tensions = [
        _tension_value(c, raw.chords[i - 1] if i > 0 else None, i, total)
        for i, c in enumerate(raw.chords)
    ]

    chromaticism = _chromaticism_score(raw.chords, key)
    avg_spread = (
        statistics.mean([_voicing_spread(c.notes) for c in raw.chords])
        if raw.chords
        else 0.0
    )
    genre_assoc = _detect_genre_associations(raw.chords, key)
    genre = _detect_genre_from_name(raw.name, file_path)

    partial = {
        "roman_numerals": romans,
        "tension_values": tensions,
        "chromaticism": chromaticism,
        "average_voicing_spread": avg_spread,
    }
    complexity = _complexity_score(partial)

    analysis = HarmonicAnalysis(
        roman_numerals=romans,
        key_center=key,
        voice_leading_distances=vl_dists,
        common_tone_retention=ct_retain,
        tension_values=tensions,
        genre_associations=genre_assoc,
        complexity=complexity,
        chromaticism=chromaticism,
        average_voicing_spread=round(avg_spread, 2),
    )

    display = raw.name.replace("-", " – ", 1) if "-" in raw.name else raw.name
    return EnrichedProgression(
        raw=raw,
        file_path=file_path,
        genre=genre,
        display_name=display,
        analysis=analysis,
    )


# ---------------------------------------------------------------------------
# Arp pattern parsing (MIDI via mido)
# ---------------------------------------------------------------------------

def _parse_arp_filename(filename: str) -> Tuple[str, str, str]:
    """Parse an arp pattern filename like '003-Chord-Dance 01.mid'.

    Returns:
        (category, sub_category, genre)
    """
    stem = Path(filename).stem
    # Strip leading number prefix
    parts = stem.split("-", 2)
    if len(parts) >= 3:
        category = parts[1].strip()
        sub_raw = parts[2].strip()
    elif len(parts) == 2:
        category = parts[0].strip()
        sub_raw = parts[1].strip()
    else:
        category = "Unknown"
        sub_raw = stem

    # Remove trailing number from sub_category
    sub_category = re.sub(r"\s*\d+$", "", sub_raw).strip()

    # Guess genre from sub_category
    genre = "unknown"
    lower = sub_category.lower()
    for g, kws in _GENRE_KEYWORDS.items():
        for kw in kws:
            if kw.lower() in lower:
                genre = g
                break
        if genre != "unknown":
            break
    return category, sub_category, genre


def _estimate_swing(note_starts: List[int], tpb: int) -> float:
    """Estimate swing amount from note start positions.

    Returns 0.0 (straight) to 1.0 (heavy shuffle).
    """
    if len(note_starts) < 4 or tpb == 0:
        return 0.0

    eighth = tpb // 2
    if eighth == 0:
        return 0.0

    offbeat_offsets: List[int] = []
    for t in note_starts:
        # Position within a beat
        pos = t % tpb
        # If this is roughly on the off-eighth (second eighth of beat)
        if eighth * 0.3 < pos < eighth * 1.7:
            offbeat_offsets.append(pos)

    if len(offbeat_offsets) < 2:
        return 0.0

    avg_offset = statistics.mean(offbeat_offsets)
    # Perfect straight = eighth, perfect shuffle ≈ 2/3 beat
    swing = (avg_offset - eighth) / (tpb * 2 / 3 - eighth) if (tpb * 2 / 3 - eighth) != 0 else 0.0
    return round(max(0.0, min(1.0, swing)), 3)


def _finest_grid(note_starts: List[int], tpb: int) -> int:
    """Return the finest rhythmic grid in ticks (e.g. 120 = 16th at 480 ppq)."""
    if len(note_starts) < 2 or tpb == 0:
        return tpb

    diffs = sorted({abs(b - a) for a, b in zip(note_starts, note_starts[1:]) if abs(b - a) > 0})
    if not diffs:
        return tpb

    # Return smallest common difference
    return diffs[0]


def parse_arp_pattern(file_path: str) -> ParsedArpPattern:
    """Parse a single MPC Beats arp ``.mid`` file.

    Args:
        file_path: Path to the MIDI file.

    Returns:
        A :class:`ParsedArpPattern` with note data and analysis.
    """
    fp = Path(file_path)
    logger.debug("Parsing arp pattern: %s", fp)

    mid = mido.MidiFile(str(fp))
    tpb = mid.ticks_per_beat or 480

    # Collect notes
    notes: List[dict] = []
    tick = 0
    active: Dict[int, dict] = {}  # pitch → partial note
    for msg in mido.merge_tracks(mid.tracks):
        tick += msg.time
        if msg.type == "note_on" and msg.velocity > 0:
            active[msg.note] = {"pitch": msg.note, "start": tick, "velocity": msg.velocity}
        elif msg.type in ("note_off",) or (msg.type == "note_on" and msg.velocity == 0):
            if msg.note in active:
                n = active.pop(msg.note)
                n["duration"] = tick - n["start"]
                notes.append(n)
    # Close any still-active notes
    for n in active.values():
        n["duration"] = tick - n["start"]
        notes.append(n)

    notes.sort(key=lambda n: n["start"])

    # Analysis
    pitches = [n["pitch"] for n in notes]
    velocities = [n["velocity"] for n in notes]
    starts = [n["start"] for n in notes]

    duration_ticks = max((n["start"] + n["duration"] for n in notes), default=0)
    duration_beats = duration_ticks / tpb if tpb else 0.0

    pitch_range = {
        "min": min(pitches, default=0),
        "max": max(pitches, default=0),
        "span": (max(pitches, default=0) - min(pitches, default=0)),
    }

    vel_stats = {
        "min": float(min(velocities, default=0)),
        "max": float(max(velocities, default=0)),
        "mean": round(statistics.mean(velocities), 2) if velocities else 0.0,
        "std": round(statistics.stdev(velocities), 2) if len(velocities) > 1 else 0.0,
    }

    density = len(notes) / duration_beats if duration_beats > 0 else 0.0

    # Interval distribution (successive note pitch intervals)
    interval_dist: Dict[int, int] = {}
    for i in range(1, len(pitches)):
        iv = abs(pitches[i] - pitches[i - 1])
        interval_dist[iv] = interval_dist.get(iv, 0) + 1

    # Polyphony – check overlapping notes
    max_poly = 1
    if notes:
        events = []
        for n in notes:
            events.append((n["start"], 1))
            events.append((n["start"] + n["duration"], -1))
        events.sort(key=lambda e: (e[0], e[1]))
        current = 0
        for _, delta in events:
            current += delta
            max_poly = max(max_poly, current)

    cat, subcat, genre = _parse_arp_filename(fp.name)

    analysis = ArpAnalysis(
        duration_ticks=duration_ticks,
        duration_beats=round(duration_beats, 2),
        note_count=len(notes),
        pitch_range=pitch_range,
        density=round(density, 3),
        velocity_stats=vel_stats,
        rhythmic_grid=_finest_grid(starts, tpb),
        swing_amount=_estimate_swing(starts, tpb),
        interval_distribution=interval_dist,
        polyphony="poly" if max_poly > 1 else "mono",
        max_polyphony=max_poly,
    )

    return ParsedArpPattern(
        file_name=fp.name,
        file_path=str(fp),
        category=cat,
        sub_category=subcat,
        genre=genre,
        notes=notes,
        analysis=analysis,
    )


def parse_all_arp_patterns() -> List[ParsedArpPattern]:
    """Parse all ``.mid`` files in the MPC Beats Arp Patterns directory.

    Returns:
        List of :class:`ParsedArpPattern`, skipping failures.
    """
    arp_dir = get_mpc_beats_path() / "Arp Patterns"
    if not arp_dir.exists():
        logger.warning("Arp Patterns directory not found: %s", arp_dir)
        return []

    results: List[ParsedArpPattern] = []
    for fp in sorted(arp_dir.glob("*.mid")):
        try:
            results.append(parse_arp_pattern(str(fp)))
        except Exception:
            logger.exception("Failed to parse arp %s", fp)
    logger.info("Parsed %d arp patterns from %s", len(results), arp_dir)
    return results


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------

def _tension_arc_shape(tensions: List[float]) -> str:
    """Classify the tension arc as rising, falling, arch, or flat."""
    if not tensions or len(tensions) < 2:
        return "flat"
    mid = len(tensions) // 2
    first_half = statistics.mean(tensions[:mid]) if mid > 0 else 0
    second_half = statistics.mean(tensions[mid:]) if mid < len(tensions) else 0
    peak_idx = tensions.index(max(tensions))

    if abs(first_half - second_half) < 0.05:
        return "flat"
    if 0.25 * len(tensions) < peak_idx < 0.75 * len(tensions):
        return "arch"
    if first_half < second_half:
        return "rising"
    return "falling"


def build_genre_profiles(
    enriched: List[EnrichedProgression],
) -> Dict[str, GenreHarmonicProfile]:
    """Aggregate enriched progressions into per-genre harmonic profiles.

    Args:
        enriched: List of enriched progressions.

    Returns:
        Mapping of genre → :class:`GenreHarmonicProfile`.
    """
    from collections import defaultdict

    buckets: Dict[str, List[EnrichedProgression]] = defaultdict(list)
    for ep in enriched:
        buckets[ep.genre].append(ep)

    profiles: Dict[str, GenreHarmonicProfile] = {}
    for genre, items in buckets.items():
        complexities = [e.analysis.complexity for e in items]
        chromas = [e.analysis.chromaticism for e in items]
        spreads = [e.analysis.average_voicing_spread for e in items]
        vl_dists = []
        all_tensions: List[float] = []
        chord_quals: List[str] = []

        for e in items:
            vl_dists.extend(e.analysis.voice_leading_distances)
            all_tensions.extend(e.analysis.tension_values)
            for c in e.raw.chords:
                chord_quals.append(_chord_quality(c.name))

        # Most common qualities
        qual_counts: Dict[str, int] = {}
        for q in chord_quals:
            qual_counts[q] = qual_counts.get(q, 0) + 1
        common_quals = sorted(qual_counts, key=qual_counts.get, reverse=True)[:5]  # type: ignore[arg-type]

        profiles[genre] = GenreHarmonicProfile(
            genre=genre,
            avg_complexity=round(statistics.mean(complexities), 4) if complexities else 0.0,
            avg_chromaticism=round(statistics.mean(chromas), 4) if chromas else 0.0,
            avg_voicing_spread=round(statistics.mean(spreads), 2) if spreads else 0.0,
            avg_voice_leading_distance=round(statistics.mean(vl_dists), 4) if vl_dists else 0.0,
            common_chord_qualities=common_quals,
            typical_tension_arc=_tension_arc_shape(all_tensions),
            progression_count=len(items),
        )

    logger.info("Built genre profiles for %d genres", len(profiles))
    return profiles


def extract_voicing_templates(
    enriched: List[EnrichedProgression],
) -> Dict[str, List[List[int]]]:
    """Map chord quality → list of voicing templates (note lists).

    Each template is the raw MIDI notes for one instance of that chord
    quality, de-duplicated by pitch-class content.

    Args:
        enriched: Enriched progressions to extract from.

    Returns:
        Dict of quality string → list of voicing note-lists.
    """
    from collections import defaultdict

    templates: Dict[str, List[List[int]]] = defaultdict(list)
    seen: Dict[str, set] = defaultdict(set)

    for ep in enriched:
        for chord in ep.raw.chords:
            quality = _chord_quality(chord.name)
            # Use frozenset of pitch classes as dedup key
            pc_key = frozenset(n % 12 for n in chord.notes)
            key_str = str(sorted(pc_key))
            if key_str not in seen[quality]:
                seen[quality].add(key_str)
                templates[quality].append(list(chord.notes))

    logger.info(
        "Extracted voicing templates for %d chord qualities", len(templates)
    )
    return dict(templates)


# ---------------------------------------------------------------------------
# Top-level loader
# ---------------------------------------------------------------------------

def load_corpus() -> CorpusData:
    """Load & analyse the full MPC Beats corpus.

    Parses all progressions and arp patterns, enriches progressions with
    harmonic analysis, builds genre profiles, and extracts voicing
    templates.

    Returns:
        A :class:`CorpusData` bundle.
    """
    logger.info("Loading MPC Beats corpus from %s", get_mpc_beats_path())

    raw_progs, name_to_path = parse_all_progressions()

    # Enrich each progression using the pre-built name→path mapping
    prog_dir = get_mpc_beats_path() / "Progressions"
    enriched: List[EnrichedProgression] = []
    for rp in raw_progs:
        fp_str = name_to_path.get(rp.name, str(prog_dir / f"{rp.name}.progression"))
        try:
            enriched.append(enrich_progression(rp, fp_str))
        except Exception:
            logger.exception("Failed to enrich progression '%s'", rp.name)

    arp_patterns = parse_all_arp_patterns()
    genre_profiles = build_genre_profiles(enriched)
    voicing_templates = extract_voicing_templates(enriched)

    logger.info(
        "Corpus loaded: %d progressions, %d enriched, %d arps, %d genres",
        len(raw_progs), len(enriched), len(arp_patterns), len(genre_profiles),
    )

    return CorpusData(
        progressions=raw_progs,
        enriched=enriched,
        arp_patterns=arp_patterns,
        genre_profiles=genre_profiles,
        voicing_templates=voicing_templates,
    )
