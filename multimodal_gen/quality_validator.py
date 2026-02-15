"""Quality Validation Suite - Industry-standard metrics for generated music."""

from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional, Set
from enum import Enum
import statistics
import math
import logging

logger = logging.getLogger(__name__)

try:
    from multimodal_gen.intelligence.critics import (
        compute_vlc, compute_bkas, compute_adc, run_all_critics,
        CriticResult, CriticReport,
    )
    _HAS_CRITICS = True
except ImportError:
    _HAS_CRITICS = False


class QualityLevel(Enum):
    """Quality level classifications."""
    EXCELLENT = "excellent"
    GOOD = "good"
    ACCEPTABLE = "acceptable"
    POOR = "poor"
    FAILING = "failing"


class MetricCategory(Enum):
    """Metric category classifications."""
    MIDI_QUALITY = "midi_quality"
    MUSIC_THEORY = "music_theory"
    HUMANIZATION = "humanization"
    GENRE_CONFORMANCE = "genre_conformance"
    STRUCTURE = "structure"
    DYNAMICS = "dynamics"
    RHYTHM = "rhythm"


@dataclass
class MetricResult:
    """Result of a single quality metric."""
    name: str
    category: MetricCategory
    value: float
    normalized_score: float
    quality_level: QualityLevel
    threshold_min: float
    threshold_max: float
    details: str = ""
    suggestions: List[str] = field(default_factory=list)


@dataclass
class ValidationReport:
    """Complete validation report."""
    overall_score: float
    overall_level: QualityLevel
    metrics: List[MetricResult]
    category_scores: Dict[MetricCategory, float]
    passed: bool
    summary: str
    recommendations: List[str]


# Genre profiles with thresholds
GENRE_QUALITY_PROFILES = {
    "hip_hop": {
        "tempo_range": (70, 100),
        "velocity_variance_min": 0.08,
        "note_density_range": (1.5, 4.0),
        "timing_variance_max": 0.15,
    },
    "jazz": {
        "tempo_range": (80, 200),
        "velocity_variance_min": 0.12,
        "note_density_range": (2.0, 6.0),
        "timing_variance_max": 0.20,
    },
    "pop": {
        "tempo_range": (90, 140),
        "velocity_variance_min": 0.06,
        "note_density_range": (2.0, 5.0),
        "timing_variance_max": 0.10,
    },
    "edm": {
        "tempo_range": (120, 150),
        "velocity_variance_min": 0.04,
        "note_density_range": (3.0, 8.0),
        "timing_variance_max": 0.05,
    },
    "rock": {
        "tempo_range": (100, 160),
        "velocity_variance_min": 0.08,
        "note_density_range": (2.5, 6.0),
        "timing_variance_max": 0.12,
    },
}

# Pitch ranges for common instruments (MIDI note numbers)
# Pulled from the canonical instrument_ranges module.
try:
    from multimodal_gen.instrument_ranges import INSTRUMENT_RANGES as _IR
    INSTRUMENT_PITCH_RANGES = {name: (r.low, r.high) for name, r in _IR.items()}
    # Keep legacy keys that validators may reference
    INSTRUMENT_PITCH_RANGES.setdefault("drums", (35, 81))
except ImportError:
    # Fallback: minimal set so the validator still works standalone
    INSTRUMENT_PITCH_RANGES = {
        "piano": (21, 108),
        "guitar": (40, 88),
        "bass": (28, 67),
        "drums": (35, 81),
        "synth": (21, 108),
    }

# Scale definitions (semitones from root)
SCALES = {
    "major": [0, 2, 4, 5, 7, 9, 11],
    "minor": [0, 2, 3, 5, 7, 8, 10],
    "dorian": [0, 2, 3, 5, 7, 9, 10],
    "mixolydian": [0, 2, 4, 5, 7, 9, 10],
    "blues": [0, 3, 5, 6, 7, 10],
    "chromatic": list(range(12)),
}

# Note to number mapping
NOTE_TO_NUM = {
    "C": 0, "C#": 1, "Db": 1, "D": 2, "D#": 3, "Eb": 3,
    "E": 4, "F": 5, "F#": 6, "Gb": 6, "G": 7, "G#": 8,
    "Ab": 8, "A": 9, "A#": 10, "Bb": 10, "B": 11,
}


class QualityValidator:
    """Validates generated MIDI with industry-standard metrics."""
    
    def __init__(self, strict_mode: bool = False):
        """Initialize validator.
        
        Args:
            strict_mode: If True, apply stricter thresholds
        """
        self.strict_mode = strict_mode
        self.genre_profiles = self._load_genre_profiles()
    
    def validate(self, notes, genre="pop", key="C", scale="major", tempo=120, 
                 ticks_per_beat=480, **kwargs) -> ValidationReport:
        """Run full validation suite.
        
        Args:
            notes: List of (start_tick, duration_ticks, pitch, velocity) tuples
            genre: Music genre for conformance checks
            key: Root note for scale analysis
            scale: Scale type for theory checks
            tempo: Tempo in BPM
            ticks_per_beat: MIDI ticks per beat
            **kwargs: Additional parameters:
                instrument: Instrument name for pitch range checks
                reference_notes: List[Tuple] — drum/reference note tuples for BKAS
                    (kick = MIDI pitch 36)
                tension_curve_data: List[float] — tension curve for ADC analysis
            
        Returns:
            ValidationReport with all metrics and recommendations
        """
        if not notes:
            return self._create_empty_report()
        
        instrument = kwargs.get("instrument", "piano")
        metrics = []
        
        # MIDI Quality Metrics
        metrics.append(self.analyze_note_density(notes, ticks_per_beat, genre))
        metrics.append(self.analyze_velocity_distribution(notes))
        metrics.append(self.analyze_pitch_range(notes, instrument))
        metrics.append(self.analyze_duration_distribution(notes, ticks_per_beat))
        metrics.append(self.analyze_note_count(notes))
        metrics.append(self.analyze_note_overlap(notes))
        
        # Humanization Metrics
        metrics.append(self.analyze_timing_variance(notes, ticks_per_beat, genre))
        metrics.append(self.analyze_velocity_variance(notes))
        metrics.append(self.analyze_repetition(notes, ticks_per_beat))
        metrics.append(self.analyze_velocity_patterns(notes))
        metrics.append(self.analyze_note_spacing(notes, ticks_per_beat))
        
        # Music Theory Metrics
        metrics.append(self.analyze_scale_adherence(notes, key, scale))
        metrics.append(self.analyze_pitch_variety(notes))
        metrics.append(self.analyze_interval_distribution(notes))
        metrics.append(self.analyze_melodic_contour(notes))
        
        # Genre Conformance
        metrics.append(self.analyze_tempo_conformance(tempo, genre))
        metrics.append(self.analyze_genre_velocity_profile(notes, genre))
        
        # Structure Metrics
        metrics.append(self.analyze_phrase_structure(notes, ticks_per_beat))
        metrics.append(self.analyze_motif_coherence(notes, ticks_per_beat))
        metrics.append(self.analyze_rhythmic_consistency(notes, ticks_per_beat))
        
        # Dynamics Metrics
        metrics.append(self.analyze_dynamic_range(notes))
        metrics.append(self.analyze_velocity_progression(notes))
        metrics.append(self.analyze_accent_patterns(notes))
        
        # Rhythm Metrics
        metrics.append(self.analyze_rhythmic_complexity(notes, ticks_per_beat))
        metrics.append(self.analyze_syncopation(notes, ticks_per_beat))
        metrics.append(self.analyze_note_duration_variety(notes, ticks_per_beat))
        
        # Sprint 2: Critic-based metrics (when module available)
        if _HAS_CRITICS:
            metrics.append(self.analyze_voice_leading_cost(notes, key))
            reference_notes = kwargs.get("reference_notes")
            metrics.append(self.analyze_bass_kick_alignment(notes, reference_notes))
            tension_curve_data = kwargs.get("tension_curve_data")
            metrics.append(self.analyze_arrangement_density(
                notes, tension_curve_data, ticks_per_beat
            ))
        
        # Calculate scores
        overall_score = self._calculate_overall_score(metrics)
        category_scores = self._calculate_category_scores(metrics)
        overall_level = self._score_to_level(overall_score)
        passed = overall_score >= 0.6
        summary = self._generate_summary(overall_score, overall_level, metrics)
        recommendations = self._generate_recommendations(metrics)
        
        return ValidationReport(
            overall_score=overall_score,
            overall_level=overall_level,
            metrics=metrics,
            category_scores=category_scores,
            passed=passed,
            summary=summary,
            recommendations=recommendations
        )

    # MIDI Quality Metrics
    
    def analyze_note_density(self, notes, ticks_per_beat, genre) -> MetricResult:
        """Analyze notes per beat."""
        if not notes:
            return self._create_failing_metric("Note Density", MetricCategory.MIDI_QUALITY)
        
        total_beats = (max(n[0] + n[1] for n in notes)) / ticks_per_beat
        notes_per_beat = len(notes) / max(total_beats, 1)
        
        profile = self.genre_profiles.get(genre, self.genre_profiles["pop"])
        min_density, max_density = profile["note_density_range"]
        
        # Normalize score: 1.0 if within range, decreases outside
        if min_density <= notes_per_beat <= max_density:
            score = 1.0
            level = QualityLevel.EXCELLENT
            details = f"{notes_per_beat:.2f} notes/beat (optimal for {genre})"
            suggestions = []
        elif notes_per_beat < min_density:
            score = max(0.0, notes_per_beat / min_density)
            level = self._score_to_level(score)
            details = f"{notes_per_beat:.2f} notes/beat (sparse for {genre})"
            suggestions = ["Consider adding more notes to increase density"]
        else:
            score = max(0.0, 1.0 - (notes_per_beat - max_density) / max_density)
            level = self._score_to_level(score)
            details = f"{notes_per_beat:.2f} notes/beat (dense for {genre})"
            suggestions = ["Consider reducing note density for clarity"]
        
        return MetricResult(
            name="Note Density",
            category=MetricCategory.MIDI_QUALITY,
            value=notes_per_beat,
            normalized_score=score,
            quality_level=level,
            threshold_min=min_density,
            threshold_max=max_density,
            details=details,
            suggestions=suggestions
        )
    
    def analyze_velocity_distribution(self, notes) -> MetricResult:
        """Analyze velocity variance."""
        if not notes:
            return self._create_failing_metric("Velocity Distribution", MetricCategory.MIDI_QUALITY)
        
        velocities = [n[3] for n in notes]
        mean_vel = statistics.mean(velocities)
        
        if len(velocities) > 1:
            variance = statistics.variance(velocities)
            std_dev = math.sqrt(variance)
            cv = std_dev / mean_vel if mean_vel > 0 else 0
        else:
            cv = 0
        
        # Good variance coefficient: 0.10 to 0.30
        if 0.10 <= cv <= 0.30:
            score = 1.0
            level = QualityLevel.EXCELLENT
            details = f"Good velocity variety (CV={cv:.3f})"
            suggestions = []
        elif cv < 0.10:
            score = max(0.0, cv / 0.10)
            level = self._score_to_level(score)
            details = f"Low velocity variety (CV={cv:.3f})"
            suggestions = ["Add more velocity variation for expressiveness"]
        else:
            score = max(0.0, 1.0 - (cv - 0.30) / 0.30)
            level = self._score_to_level(score)
            details = f"High velocity variance (CV={cv:.3f})"
            suggestions = ["Reduce extreme velocity variations"]
        
        return MetricResult(
            name="Velocity Distribution",
            category=MetricCategory.MIDI_QUALITY,
            value=cv,
            normalized_score=score,
            quality_level=level,
            threshold_min=0.10,
            threshold_max=0.30,
            details=details,
            suggestions=suggestions
        )
    
    def analyze_pitch_range(self, notes, instrument="piano") -> MetricResult:
        """Validate pitch range for instrument."""
        if not notes:
            return self._create_failing_metric("Pitch Range", MetricCategory.MIDI_QUALITY)
        
        pitches = [n[2] for n in notes]
        min_pitch = min(pitches)
        max_pitch = max(pitches)
        pitch_span = max_pitch - min_pitch
        
        inst_range = INSTRUMENT_PITCH_RANGES.get(instrument, INSTRUMENT_PITCH_RANGES["piano"])
        inst_min, inst_max = inst_range
        
        # Check if notes are within instrument range
        in_range = inst_min <= min_pitch and max_pitch <= inst_max
        
        if in_range:
            # Check if using good variety (at least 1 octave)
            if pitch_span >= 12:
                score = 1.0
                level = QualityLevel.EXCELLENT
                details = f"Pitch range {min_pitch}-{max_pitch} ({pitch_span} semitones)"
                suggestions = []
            else:
                score = 0.7
                level = QualityLevel.ACCEPTABLE
                details = f"Limited pitch range: {pitch_span} semitones"
                suggestions = ["Consider using wider pitch range for variety"]
        else:
            score = 0.3
            level = QualityLevel.POOR
            details = f"Notes outside {instrument} range: {min_pitch}-{max_pitch}"
            suggestions = [f"Adjust pitches to fit {instrument} range ({inst_min}-{inst_max})"]
        
        return MetricResult(
            name="Pitch Range",
            category=MetricCategory.MIDI_QUALITY,
            value=pitch_span,
            normalized_score=score,
            quality_level=level,
            threshold_min=inst_min,
            threshold_max=inst_max,
            details=details,
            suggestions=suggestions
        )
    
    def analyze_duration_distribution(self, notes, ticks_per_beat) -> MetricResult:
        """Analyze note duration variety."""
        if not notes:
            return self._create_failing_metric("Duration Distribution", MetricCategory.MIDI_QUALITY)
        
        durations = [n[1] / ticks_per_beat for n in notes]
        unique_durations = len(set(durations))
        
        # More variety is better (up to a point)
        if unique_durations >= 4:
            score = 1.0
            level = QualityLevel.EXCELLENT
            details = f"{unique_durations} different note durations"
            suggestions = []
        elif unique_durations >= 2:
            score = 0.7
            level = QualityLevel.GOOD
            details = f"{unique_durations} different note durations"
            suggestions = ["Consider adding more rhythmic variety"]
        else:
            score = 0.4
            level = QualityLevel.ACCEPTABLE
            details = f"Only {unique_durations} note duration(s)"
            suggestions = ["Add more rhythmic variation with different note lengths"]
        
        return MetricResult(
            name="Duration Distribution",
            category=MetricCategory.MIDI_QUALITY,
            value=unique_durations,
            normalized_score=score,
            quality_level=level,
            threshold_min=2,
            threshold_max=8,
            details=details,
            suggestions=suggestions
        )
    
    def analyze_note_count(self, notes) -> MetricResult:
        """Validate sufficient note count."""
        count = len(notes)
        
        if count >= 20:
            score = 1.0
            level = QualityLevel.EXCELLENT
            details = f"{count} notes (good length)"
            suggestions = []
        elif count >= 10:
            score = 0.7
            level = QualityLevel.GOOD
            details = f"{count} notes"
            suggestions = []
        elif count >= 4:
            score = 0.5
            level = QualityLevel.ACCEPTABLE
            details = f"{count} notes (short)"
            suggestions = ["Consider generating longer sequences"]
        else:
            score = 0.2
            level = QualityLevel.POOR
            details = f"Only {count} notes"
            suggestions = ["Generate more notes for better analysis"]
        
        return MetricResult(
            name="Note Count",
            category=MetricCategory.MIDI_QUALITY,
            value=count,
            normalized_score=score,
            quality_level=level,
            threshold_min=10,
            threshold_max=1000,
            details=details,
            suggestions=suggestions
        )
    
    def analyze_note_overlap(self, notes) -> MetricResult:
        """Analyze note overlap/polyphony characteristics."""
        if len(notes) < 2:
            return self._create_acceptable_metric("Note Overlap", MetricCategory.MIDI_QUALITY, 0.7)
        
        # Sort by start time
        sorted_notes = sorted(notes, key=lambda n: n[0])
        
        # Check for overlapping notes
        overlaps = 0
        for i in range(len(sorted_notes) - 1):
            note_end = sorted_notes[i][0] + sorted_notes[i][1]
            for j in range(i + 1, len(sorted_notes)):
                if sorted_notes[j][0] < note_end:
                    overlaps += 1
                else:
                    break
        
        overlap_ratio = overlaps / len(notes)
        
        # Some overlap is good for polyphonic music
        if 0.1 <= overlap_ratio <= 0.5:
            score = 1.0
            level = QualityLevel.EXCELLENT
            details = f"Good polyphony ({overlap_ratio:.1%} overlap)"
            suggestions = []
        elif overlap_ratio < 0.1:
            score = 0.7
            level = QualityLevel.GOOD
            details = f"Mostly monophonic ({overlap_ratio:.1%} overlap)"
            suggestions = ["Consider adding harmony or counter-melodies"]
        else:
            score = 0.6
            level = QualityLevel.ACCEPTABLE
            details = f"High polyphony ({overlap_ratio:.1%} overlap)"
            suggestions = ["Consider reducing voice density for clarity"]
        
        return MetricResult(
            name="Note Overlap",
            category=MetricCategory.MIDI_QUALITY,
            value=overlap_ratio,
            normalized_score=score,
            quality_level=level,
            threshold_min=0.1,
            threshold_max=0.5,
            details=details,
            suggestions=suggestions
        )

    # Humanization Metrics
    
    def analyze_timing_variance(self, notes, ticks_per_beat, genre) -> MetricResult:
        """Detect robotic vs humanized timing."""
        if len(notes) < 2:
            return self._create_failing_metric("Timing Variance", MetricCategory.HUMANIZATION)
        
        # Check for perfectly quantized notes (all start on exact beat divisions)
        starts = [n[0] for n in notes]
        
        # Calculate timing deviations from perfect quantization
        deviations = []
        for start in starts:
            # Find nearest 16th note position
            nearest_16th = round(start / (ticks_per_beat / 4)) * (ticks_per_beat / 4)
            deviation = abs(start - nearest_16th)
            deviations.append(deviation / ticks_per_beat)
        
        avg_deviation = statistics.mean(deviations)
        
        profile = self.genre_profiles.get(genre, self.genre_profiles["pop"])
        max_variance = profile.get("timing_variance_max", 0.10)
        
        # EDM should be more quantized, jazz more loose
        if genre == "edm":
            ideal_range = (0.0, 0.03)
        elif genre == "jazz":
            ideal_range = (0.03, 0.15)
        else:
            ideal_range = (0.02, 0.08)
        
        if ideal_range[0] <= avg_deviation <= ideal_range[1]:
            score = 1.0
            level = QualityLevel.EXCELLENT
            details = f"Good humanization ({avg_deviation:.3f} beat deviation)"
            suggestions = []
        elif avg_deviation < ideal_range[0]:
            score = max(0.5, avg_deviation / ideal_range[0])
            level = self._score_to_level(score)
            details = f"Robotic timing ({avg_deviation:.3f} beat deviation)"
            suggestions = ["Add micro-timing variations for humanization"]
        else:
            score = max(0.3, 1.0 - (avg_deviation - ideal_range[1]) / ideal_range[1])
            level = self._score_to_level(score)
            details = f"Excessive timing variance ({avg_deviation:.3f})"
            suggestions = ["Reduce timing variations for tighter feel"]
        
        return MetricResult(
            name="Timing Variance",
            category=MetricCategory.HUMANIZATION,
            value=avg_deviation,
            normalized_score=score,
            quality_level=level,
            threshold_min=ideal_range[0],
            threshold_max=ideal_range[1],
            details=details,
            suggestions=suggestions
        )
    
    def analyze_velocity_variance(self, notes) -> MetricResult:
        """Analyze dynamic variation coefficient."""
        if not notes:
            return self._create_failing_metric("Velocity Variance", MetricCategory.HUMANIZATION)
        
        velocities = [n[3] for n in notes]
        
        if len(velocities) > 1:
            std_dev = statistics.stdev(velocities)
        else:
            std_dev = 0
        
        # Good std dev: 8-20
        if 8 <= std_dev <= 20:
            score = 1.0
            level = QualityLevel.EXCELLENT
            details = f"Good velocity variation (σ={std_dev:.1f})"
            suggestions = []
        elif std_dev < 8:
            score = max(0.4, std_dev / 8)
            level = self._score_to_level(score)
            details = f"Low velocity variation (σ={std_dev:.1f})"
            suggestions = ["Add more dynamic expression"]
        else:
            score = max(0.5, 1.0 - (std_dev - 20) / 20)
            level = self._score_to_level(score)
            details = f"High velocity variation (σ={std_dev:.1f})"
            suggestions = ["Moderate extreme velocity changes"]
        
        return MetricResult(
            name="Velocity Variance",
            category=MetricCategory.HUMANIZATION,
            value=std_dev,
            normalized_score=score,
            quality_level=level,
            threshold_min=8,
            threshold_max=20,
            details=details,
            suggestions=suggestions
        )
    
    def analyze_repetition(self, notes, ticks_per_beat) -> MetricResult:
        """Detect exact pattern repetition."""
        if len(notes) < 4:
            return self._create_acceptable_metric("Repetition", MetricCategory.HUMANIZATION, 0.5)
        
        # Look for repeated 4-note patterns
        patterns = []
        for i in range(len(notes) - 3):
            pattern = tuple((notes[i+j][2], notes[i+j][3]) for j in range(4))
            patterns.append(pattern)
        
        if not patterns:
            return self._create_acceptable_metric("Repetition", MetricCategory.HUMANIZATION, 0.7)
        
        # Count unique patterns
        unique_patterns = len(set(patterns))
        repetition_rate = 1.0 - (unique_patterns / len(patterns))
        
        # Some repetition is good, too much is bad
        if 0.2 <= repetition_rate <= 0.5:
            score = 1.0
            level = QualityLevel.EXCELLENT
            details = f"Good pattern repetition ({repetition_rate:.2f})"
            suggestions = []
        elif repetition_rate < 0.2:
            score = 0.7
            level = QualityLevel.GOOD
            details = f"Low repetition ({repetition_rate:.2f})"
            suggestions = ["Consider adding some repeated motifs"]
        else:
            score = max(0.3, 1.0 - (repetition_rate - 0.5) / 0.5)
            level = self._score_to_level(score)
            details = f"High repetition ({repetition_rate:.2f})"
            suggestions = ["Add more variation to avoid monotony"]
        
        return MetricResult(
            name="Repetition",
            category=MetricCategory.HUMANIZATION,
            value=repetition_rate,
            normalized_score=score,
            quality_level=level,
            threshold_min=0.2,
            threshold_max=0.5,
            details=details,
            suggestions=suggestions
        )
    
    def analyze_velocity_patterns(self, notes) -> MetricResult:
        """Analyze velocity patterns for expressiveness."""
        if len(notes) < 3:
            return self._create_acceptable_metric("Velocity Patterns", MetricCategory.HUMANIZATION, 0.6)
        
        velocities = [n[3] for n in notes]
        
        # Check for velocity changes between consecutive notes
        changes = 0
        for i in range(len(velocities) - 1):
            if abs(velocities[i+1] - velocities[i]) >= 5:
                changes += 1
        
        change_rate = changes / (len(velocities) - 1)
        
        if 0.4 <= change_rate <= 0.8:
            score = 1.0
            level = QualityLevel.EXCELLENT
            details = f"Good velocity dynamics ({change_rate:.2f} change rate)"
            suggestions = []
        elif change_rate < 0.4:
            score = max(0.5, change_rate / 0.4)
            level = self._score_to_level(score)
            details = f"Static velocities ({change_rate:.2f} change rate)"
            suggestions = ["Add more dynamic expression"]
        else:
            score = 0.8
            level = QualityLevel.GOOD
            details = f"Highly dynamic ({change_rate:.2f} change rate)"
            suggestions = []
        
        return MetricResult(
            name="Velocity Patterns",
            category=MetricCategory.HUMANIZATION,
            value=change_rate,
            normalized_score=score,
            quality_level=level,
            threshold_min=0.4,
            threshold_max=0.8,
            details=details,
            suggestions=suggestions
        )
    
    def analyze_note_spacing(self, notes, ticks_per_beat) -> MetricResult:
        """Analyze spacing between note starts."""
        if len(notes) < 2:
            return self._create_acceptable_metric("Note Spacing", MetricCategory.HUMANIZATION, 0.6)
        
        sorted_notes = sorted(notes, key=lambda n: n[0])
        gaps = []
        for i in range(len(sorted_notes) - 1):
            gap = (sorted_notes[i+1][0] - sorted_notes[i][0]) / ticks_per_beat
            gaps.append(gap)
        
        if not gaps:
            return self._create_acceptable_metric("Note Spacing", MetricCategory.HUMANIZATION, 0.6)
        
        avg_gap = statistics.mean(gaps)
        
        # Good average gap: 0.25 to 1.0 beats
        if 0.25 <= avg_gap <= 1.0:
            score = 1.0
            level = QualityLevel.EXCELLENT
            details = f"Good note spacing ({avg_gap:.2f} beats avg)"
            suggestions = []
        elif avg_gap < 0.25:
            score = max(0.5, avg_gap / 0.25)
            level = self._score_to_level(score)
            details = f"Notes very close ({avg_gap:.2f} beats avg)"
            suggestions = ["Consider spreading notes out more"]
        else:
            score = max(0.6, 1.0 - (avg_gap - 1.0) / 2.0)
            level = self._score_to_level(score)
            details = f"Notes far apart ({avg_gap:.2f} beats avg)"
            suggestions = ["Consider tighter note spacing"]
        
        return MetricResult(
            name="Note Spacing",
            category=MetricCategory.HUMANIZATION,
            value=avg_gap,
            normalized_score=score,
            quality_level=level,
            threshold_min=0.25,
            threshold_max=1.0,
            details=details,
            suggestions=suggestions
        )
    
    # Music Theory Metrics
    
    def analyze_scale_adherence(self, notes, key, scale) -> MetricResult:
        """Calculate percentage of notes in scale."""
        if not notes:
            return self._create_failing_metric("Scale Adherence", MetricCategory.MUSIC_THEORY)
        
        # Get root note number
        root = NOTE_TO_NUM.get(key.upper(), 0)
        
        # Get scale intervals
        scale_intervals = SCALES.get(scale.lower(), SCALES["major"])
        
        # Create set of all valid MIDI notes in this scale
        valid_notes = set()
        for octave in range(11):
            for interval in scale_intervals:
                valid_notes.add((root + interval + octave * 12) % 12)
        
        # Check each note
        pitches = [n[2] for n in notes]
        in_scale = sum(1 for p in pitches if (p % 12) in valid_notes)
        adherence = in_scale / len(pitches)
        
        if adherence >= 0.9:
            score = 1.0
            level = QualityLevel.EXCELLENT
            details = f"{adherence:.1%} notes in {key} {scale}"
            suggestions = []
        elif adherence >= 0.7:
            score = 0.8
            level = QualityLevel.GOOD
            details = f"{adherence:.1%} notes in {key} {scale}"
            suggestions = ["Some chromatic notes detected"]
        elif adherence >= 0.5:
            score = 0.6
            level = QualityLevel.ACCEPTABLE
            details = f"{adherence:.1%} notes in {key} {scale}"
            suggestions = ["Consider staying closer to the scale"]
        else:
            score = 0.3
            level = QualityLevel.POOR
            details = f"Only {adherence:.1%} notes in {key} {scale}"
            suggestions = ["Many notes outside the scale - check key/scale settings"]
        
        return MetricResult(
            name="Scale Adherence",
            category=MetricCategory.MUSIC_THEORY,
            value=adherence,
            normalized_score=score,
            quality_level=level,
            threshold_min=0.7,
            threshold_max=1.0,
            details=details,
            suggestions=suggestions
        )
    
    def analyze_pitch_variety(self, notes) -> MetricResult:
        """Analyze pitch variety."""
        if not notes:
            return self._create_failing_metric("Pitch Variety", MetricCategory.MUSIC_THEORY)
        
        pitches = [n[2] for n in notes]
        unique_pitches = len(set(pitches))
        variety_ratio = unique_pitches / len(pitches)
        
        if variety_ratio >= 0.4:
            score = 1.0
            level = QualityLevel.EXCELLENT
            details = f"{unique_pitches} unique pitches ({variety_ratio:.1%})"
            suggestions = []
        elif variety_ratio >= 0.25:
            score = 0.7
            level = QualityLevel.GOOD
            details = f"{unique_pitches} unique pitches ({variety_ratio:.1%})"
            suggestions = []
        else:
            score = 0.5
            level = QualityLevel.ACCEPTABLE
            details = f"Limited variety: {unique_pitches} unique pitches"
            suggestions = ["Add more pitch variety"]
        
        return MetricResult(
            name="Pitch Variety",
            category=MetricCategory.MUSIC_THEORY,
            value=variety_ratio,
            normalized_score=score,
            quality_level=level,
            threshold_min=0.25,
            threshold_max=1.0,
            details=details,
            suggestions=suggestions
        )
    
    def analyze_interval_distribution(self, notes) -> MetricResult:
        """Analyze melodic interval distribution."""
        if len(notes) < 2:
            return self._create_acceptable_metric("Interval Distribution", MetricCategory.MUSIC_THEORY, 0.7)
        
        sorted_notes = sorted(notes, key=lambda n: n[0])
        intervals = []
        for i in range(len(sorted_notes) - 1):
            interval = abs(sorted_notes[i+1][2] - sorted_notes[i][2])
            intervals.append(interval)
        
        if not intervals:
            return self._create_acceptable_metric("Interval Distribution", MetricCategory.MUSIC_THEORY, 0.7)
        
        avg_interval = statistics.mean(intervals)
        max_interval = max(intervals)
        
        # Good melodic motion: mostly steps and small leaps
        small_intervals = sum(1 for i in intervals if i <= 4)
        small_ratio = small_intervals / len(intervals)
        
        if small_ratio >= 0.6 and max_interval <= 12:
            score = 1.0
            level = QualityLevel.EXCELLENT
            details = f"Smooth melodic motion ({small_ratio:.1%} small intervals)"
            suggestions = []
        elif small_ratio >= 0.4:
            score = 0.7
            level = QualityLevel.GOOD
            details = f"Good melodic motion ({small_ratio:.1%} small intervals)"
            suggestions = []
        else:
            score = 0.5
            level = QualityLevel.ACCEPTABLE
            details = f"Large leaps ({small_ratio:.1%} small intervals)"
            suggestions = ["Consider using more stepwise motion"]
        
        return MetricResult(
            name="Interval Distribution",
            category=MetricCategory.MUSIC_THEORY,
            value=small_ratio,
            normalized_score=score,
            quality_level=level,
            threshold_min=0.4,
            threshold_max=1.0,
            details=details,
            suggestions=suggestions
        )
    
    def analyze_melodic_contour(self, notes) -> MetricResult:
        """Analyze melodic contour shape."""
        if len(notes) < 3:
            return self._create_acceptable_metric("Melodic Contour", MetricCategory.MUSIC_THEORY, 0.7)
        
        sorted_notes = sorted(notes, key=lambda n: n[0])
        pitches = [n[2] for n in sorted_notes]
        
        # Analyze direction changes
        directions = []
        for i in range(len(pitches) - 1):
            if pitches[i+1] > pitches[i]:
                directions.append(1)
            elif pitches[i+1] < pitches[i]:
                directions.append(-1)
            else:
                directions.append(0)
        
        if not directions:
            return self._create_acceptable_metric("Melodic Contour", MetricCategory.MUSIC_THEORY, 0.7)
        
        # Count direction changes
        changes = 0
        for i in range(len(directions) - 1):
            if directions[i] != 0 and directions[i+1] != 0 and directions[i] != directions[i+1]:
                changes += 1
        
        change_rate = changes / (len(directions) - 1) if len(directions) > 1 else 0
        
        # Good contour has some direction changes but not too many
        if 0.2 <= change_rate <= 0.5:
            score = 1.0
            level = QualityLevel.EXCELLENT
            details = f"Good melodic contour ({change_rate:.2f} change rate)"
            suggestions = []
        elif change_rate < 0.2:
            score = 0.7
            level = QualityLevel.GOOD
            details = f"Linear contour ({change_rate:.2f} change rate)"
            suggestions = ["Add more melodic variety"]
        else:
            score = 0.6
            level = QualityLevel.ACCEPTABLE
            details = f"Irregular contour ({change_rate:.2f} change rate)"
            suggestions = ["Consider smoother melodic lines"]
        
        return MetricResult(
            name="Melodic Contour",
            category=MetricCategory.MUSIC_THEORY,
            value=change_rate,
            normalized_score=score,
            quality_level=level,
            threshold_min=0.2,
            threshold_max=0.5,
            details=details,
            suggestions=suggestions
        )
    
    # Genre Conformance Metrics
    
    def analyze_tempo_conformance(self, tempo, genre) -> MetricResult:
        """Check tempo within genre norms."""
        profile = self.genre_profiles.get(genre, self.genre_profiles["pop"])
        min_tempo, max_tempo = profile["tempo_range"]
        
        if min_tempo <= tempo <= max_tempo:
            score = 1.0
            level = QualityLevel.EXCELLENT
            details = f"Tempo {tempo} BPM fits {genre} ({min_tempo}-{max_tempo})"
            suggestions = []
        elif tempo < min_tempo:
            score = max(0.4, tempo / min_tempo)
            level = self._score_to_level(score)
            details = f"Tempo {tempo} BPM slow for {genre}"
            suggestions = [f"Consider tempo between {min_tempo}-{max_tempo} BPM for {genre}"]
        else:
            score = max(0.4, min_tempo / tempo)
            level = self._score_to_level(score)
            details = f"Tempo {tempo} BPM fast for {genre}"
            suggestions = [f"Consider tempo between {min_tempo}-{max_tempo} BPM for {genre}"]
        
        return MetricResult(
            name="Tempo Conformance",
            category=MetricCategory.GENRE_CONFORMANCE,
            value=tempo,
            normalized_score=score,
            quality_level=level,
            threshold_min=min_tempo,
            threshold_max=max_tempo,
            details=details,
            suggestions=suggestions
        )
    
    def analyze_genre_velocity_profile(self, notes, genre) -> MetricResult:
        """Analyze if velocity profile matches genre expectations."""
        if not notes:
            return self._create_failing_metric("Genre Velocity Profile", MetricCategory.GENRE_CONFORMANCE)
        
        velocities = [n[3] for n in notes]
        
        if len(velocities) > 1:
            cv = statistics.stdev(velocities) / statistics.mean(velocities)
        else:
            cv = 0
        
        profile = self.genre_profiles.get(genre, self.genre_profiles["pop"])
        min_variance = profile.get("velocity_variance_min", 0.06)
        
        if cv >= min_variance:
            score = 1.0
            level = QualityLevel.EXCELLENT
            details = f"Velocity profile fits {genre} (CV={cv:.3f})"
            suggestions = []
        else:
            score = max(0.5, cv / min_variance)
            level = self._score_to_level(score)
            details = f"Velocity too uniform for {genre} (CV={cv:.3f})"
            suggestions = [f"Increase velocity variation for {genre} (min CV={min_variance:.2f})"]
        
        return MetricResult(
            name="Genre Velocity Profile",
            category=MetricCategory.GENRE_CONFORMANCE,
            value=cv,
            normalized_score=score,
            quality_level=level,
            threshold_min=min_variance,
            threshold_max=1.0,
            details=details,
            suggestions=suggestions
        )
    
    # Structure Metrics
    
    def analyze_phrase_structure(self, notes, ticks_per_beat) -> MetricResult:
        """Analyze phrase structure and boundaries."""
        if not notes:
            return self._create_failing_metric("Phrase Structure", MetricCategory.STRUCTURE)
        
        # Look for phrase boundaries (gaps > 1 beat)
        sorted_notes = sorted(notes, key=lambda n: n[0])
        gaps = []
        for i in range(len(sorted_notes) - 1):
            gap = (sorted_notes[i+1][0] - (sorted_notes[i][0] + sorted_notes[i][1])) / ticks_per_beat
            if gap > 0.5:
                gaps.append(gap)
        
        phrase_count = len([g for g in gaps if g >= 1.0]) + 1
        
        if phrase_count >= 2:
            score = 1.0
            level = QualityLevel.EXCELLENT
            details = f"{phrase_count} phrases detected"
            suggestions = []
        elif phrase_count == 1:
            score = 0.7
            level = QualityLevel.GOOD
            details = "Single continuous phrase"
            suggestions = ["Consider adding phrase boundaries for structure"]
        else:
            score = 0.6
            level = QualityLevel.ACCEPTABLE
            details = "No clear phrase structure"
            suggestions = []
        
        return MetricResult(
            name="Phrase Structure",
            category=MetricCategory.STRUCTURE,
            value=phrase_count,
            normalized_score=score,
            quality_level=level,
            threshold_min=1,
            threshold_max=8,
            details=details,
            suggestions=suggestions
        )

    def analyze_motif_coherence(self, notes, ticks_per_beat) -> MetricResult:
        """Analyze whether there is a recurring motif-like shape.

        This is intentionally heuristic and note-list only: it looks for repeating
        interval+rhythm n-grams in the monophonic projection of the sequence.
        """
        if len(notes) < 10:
            return self._create_acceptable_metric("Motif Coherence", MetricCategory.STRUCTURE, 0.7)

        # Project chords to a monophonic line (highest note at each start time)
        by_start: Dict[int, List[Tuple[int, int]]] = {}
        for start_tick, _dur, pitch, velocity in notes:
            by_start.setdefault(int(start_tick), []).append((int(pitch), int(velocity)))

        events = []
        for start_tick in sorted(by_start.keys()):
            pitches = [p for p, _v in by_start[start_tick]]
            events.append((start_tick, max(pitches)))

        if len(events) < 10:
            return self._create_acceptable_metric("Motif Coherence", MetricCategory.STRUCTURE, 0.7)

        # Build interval+rhythm pairs
        pairs = []
        for i in range(1, len(events)):
            prev_start, prev_pitch = events[i - 1]
            cur_start, cur_pitch = events[i]

            dp = int(cur_pitch - prev_pitch)
            dp = max(-12, min(12, dp))

            dt_beats = (cur_start - prev_start) / max(float(ticks_per_beat), 1.0)
            # Quantize to 16th-note grid for robustness
            dt_q = round(dt_beats * 4) / 4.0
            pairs.append((dp, dt_q))

        gram_len = 4
        if len(pairs) < gram_len + 1:
            return self._create_acceptable_metric("Motif Coherence", MetricCategory.STRUCTURE, 0.7)

        grams: Dict[Tuple[Tuple[int, float], ...], int] = {}
        for i in range(0, len(pairs) - gram_len + 1):
            gram = tuple(pairs[i:i + gram_len])
            grams[gram] = grams.get(gram, 0) + 1

        best_count = max(grams.values()) if grams else 1
        repeating = best_count >= 2

        # Approximate how much of the line is covered by the most frequent gram
        approx_coverage = min(1.0, (best_count * (gram_len + 1)) / max(len(events), 1))

        if not repeating or approx_coverage < 0.25:
            score = max(0.3, approx_coverage)
            level = self._score_to_level(score)
            details = f"Weak motif signal (top pattern coverage ≈ {approx_coverage:.2f})"
            suggestions = [
                "Introduce a short motif and repeat it with variation (sequence/inversion/rhythm shift)",
                "If available, enable motif-driven melody or increase motif density",
            ]
        elif approx_coverage <= 0.75:
            score = 1.0
            level = QualityLevel.EXCELLENT
            details = f"Good motif coherence (top pattern coverage ≈ {approx_coverage:.2f})"
            suggestions = []
        else:
            score = 0.75
            level = QualityLevel.GOOD
            details = f"Very strong repetition (top pattern coverage ≈ {approx_coverage:.2f})"
            suggestions = ["Consider adding variation to avoid feeling looped"]

        return MetricResult(
            name="Motif Coherence",
            category=MetricCategory.STRUCTURE,
            value=approx_coverage,
            normalized_score=score,
            quality_level=level,
            threshold_min=0.25,
            threshold_max=0.75,
            details=details,
            suggestions=suggestions
        )
    
    def analyze_rhythmic_consistency(self, notes, ticks_per_beat) -> MetricResult:
        """Analyze rhythmic consistency."""
        if len(notes) < 3:
            return self._create_acceptable_metric("Rhythmic Consistency", MetricCategory.STRUCTURE, 0.7)
        
        sorted_notes = sorted(notes, key=lambda n: n[0])
        gaps = []
        for i in range(len(sorted_notes) - 1):
            gap = sorted_notes[i+1][0] - sorted_notes[i][0]
            gaps.append(gap)
        
        if not gaps:
            return self._create_acceptable_metric("Rhythmic Consistency", MetricCategory.STRUCTURE, 0.7)
        
        # Check for consistent rhythmic patterns
        if len(gaps) > 1:
            std_dev = statistics.stdev(gaps) / ticks_per_beat
        else:
            std_dev = 0
        
        # Lower std dev = more consistent
        if std_dev <= 0.5:
            score = 1.0
            level = QualityLevel.EXCELLENT
            details = f"Consistent rhythm (σ={std_dev:.2f} beats)"
            suggestions = []
        elif std_dev <= 1.0:
            score = 0.7
            level = QualityLevel.GOOD
            details = f"Moderate rhythmic variety (σ={std_dev:.2f} beats)"
            suggestions = []
        else:
            score = 0.5
            level = QualityLevel.ACCEPTABLE
            details = f"Irregular rhythm (σ={std_dev:.2f} beats)"
            suggestions = ["Consider more consistent rhythmic patterns"]
        
        return MetricResult(
            name="Rhythmic Consistency",
            category=MetricCategory.STRUCTURE,
            value=std_dev,
            normalized_score=score,
            quality_level=level,
            threshold_min=0.0,
            threshold_max=1.0,
            details=details,
            suggestions=suggestions
        )
    
    # Dynamics Metrics
    
    def analyze_dynamic_range(self, notes) -> MetricResult:
        """Analyze dynamic range."""
        if not notes:
            return self._create_failing_metric("Dynamic Range", MetricCategory.DYNAMICS)
        
        velocities = [n[3] for n in notes]
        vel_range = max(velocities) - min(velocities)
        
        # Good dynamic range: 30-80
        if 30 <= vel_range <= 80:
            score = 1.0
            level = QualityLevel.EXCELLENT
            details = f"Good dynamic range ({vel_range} MIDI units)"
            suggestions = []
        elif vel_range < 30:
            score = max(0.4, vel_range / 30)
            level = self._score_to_level(score)
            details = f"Limited dynamics ({vel_range} MIDI units)"
            suggestions = ["Increase dynamic range for more expression"]
        else:
            score = 0.8
            level = QualityLevel.GOOD
            details = f"Wide dynamic range ({vel_range} MIDI units)"
            suggestions = []
        
        return MetricResult(
            name="Dynamic Range",
            category=MetricCategory.DYNAMICS,
            value=vel_range,
            normalized_score=score,
            quality_level=level,
            threshold_min=30,
            threshold_max=80,
            details=details,
            suggestions=suggestions
        )
    
    def analyze_velocity_progression(self, notes) -> MetricResult:
        """Analyze velocity progression patterns."""
        if len(notes) < 4:
            return self._create_acceptable_metric("Velocity Progression", MetricCategory.DYNAMICS, 0.7)
        
        sorted_notes = sorted(notes, key=lambda n: n[0])
        velocities = [n[3] for n in sorted_notes]
        
        # Look for trends (crescendo/decrescendo)
        first_half = velocities[:len(velocities)//2]
        second_half = velocities[len(velocities)//2:]
        
        avg_first = statistics.mean(first_half)
        avg_second = statistics.mean(second_half)
        
        trend = abs(avg_second - avg_first)
        
        if trend >= 10:
            score = 1.0
            level = QualityLevel.EXCELLENT
            direction = "crescendo" if avg_second > avg_first else "decrescendo"
            details = f"Dynamic progression ({direction}, Δ={trend:.1f})"
            suggestions = []
        elif trend >= 5:
            score = 0.8
            level = QualityLevel.GOOD
            details = f"Subtle dynamic change (Δ={trend:.1f})"
            suggestions = []
        else:
            score = 0.6
            level = QualityLevel.ACCEPTABLE
            details = f"Flat dynamics (Δ={trend:.1f})"
            suggestions = ["Add crescendo or decrescendo for musical shape"]
        
        return MetricResult(
            name="Velocity Progression",
            category=MetricCategory.DYNAMICS,
            value=trend,
            normalized_score=score,
            quality_level=level,
            threshold_min=5,
            threshold_max=50,
            details=details,
            suggestions=suggestions
        )
    
    def analyze_accent_patterns(self, notes) -> MetricResult:
        """Analyze accent patterns in velocities."""
        if len(notes) < 4:
            return self._create_acceptable_metric("Accent Patterns", MetricCategory.DYNAMICS, 0.7)
        
        velocities = [n[3] for n in notes]
        mean_vel = statistics.mean(velocities)
        
        # Count accented notes (significantly above average)
        accents = sum(1 for v in velocities if v > mean_vel + 10)
        accent_ratio = accents / len(velocities)
        
        if 0.15 <= accent_ratio <= 0.35:
            score = 1.0
            level = QualityLevel.EXCELLENT
            details = f"Good accent pattern ({accent_ratio:.1%} accented)"
            suggestions = []
        elif accent_ratio < 0.15:
            score = 0.7
            level = QualityLevel.GOOD
            details = f"Few accents ({accent_ratio:.1%})"
            suggestions = ["Add more accented notes for emphasis"]
        else:
            score = 0.6
            level = QualityLevel.ACCEPTABLE
            details = f"Many accents ({accent_ratio:.1%})"
            suggestions = ["Reduce accents for better contrast"]
        
        return MetricResult(
            name="Accent Patterns",
            category=MetricCategory.DYNAMICS,
            value=accent_ratio,
            normalized_score=score,
            quality_level=level,
            threshold_min=0.15,
            threshold_max=0.35,
            details=details,
            suggestions=suggestions
        )
    
    # Rhythm Metrics
    
    def analyze_voice_leading_cost(self, notes, key="C") -> MetricResult:
        """Analyse voice-leading cost using the VLC critic.

        Extracts voicings by grouping simultaneous notes (same start tick),
        then delegates to ``compute_vlc``.

        Args:
            notes: List of (start_tick, duration_ticks, pitch, velocity) tuples.
            key: Root note (reserved for future key-aware VLC weighting).

        Returns:
            MetricResult with category MUSIC_THEORY.
        """
        if not _HAS_CRITICS:
            return self._create_acceptable_metric(
                "Voice Leading Cost (VLC)", MetricCategory.MUSIC_THEORY, 0.7
            )

        # Group simultaneous notes by tick to extract voicings.
        # Filter to chord register (MIDI 48-96 / C3-C7) to exclude
        # drum hits and bass notes that inflate voice-leading cost.
        from collections import defaultdict
        tick_groups: Dict[int, List[int]] = defaultdict(list)
        for start_tick, _dur, pitch, _vel in notes:
            p = int(pitch)
            if 48 <= p <= 96:
                tick_groups[int(start_tick)].append(p)

        voicings = [
            sorted(tick_groups[t])
            for t in sorted(tick_groups)
            if len(tick_groups[t]) >= 2
        ]

        if len(voicings) < 2:
            return self._create_acceptable_metric(
                "Voice Leading Cost (VLC)", MetricCategory.MUSIC_THEORY, 0.7
            )

        result = compute_vlc(voicings)
        vlc = result.value

        # Stepped threshold mapping
        if vlc < 1.5:
            normalized, level = 1.0, QualityLevel.EXCELLENT
        elif vlc < 3.0:
            normalized, level = 0.8, QualityLevel.GOOD
        elif vlc < 5.0:
            normalized, level = 0.6, QualityLevel.ACCEPTABLE
        else:
            normalized, level = 0.3, QualityLevel.POOR

        suggestions: List[str] = []
        if not result.passed:
            suggestions.append("Reduce voice-leading jumps — use closer voicings.")

        return MetricResult(
            name="Voice Leading Cost (VLC)",
            category=MetricCategory.MUSIC_THEORY,
            value=vlc,
            normalized_score=normalized,
            quality_level=level,
            threshold_min=0.0,
            threshold_max=result.threshold,
            details=result.details,
            suggestions=suggestions,
        )
    
    def analyze_bass_kick_alignment(self, notes, reference_notes=None) -> MetricResult:
        """Analyse bass-kick alignment using the BKAS critic.

        Extracts bass notes (pitch < 60 MIDI) from *notes* and kick event
        ticks (MIDI note 36) from *reference_notes*.

        Args:
            notes: List of (start_tick, duration_ticks, pitch, velocity) tuples.
            reference_notes: Optional list of note tuples containing drum events.
                Kick hits are identified as MIDI pitch 36.

        Returns:
            MetricResult with category RHYTHM.
        """
        if not _HAS_CRITICS:
            return self._create_acceptable_metric(
                "Bass-Kick Alignment (BKAS)", MetricCategory.RHYTHM, 0.7
            )

        # Extract bass notes (pitch < 60)
        bass_notes = [{"tick": int(n[0])} for n in notes if int(n[2]) < 60]

        # Extract kick ticks (MIDI 36) from reference_notes
        kick_ticks: List[int] = []
        if reference_notes:
            kick_ticks = [int(n[0]) for n in reference_notes if int(n[2]) == 36]

        if not bass_notes or not kick_ticks:
            return self._create_acceptable_metric(
                "Bass-Kick Alignment (BKAS)", MetricCategory.RHYTHM, 0.7
            )

        result = compute_bkas(bass_notes, kick_ticks, tolerance_ticks=60)
        bkas = result.value

        # Stepped threshold mapping
        if bkas >= 0.85:
            normalized, level = 1.0, QualityLevel.EXCELLENT
        elif bkas >= 0.70:
            normalized, level = 0.8, QualityLevel.GOOD
        elif bkas >= 0.50:
            normalized, level = 0.6, QualityLevel.ACCEPTABLE
        else:
            normalized, level = 0.3, QualityLevel.POOR

        suggestions: List[str] = []
        if not result.passed:
            suggestions.append(
                "Tighten bass-kick pocket — align bass onsets with kick hits."
            )

        return MetricResult(
            name="Bass-Kick Alignment (BKAS)",
            category=MetricCategory.RHYTHM,
            value=bkas,
            normalized_score=normalized,
            quality_level=level,
            threshold_min=result.threshold,
            threshold_max=1.0,
            details=result.details,
            suggestions=suggestions,
        )
    
    def analyze_arrangement_density(
        self, notes, tension_curve=None, ticks_per_beat: int = 480
    ) -> MetricResult:
        """Analyse arrangement density correlation using the ADC critic.

        Computes note density per bar from *notes*, then correlates with
        *tension_curve*.  Using per-bar granularity captures section-level
        density changes (intro=sparse, chorus=dense) that per-beat
        analysis misses since performers repeat patterns consistently
        within bars.

        If no curve is supplied a simple ascending ramp is synthesised.

        Args:
            notes: List of (start_tick, duration_ticks, pitch, velocity) tuples.
            tension_curve: Optional per-bar tension values (0-1).
            ticks_per_beat: MIDI ticks per beat (default 480).

        Returns:
            MetricResult with category STRUCTURE.
        """
        if not _HAS_CRITICS:
            return self._create_acceptable_metric(
                "Arrangement Density Curve (ADC)", MetricCategory.STRUCTURE, 0.7
            )

        if not notes:
            return self._create_acceptable_metric(
                "Arrangement Density Curve (ADC)", MetricCategory.STRUCTURE, 0.7
            )

        # Compute note density per BAR (not per beat) for meaningful
        # section-level correlation.  Songs vary density across sections
        # (intro→verse→chorus) not within individual beats.
        ticks_per_bar = ticks_per_beat * 4  # assume 4/4
        from collections import Counter
        bar_counts: Dict[int, int] = Counter()
        for start_tick, _dur, _pitch, _vel in notes:
            bar = int(start_tick) // max(ticks_per_bar, 1)
            bar_counts[bar] += 1

        if not bar_counts:
            return self._create_acceptable_metric(
                "Arrangement Density Curve (ADC)", MetricCategory.STRUCTURE, 0.7
            )

        max_bar = max(bar_counts)
        density_per_bar = [float(bar_counts.get(b, 0)) for b in range(max_bar + 1)]

        # When an explicit tension curve is provided, correlate with it.
        # Otherwise measure density *variation* — a well-arranged piece
        # has dynamic density (sparse intros, dense choruses) rather
        # than flat density throughout.  The coefficient of variation
        # (std/mean) captures this independent of any assumed shape.
        if tension_curve is not None and len(tension_curve) >= 2 and len(density_per_bar) >= 2:
            result = compute_adc(tension_curve, density_per_bar)
            adc = result.value
            details = result.details
        else:
            # Density-variation fallback (no tension curve available)
            import math
            n = len(density_per_bar)
            if n < 2:
                return self._create_acceptable_metric(
                    "Arrangement Density Curve (ADC)", MetricCategory.STRUCTURE, 0.7
                )
            mean_d = sum(density_per_bar) / n
            if mean_d < 0.01:
                return self._create_acceptable_metric(
                    "Arrangement Density Curve (ADC)", MetricCategory.STRUCTURE, 0.7
                )
            var = sum((d - mean_d) ** 2 for d in density_per_bar) / n
            std_d = math.sqrt(var)
            cv = std_d / mean_d  # coefficient of variation

            # CV > 0.2 → very dynamic arrangement → EXCELLENT
            # CV > 0.12 → good variation → GOOD
            # CV > 0.06 → some variation → ACCEPTABLE  
            # CV <= 0.06 → flat/monotonous
            adc = min(cv / 0.2, 1.0)  # normalise to 0-1
            details = (
                f"Density variation (CV): {cv:.3f} over {n} bars. "
                f"{'Dynamic arrangement.' if cv > 0.3 else 'Consider varying density across sections.'}"
            )

        # Stepped threshold mapping
        if adc >= 0.8:
            normalized, level = 1.0, QualityLevel.EXCELLENT
        elif adc >= 0.5:
            normalized, level = 0.8, QualityLevel.GOOD
        elif adc >= 0.25:
            normalized, level = 0.6, QualityLevel.ACCEPTABLE
        else:
            normalized, level = 0.3, QualityLevel.POOR

        suggestions: List[str] = []
        if adc < 0.6:
            suggestions.append(
                "Note density should track tension — add notes in high-energy "
                "sections, thin out in calm sections."
            )

        return MetricResult(
            name="Arrangement Density Curve (ADC)",
            category=MetricCategory.STRUCTURE,
            value=adc,
            normalized_score=normalized,
            quality_level=level,
            threshold_min=0.4,
            threshold_max=1.0,
            details=details,
            suggestions=suggestions,
        )
    
    def analyze_rhythmic_complexity(self, notes, ticks_per_beat) -> MetricResult:
        """Analyze rhythmic complexity."""
        if not notes:
            return self._create_failing_metric("Rhythmic Complexity", MetricCategory.RHYTHM)
        
        # Quantize to 16th notes and count unique patterns
        sorted_notes = sorted(notes, key=lambda n: n[0])
        
        # Create 16th note grid
        max_tick = max(n[0] + n[1] for n in sorted_notes)
        grid_size = int(max_tick / (ticks_per_beat / 4)) + 1
        grid = [0] * grid_size
        
        for start, dur, pitch, vel in sorted_notes:
            grid_pos = int(start / (ticks_per_beat / 4))
            if grid_pos < grid_size:
                grid[grid_pos] = 1
        
        # Count pattern changes
        pattern_changes = sum(1 for i in range(len(grid)-1) if grid[i] != grid[i+1])
        complexity = pattern_changes / len(grid) if grid else 0
        
        if 0.3 <= complexity <= 0.6:
            score = 1.0
            level = QualityLevel.EXCELLENT
            details = f"Good rhythmic complexity ({complexity:.2f})"
            suggestions = []
        elif complexity < 0.3:
            score = 0.7
            level = QualityLevel.GOOD
            details = f"Simple rhythm ({complexity:.2f})"
            suggestions = ["Consider adding more rhythmic interest"]
        else:
            score = 0.6
            level = QualityLevel.ACCEPTABLE
            details = f"Complex rhythm ({complexity:.2f})"
            suggestions = ["Consider simplifying for clarity"]
        
        return MetricResult(
            name="Rhythmic Complexity",
            category=MetricCategory.RHYTHM,
            value=complexity,
            normalized_score=score,
            quality_level=level,
            threshold_min=0.3,
            threshold_max=0.6,
            details=details,
            suggestions=suggestions
        )
    
    def analyze_syncopation(self, notes, ticks_per_beat) -> MetricResult:
        """Analyze syncopation level."""
        if not notes:
            return self._create_failing_metric("Syncopation", MetricCategory.RHYTHM)
        
        # Count notes that start off-beat
        off_beat_count = 0
        for start, dur, pitch, vel in notes:
            beat_pos = (start % ticks_per_beat) / ticks_per_beat
            # Check if not on major beat divisions (0, 0.25, 0.5, 0.75)
            is_syncopated = not any(abs(beat_pos - div) < 0.05 for div in [0, 0.25, 0.5, 0.75])
            if is_syncopated:
                off_beat_count += 1
        
        syncopation_ratio = off_beat_count / len(notes)
        
        if 0.1 <= syncopation_ratio <= 0.4:
            score = 1.0
            level = QualityLevel.EXCELLENT
            details = f"Good syncopation ({syncopation_ratio:.1%})"
            suggestions = []
        elif syncopation_ratio < 0.1:
            score = 0.7
            level = QualityLevel.GOOD
            details = f"Low syncopation ({syncopation_ratio:.1%})"
            suggestions = ["Add off-beat notes for groove"]
        else:
            score = 0.7
            level = QualityLevel.GOOD
            details = f"High syncopation ({syncopation_ratio:.1%})"
            suggestions = []
        
        return MetricResult(
            name="Syncopation",
            category=MetricCategory.RHYTHM,
            value=syncopation_ratio,
            normalized_score=score,
            quality_level=level,
            threshold_min=0.1,
            threshold_max=0.4,
            details=details,
            suggestions=suggestions
        )
    
    def analyze_note_duration_variety(self, notes, ticks_per_beat) -> MetricResult:
        """Analyze variety in note durations."""
        if not notes:
            return self._create_failing_metric("Note Duration Variety", MetricCategory.RHYTHM)
        
        durations_beats = [n[1] / ticks_per_beat for n in notes]
        
        if len(durations_beats) > 1:
            cv = statistics.stdev(durations_beats) / statistics.mean(durations_beats)
        else:
            cv = 0
        
        if 0.3 <= cv <= 0.8:
            score = 1.0
            level = QualityLevel.EXCELLENT
            details = f"Good duration variety (CV={cv:.2f})"
            suggestions = []
        elif cv < 0.3:
            score = max(0.5, cv / 0.3)
            level = self._score_to_level(score)
            details = f"Uniform durations (CV={cv:.2f})"
            suggestions = ["Add variety in note lengths"]
        else:
            score = 0.7
            level = QualityLevel.GOOD
            details = f"Varied durations (CV={cv:.2f})"
            suggestions = []
        
        return MetricResult(
            name="Note Duration Variety",
            category=MetricCategory.RHYTHM,
            value=cv,
            normalized_score=score,
            quality_level=level,
            threshold_min=0.3,
            threshold_max=0.8,
            details=details,
            suggestions=suggestions
        )
    
    # Helper Methods
    
    def _load_genre_profiles(self) -> Dict:
        """Load genre-specific thresholds."""
        return GENRE_QUALITY_PROFILES
    
    def _calculate_overall_score(self, metrics: List[MetricResult]) -> float:
        """Calculate weighted overall score."""
        if not metrics:
            return 0.0
        
        # Weight by category
        category_weights = {
            MetricCategory.MIDI_QUALITY: 1.5,
            MetricCategory.MUSIC_THEORY: 1.3,
            MetricCategory.HUMANIZATION: 1.2,
            MetricCategory.GENRE_CONFORMANCE: 1.0,
            MetricCategory.STRUCTURE: 0.8,
            MetricCategory.DYNAMICS: 1.0,
            MetricCategory.RHYTHM: 1.0,
        }
        
        total_weighted_score = 0.0
        total_weight = 0.0
        
        for metric in metrics:
            weight = category_weights.get(metric.category, 1.0)
            total_weighted_score += metric.normalized_score * weight
            total_weight += weight
        
        return total_weighted_score / total_weight if total_weight > 0 else 0.0
    
    def _calculate_category_scores(self, metrics: List[MetricResult]) -> Dict[MetricCategory, float]:
        """Calculate average score per category."""
        category_scores = {}
        category_counts = {}
        
        for metric in metrics:
            if metric.category not in category_scores:
                category_scores[metric.category] = 0.0
                category_counts[metric.category] = 0
            
            category_scores[metric.category] += metric.normalized_score
            category_counts[metric.category] += 1
        
        return {
            cat: score / category_counts[cat]
            for cat, score in category_scores.items()
        }
    
    def _generate_summary(self, overall_score: float, overall_level: QualityLevel, 
                         metrics: List[MetricResult]) -> str:
        """Generate summary text."""
        failing_metrics = [m for m in metrics if m.quality_level == QualityLevel.FAILING]
        poor_metrics = [m for m in metrics if m.quality_level == QualityLevel.POOR]
        
        summary = f"Overall quality: {overall_level.value} ({overall_score:.1%}). "
        
        if failing_metrics:
            summary += f"{len(failing_metrics)} critical issues. "
        if poor_metrics:
            summary += f"{len(poor_metrics)} areas need improvement. "
        
        if overall_score >= 0.9:
            summary += "Excellent quality across all metrics!"
        elif overall_score >= 0.7:
            summary += "Good quality with minor areas for improvement."
        elif overall_score >= 0.5:
            summary += "Acceptable quality but several areas need work."
        else:
            summary += "Significant improvements needed."
        
        return summary
    
    def _generate_recommendations(self, metrics: List[MetricResult]) -> List[str]:
        """Generate actionable recommendations."""
        recommendations = []
        
        # Collect all suggestions from metrics
        for metric in metrics:
            if metric.suggestions and metric.normalized_score < 0.8:
                for suggestion in metric.suggestions:
                    if suggestion not in recommendations:
                        recommendations.append(f"{metric.name}: {suggestion}")
        
        # Prioritize by score
        metric_priority = sorted(
            [(m.normalized_score, m) for m in metrics if m.suggestions],
            key=lambda x: x[0]
        )
        
        priority_recs = []
        for score, metric in metric_priority[:5]:
            if metric.suggestions:
                priority_recs.append(f"Priority - {metric.name}: {metric.suggestions[0]}")
        
        return priority_recs if priority_recs else recommendations[:10]
    
    def _score_to_level(self, score: float) -> QualityLevel:
        """Convert numeric score to quality level."""
        if score >= 0.9:
            return QualityLevel.EXCELLENT
        elif score >= 0.7:
            return QualityLevel.GOOD
        elif score >= 0.5:
            return QualityLevel.ACCEPTABLE
        elif score >= 0.3:
            return QualityLevel.POOR
        else:
            return QualityLevel.FAILING
    
    def _create_failing_metric(self, name: str, category: MetricCategory) -> MetricResult:
        """Create a failing metric result."""
        return MetricResult(
            name=name,
            category=category,
            value=0.0,
            normalized_score=0.0,
            quality_level=QualityLevel.FAILING,
            threshold_min=0.0,
            threshold_max=1.0,
            details="Insufficient data",
            suggestions=["Provide valid note data"]
        )
    
    def _create_acceptable_metric(self, name: str, category: MetricCategory, score: float) -> MetricResult:
        """Create an acceptable metric result."""
        return MetricResult(
            name=name,
            category=category,
            value=score,
            normalized_score=score,
            quality_level=QualityLevel.ACCEPTABLE,
            threshold_min=0.0,
            threshold_max=1.0,
            details="Limited data for analysis",
            suggestions=[]
        )
    
    def _create_empty_report(self) -> ValidationReport:
        """Create empty validation report for no notes."""
        return ValidationReport(
            overall_score=0.0,
            overall_level=QualityLevel.FAILING,
            metrics=[],
            category_scores={},
            passed=False,
            summary="No notes provided for validation",
            recommendations=["Generate notes before validating"]
        )


def quick_validate(notes, genre="pop") -> Tuple[bool, float, List[str]]:
    """Quick validation returning (passed, score, issues).
    
    Args:
        notes: List of (start_tick, duration_ticks, pitch, velocity) tuples
        genre: Music genre for validation
        
    Returns:
        Tuple of (passed, score, list of issue descriptions)
    """
    validator = QualityValidator()
    report = validator.validate(notes, genre=genre)
    
    issues = []
    for metric in report.metrics:
        if metric.normalized_score < 0.6:
            issues.append(f"{metric.name}: {metric.details}")
    
    # Lightweight VLC check when chord notes are present
    if _HAS_CRITICS and notes:
        from collections import defaultdict
        tick_groups: Dict[int, List[int]] = defaultdict(list)
        for start_tick, _dur, pitch, _vel in notes:
            tick_groups[int(start_tick)].append(int(pitch))
        voicings = [
            sorted(tick_groups[t])
            for t in sorted(tick_groups)
            if len(tick_groups[t]) >= 2
        ]
        if len(voicings) >= 2:
            vlc_result = compute_vlc(voicings)
            if not vlc_result.passed:
                issues.append(f"VLC: {vlc_result.details}")
    
    return report.passed, report.overall_score, issues
