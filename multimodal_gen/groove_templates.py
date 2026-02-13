"""
Groove Templates Module - Extract, store, and apply groove patterns

Milestone F: GrooveTemplate v1 - Extract + Apply Non-Destructively

This module provides:
- GrooveTemplate: Reusable groove pattern with timing/velocity offsets
- GrooveExtractor: Extract grooves from audio or MIDI references
- GrooveApplicator: Apply grooves to MIDI patterns non-destructively
- Built-in genre-specific groove presets

A groove template captures the "feel" of a performance:
- Timing offsets per subdivision (how far ahead/behind the grid)
- Velocity offsets per subdivision (accent patterns)
- Swing amount and shuffle metadata
- Can be extracted from references or created manually

Usage:
    # Extract from reference
    extractor = GrooveExtractor()
    template = extractor.extract_from_audio("reference.wav", bpm=95)
    template.save("grooves/my_groove.json")
    
    # Apply to MIDI
    applicator = GrooveApplicator()
    grooved_notes = applicator.apply(notes, template)
    
    # Use presets
    template = get_preset_groove("boom_bap")
"""

from __future__ import annotations
import os
import json
import random
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple, Any, Union
from enum import Enum
from pathlib import Path
import numpy as np
from datetime import datetime, timezone

# Standard MIDI ticks per beat (used for timing calculations)
TICKS_PER_BEAT = 480


class GrooveResolution(Enum):
    """Groove template resolution (subdivision level)."""
    QUARTER = 4      # Quarter notes (4 per bar in 4/4)
    EIGHTH = 8       # Eighth notes
    SIXTEENTH = 16   # Sixteenth notes
    TRIPLET_8 = 12   # Eighth note triplets (12 per bar)
    TRIPLET_16 = 24  # Sixteenth note triplets


@dataclass
class GroovePoint:
    """Single point in a groove template."""
    position: float  # Position in bar (0.0 to 1.0)
    timing_offset_ticks: int  # Timing shift in ticks (+ahead, -behind)
    velocity_offset: int  # Velocity adjustment (-127 to +127)
    accent: float = 1.0  # Accent multiplier (1.0 = normal)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'position': self.position,
            'timing_offset_ticks': self.timing_offset_ticks,
            'velocity_offset': self.velocity_offset,
            'accent': self.accent
        }
    
    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> 'GroovePoint':
        return cls(
            position=d['position'],
            timing_offset_ticks=d['timing_offset_ticks'],
            velocity_offset=d['velocity_offset'],
            accent=d.get('accent', 1.0)
        )


@dataclass
class GrooveTemplate:
    """
    Reusable groove pattern template.
    
    Stores timing and velocity offsets for each subdivision position,
    capturing the "feel" of a performance that can be applied to any pattern.
    
    Attributes:
        name: Human-readable template name
        resolution: Subdivision level (8th, 16th, etc.)
        bars: Number of bars the template spans (usually 1-2)
        points: List of GroovePoint offsets
        swing_amount: Overall swing/shuffle amount (0.0-1.0)
        intensity: How strongly to apply the groove (0.0-1.0)
        source: Where this groove came from (file, preset, extracted)
        genre: Associated genre (optional)
        metadata: Additional metadata
    """
    name: str
    resolution: GrooveResolution = GrooveResolution.SIXTEENTH
    bars: int = 1
    points: List[GroovePoint] = field(default_factory=list)
    swing_amount: float = 0.0
    intensity: float = 1.0
    source: str = "preset"
    genre: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Schema version for compatibility
    SCHEMA_VERSION: str = "1.0.0"
    
    def __post_init__(self):
        """Initialize default points if empty."""
        if not self.points and self.resolution:
            self._init_default_points()
    
    def _init_default_points(self):
        """Initialize grid-aligned points with zero offsets."""
        subdivisions = self.resolution.value * self.bars
        step = 1.0 / self.resolution.value
        
        for i in range(subdivisions):
            bar = i // self.resolution.value
            pos_in_bar = (i % self.resolution.value) * step
            position = bar + pos_in_bar
            
            self.points.append(GroovePoint(
                position=position / self.bars,  # Normalize to 0-1
                timing_offset_ticks=0,
                velocity_offset=0,
                accent=1.0
            ))
    
    def get_offset_at_position(self, position: float) -> Tuple[int, int, float]:
        """
        Get timing/velocity offset for a note at given position.
        
        Args:
            position: Position in bar (0.0 to 1.0 per bar)
            
        Returns:
            Tuple of (timing_offset_ticks, velocity_offset, accent)
        """
        if not self.points:
            return (0, 0, 1.0)
        
        # Normalize position to template range
        pos_normalized = position % 1.0
        
        # Find closest groove point
        closest_point = min(
            self.points,
            key=lambda p: abs((p.position % 1.0) - pos_normalized)
        )
        
        # Apply intensity scaling
        timing = int(closest_point.timing_offset_ticks * self.intensity)
        velocity = int(closest_point.velocity_offset * self.intensity)
        accent = 1.0 + (closest_point.accent - 1.0) * self.intensity
        
        return (timing, velocity, accent)
    
    def apply_swing(self, swing_override: Optional[float] = None):
        """
        Apply swing feel by shifting off-beat positions.
        
        Swing delays the 2nd, 4th, etc. subdivisions to create a triplet-like feel.
        
        Args:
            swing_override: Override the template's swing_amount (0.0-1.0)
        """
        swing = swing_override if swing_override is not None else self.swing_amount
        if swing <= 0:
            return
        
        # Calculate swing offset (max ~30 ticks for full swing)
        max_swing_ticks = int(TICKS_PER_BEAT / 4 * 0.33)  # ~40 ticks
        swing_offset = int(max_swing_ticks * swing)
        
        # Apply to off-beat positions (positions at odd indices)
        for i, point in enumerate(self.points):
            # Determine if this is an off-beat position
            subdivision = self.resolution.value
            position_index = int(point.position * subdivision) % subdivision
            
            # Off-beats are odd positions in the subdivision grid
            if position_index % 2 == 1:
                point.timing_offset_ticks += swing_offset
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            'schema_version': self.SCHEMA_VERSION,
            'name': self.name,
            'resolution': self.resolution.name,
            'bars': self.bars,
            'points': [p.to_dict() for p in self.points],
            'swing_amount': self.swing_amount,
            'intensity': self.intensity,
            'source': self.source,
            'genre': self.genre,
            'created_at': self.created_at,
            'metadata': self.metadata
        }
    
    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> 'GrooveTemplate':
        """Deserialize from dictionary."""
        return cls(
            name=d['name'],
            resolution=GrooveResolution[d.get('resolution', 'SIXTEENTH')],
            bars=d.get('bars', 1),
            points=[GroovePoint.from_dict(p) for p in d.get('points', [])],
            swing_amount=d.get('swing_amount', 0.0),
            intensity=d.get('intensity', 1.0),
            source=d.get('source', 'preset'),
            genre=d.get('genre'),
            created_at=d.get('created_at', datetime.now(timezone.utc).isoformat()),
            metadata=d.get('metadata', {})
        )
    
    def save(self, path: Union[str, Path]):
        """Save template to JSON file."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, indent=2)
    
    @classmethod
    def load(cls, path: Union[str, Path]) -> 'GrooveTemplate':
        """Load template from JSON file."""
        with open(path, 'r', encoding='utf-8') as f:
            return cls.from_dict(json.load(f))
    
    def copy(self) -> 'GrooveTemplate':
        """Create a deep copy of this template."""
        return GrooveTemplate.from_dict(self.to_dict())


@dataclass
class GrooveExtractionResult:
    """Result from groove extraction."""
    template: GrooveTemplate
    confidence: float  # 0.0-1.0
    detected_bpm: Optional[float] = None
    onset_count: int = 0
    analysis_notes: List[str] = field(default_factory=list)


class GrooveExtractor:
    """
    Extract groove templates from audio or MIDI files.
    
    Uses onset detection to find note timings, then calculates
    how far each onset deviates from the quantized grid.
    """
    
    def __init__(self, sample_rate: int = 22050):
        self.sample_rate = sample_rate
        self._librosa = None
    
    def _get_librosa(self):
        """Lazy load librosa."""
        if self._librosa is None:
            try:
                import librosa
                self._librosa = librosa
            except ImportError:
                raise ImportError("librosa required for groove extraction")
        return self._librosa
    
    def extract_from_audio(
        self,
        audio_path: str,
        bpm: Optional[float] = None,
        bars: int = 2,
        resolution: GrooveResolution = GrooveResolution.SIXTEENTH,
        name: Optional[str] = None
    ) -> GrooveExtractionResult:
        """
        Extract groove template from audio file.
        
        Args:
            audio_path: Path to audio file (WAV, MP3, etc.)
            bpm: Known BPM (if None, will detect)
            bars: Number of bars to analyze (1-4)
            resolution: Target subdivision resolution
            name: Template name (defaults to filename)
            
        Returns:
            GrooveExtractionResult with template and confidence
        """
        librosa = self._get_librosa()
        
        # Load audio
        y, sr = librosa.load(audio_path, sr=self.sample_rate, mono=True)
        duration = len(y) / sr
        
        # Detect BPM if not provided
        if bpm is None:
            tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
            bpm = float(np.atleast_1d(tempo)[0])
        
        # Calculate bar duration
        beats_per_bar = 4  # Assume 4/4
        bar_duration = (60.0 / bpm) * beats_per_bar
        
        # Get onset times
        onset_env = librosa.onset.onset_strength(y=y, sr=sr)
        onset_frames = librosa.onset.onset_detect(
            onset_envelope=onset_env,
            sr=sr,
            units='frames'
        )
        onset_times = librosa.frames_to_time(onset_frames, sr=sr)
        
        # Separate percussive for better onset detection
        y_harm, y_perc = librosa.effects.hpss(y)
        perc_onset_env = librosa.onset.onset_strength(y=y_perc, sr=sr)
        perc_onset_frames = librosa.onset.onset_detect(
            onset_envelope=perc_onset_env,
            sr=sr,
            units='frames'
        )
        perc_onset_times = librosa.frames_to_time(perc_onset_frames, sr=sr)
        
        # Combine onset times (prefer percussive)
        all_onsets = np.unique(np.concatenate([onset_times, perc_onset_times]))
        
        # Create template
        template_name = name or Path(audio_path).stem
        template = GrooveTemplate(
            name=template_name,
            resolution=resolution,
            bars=bars,
            source=f"extracted:{audio_path}",
            points=[]  # Will populate below
        )
        
        # Calculate timing offsets for each subdivision
        subdivisions = resolution.value * bars
        subdivision_duration = bar_duration / resolution.value
        
        # Analyze multiple bar windows and average
        analysis_bars = int(duration / bar_duration)
        if analysis_bars < 1:
            analysis_bars = 1
        
        # Collect offsets per subdivision position
        position_offsets: Dict[int, List[int]] = {i: [] for i in range(subdivisions)}
        position_velocities: Dict[int, List[float]] = {i: [] for i in range(subdivisions)}
        
        # Analyze each bar
        for bar_idx in range(min(analysis_bars, 8)):  # Analyze up to 8 bars
            bar_start = bar_idx * bar_duration
            bar_end = bar_start + bars * bar_duration
            
            # Get onsets in this window
            bar_onsets = all_onsets[(all_onsets >= bar_start) & (all_onsets < bar_end)]
            
            for onset_time in bar_onsets:
                # Calculate position relative to bar start
                rel_time = (onset_time - bar_start) % (bar_duration * bars)
                
                # Find nearest grid position
                subdivision_idx = int(round(rel_time / subdivision_duration))
                if subdivision_idx >= subdivisions:
                    subdivision_idx = 0
                
                # Calculate offset from grid
                grid_time = subdivision_idx * subdivision_duration
                offset_seconds = rel_time - grid_time
                offset_ticks = int(offset_seconds * TICKS_PER_BEAT * (bpm / 60))
                
                # Clamp to reasonable range
                offset_ticks = max(-60, min(60, offset_ticks))
                
                position_offsets[subdivision_idx].append(offset_ticks)
                
                # Estimate velocity from onset strength
                onset_frame = librosa.time_to_frames(onset_time, sr=sr)
                if onset_frame < len(onset_env):
                    strength = onset_env[onset_frame]
                    position_velocities[subdivision_idx].append(strength)
        
        # Build groove points from averaged offsets
        groove_points = []
        for i in range(subdivisions):
            position = i / subdivisions
            
            # Average timing offset
            if position_offsets[i]:
                avg_offset = int(np.median(position_offsets[i]))
            else:
                avg_offset = 0
            
            # Calculate velocity offset from relative strength
            if position_velocities[i]:
                avg_strength = np.mean(position_velocities[i])
                max_strength = max(max(v) for v in position_velocities.values() if v) or 1.0
                rel_strength = avg_strength / max_strength
                # Convert to velocity offset (-20 to +20 range)
                velocity_offset = int((rel_strength - 0.5) * 40)
            else:
                velocity_offset = 0
            
            # Calculate accent
            accent = 1.0
            if position_velocities[i]:
                accent = 0.8 + 0.4 * (np.mean(position_velocities[i]) / 
                                       (max(max(v) for v in position_velocities.values() if v) or 1.0))
            
            groove_points.append(GroovePoint(
                position=position,
                timing_offset_ticks=avg_offset,
                velocity_offset=velocity_offset,
                accent=accent
            ))
        
        template.points = groove_points
        
        # Detect swing amount from off-beat timing
        swing = self._detect_swing(groove_points, resolution)
        template.swing_amount = swing
        
        # Calculate confidence based on consistency
        confidence = self._calculate_confidence(position_offsets)
        
        return GrooveExtractionResult(
            template=template,
            confidence=confidence,
            detected_bpm=bpm,
            onset_count=len(all_onsets),
            analysis_notes=[
                f"Analyzed {analysis_bars} bars",
                f"Found {len(all_onsets)} onsets",
                f"Swing detected: {swing:.2f}"
            ]
        )
    
    def extract_from_midi(
        self,
        midi_path: str,
        name: Optional[str] = None,
        bars: int = 2,
        resolution: GrooveResolution = GrooveResolution.SIXTEENTH
    ) -> GrooveExtractionResult:
        """
        Extract groove template from MIDI file.
        
        MIDI extraction is more accurate than audio since we have exact timing.
        """
        import mido
        
        midi = mido.MidiFile(midi_path)
        ticks_per_beat = midi.ticks_per_beat
        
        # Collect all note events
        notes = []
        tempo = 500000  # Default 120 BPM
        
        for track in midi.tracks:
            current_tick = 0
            for msg in track:
                current_tick += msg.time
                if msg.type == 'set_tempo':
                    tempo = msg.tempo
                elif msg.type == 'note_on' and msg.velocity > 0:
                    notes.append({
                        'tick': current_tick,
                        'velocity': msg.velocity,
                        'note': msg.note
                    })
        
        if not notes:
            return GrooveExtractionResult(
                template=GrooveTemplate(name=name or "empty", source="midi:empty"),
                confidence=0.0,
                analysis_notes=["No notes found in MIDI"]
            )
        
        # Calculate BPM
        bpm = 60_000_000 / tempo
        
        # Calculate bar duration in ticks
        beats_per_bar = 4
        ticks_per_bar = ticks_per_beat * beats_per_bar
        
        # Create template
        template_name = name or Path(midi_path).stem
        template = GrooveTemplate(
            name=template_name,
            resolution=resolution,
            bars=bars,
            source=f"midi:{midi_path}",
            points=[]
        )
        
        # Calculate subdivisions
        subdivisions = resolution.value * bars
        ticks_per_subdivision = (ticks_per_bar * bars) / subdivisions
        
        # Collect offsets per subdivision
        position_offsets: Dict[int, List[int]] = {i: [] for i in range(subdivisions)}
        position_velocities: Dict[int, List[int]] = {i: [] for i in range(subdivisions)}
        
        for note in notes:
            tick = note['tick']
            velocity = note['velocity']
            
            # Find position within template range
            tick_in_pattern = tick % (ticks_per_bar * bars)
            
            # Find nearest subdivision
            subdivision_idx = int(round(tick_in_pattern / ticks_per_subdivision))
            if subdivision_idx >= subdivisions:
                subdivision_idx = 0
            
            # Calculate offset from grid
            grid_tick = subdivision_idx * ticks_per_subdivision
            offset = int(tick_in_pattern - grid_tick)
            
            # Normalize to TICKS_PER_BEAT scale
            offset = int(offset * (TICKS_PER_BEAT / ticks_per_beat))
            offset = max(-60, min(60, offset))
            
            position_offsets[subdivision_idx].append(offset)
            position_velocities[subdivision_idx].append(velocity)
        
        # Build groove points
        avg_velocity = np.mean([v for vlist in position_velocities.values() for v in vlist]) if any(position_velocities.values()) else 64
        
        for i in range(subdivisions):
            position = i / subdivisions
            
            # Average timing offset
            if position_offsets[i]:
                avg_offset = int(np.median(position_offsets[i]))
            else:
                avg_offset = 0
            
            # Velocity offset relative to average
            if position_velocities[i]:
                pos_avg_vel = np.mean(position_velocities[i])
                velocity_offset = int(pos_avg_vel - avg_velocity)
            else:
                velocity_offset = 0
            
            # Accent
            accent = 1.0
            if position_velocities[i]:
                accent = 0.8 + 0.4 * (np.mean(position_velocities[i]) / 127)
            
            template.points.append(GroovePoint(
                position=position,
                timing_offset_ticks=avg_offset,
                velocity_offset=velocity_offset,
                accent=accent
            ))
        
        # Detect swing
        template.swing_amount = self._detect_swing(template.points, resolution)
        
        # Calculate confidence
        confidence = self._calculate_confidence(position_offsets)
        
        return GrooveExtractionResult(
            template=template,
            confidence=confidence,
            detected_bpm=bpm,
            onset_count=len(notes),
            analysis_notes=[f"MIDI extraction from {len(notes)} notes"]
        )
    
    def _detect_swing(
        self,
        points: List[GroovePoint],
        resolution: GrooveResolution
    ) -> float:
        """Detect swing amount from groove points."""
        if len(points) < 4:
            return 0.0
        
        # Look at off-beat positions (odd indices)
        off_beat_offsets = []
        on_beat_offsets = []
        
        for i, point in enumerate(points):
            if i % 2 == 1:  # Off-beat
                off_beat_offsets.append(point.timing_offset_ticks)
            else:  # On-beat
                on_beat_offsets.append(point.timing_offset_ticks)
        
        if not off_beat_offsets:
            return 0.0
        
        # Swing = average delay of off-beats relative to on-beats
        avg_off = np.mean(off_beat_offsets) if off_beat_offsets else 0
        avg_on = np.mean(on_beat_offsets) if on_beat_offsets else 0
        
        # Calculate swing as normalized offset difference
        swing_ticks = avg_off - avg_on
        max_swing = TICKS_PER_BEAT / 8  # ~60 ticks
        
        swing = max(0.0, min(1.0, swing_ticks / max_swing))
        return swing
    
    def _calculate_confidence(
        self,
        position_offsets: Dict[int, List[int]]
    ) -> float:
        """Calculate confidence based on consistency of detected offsets."""
        if not any(position_offsets.values()):
            return 0.0
        
        # Calculate variance per position
        variances = []
        for offsets in position_offsets.values():
            if len(offsets) > 1:
                variances.append(np.var(offsets))
        
        if not variances:
            return 0.5  # Not enough data
        
        # Lower variance = higher confidence
        avg_variance = np.mean(variances)
        # Normalize: variance of 0 = 1.0 confidence, variance of 400+ = 0.0
        confidence = max(0.0, 1.0 - (avg_variance / 400))
        
        return confidence


class GrooveApplicator:
    """
    Apply groove templates to MIDI notes non-destructively.
    
    The applicator transforms note timings and velocities according
    to the groove template, keeping the base pattern separate.
    """
    
    def __init__(self, ticks_per_beat: int = TICKS_PER_BEAT):
        self.ticks_per_beat = ticks_per_beat
    
    def apply(
        self,
        notes: List[Dict[str, Any]],
        template: GrooveTemplate,
        intensity: Optional[float] = None,
        preserve_original: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Apply groove template to notes.
        
        Args:
            notes: List of note dicts with 'tick', 'velocity', etc.
            template: Groove template to apply
            intensity: Override template intensity (0.0-1.0)
            preserve_original: If True, keep original timing in 'original_tick'
            
        Returns:
            List of notes with groove applied
        """
        if not notes or not template.points:
            return notes
        
        # Use override intensity if provided
        apply_intensity = intensity if intensity is not None else template.intensity
        
        # Calculate ticks per bar
        beats_per_bar = 4
        ticks_per_bar = self.ticks_per_beat * beats_per_bar
        
        result = []
        for note in notes:
            new_note = dict(note)
            
            # Preserve original if requested
            if preserve_original:
                new_note['original_tick'] = note.get('tick', 0)
                new_note['original_velocity'] = note.get('velocity', 64)
            
            tick = note.get('tick', 0)
            velocity = note.get('velocity', 64)
            
            # Calculate position in bar (0.0 to 1.0)
            position = (tick % (ticks_per_bar * template.bars)) / (ticks_per_bar * template.bars)
            
            # Get groove offset for this position
            timing_offset, velocity_offset, accent = template.get_offset_at_position(position)
            
            # Apply intensity scaling
            timing_offset = int(timing_offset * apply_intensity)
            velocity_offset = int(velocity_offset * apply_intensity)
            accent = 1.0 + (accent - 1.0) * apply_intensity
            
            # Apply groove
            new_note['tick'] = tick + timing_offset
            new_note['velocity'] = max(1, min(127, int(velocity * accent + velocity_offset)))
            
            # Store groove metadata
            new_note['groove_applied'] = {
                'template': template.name,
                'timing_offset': timing_offset,
                'velocity_offset': velocity_offset,
                'accent': accent
            }
            
            result.append(new_note)
        
        return result
    
    def remove_groove(
        self,
        notes: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Remove groove and restore original timing/velocity.
        
        Only works on notes that have 'original_tick' preserved.
        """
        result = []
        for note in notes:
            new_note = dict(note)
            
            # Restore originals if available
            if 'original_tick' in note:
                new_note['tick'] = note['original_tick']
                del new_note['original_tick']
            
            if 'original_velocity' in note:
                new_note['velocity'] = note['original_velocity']
                del new_note['original_velocity']
            
            if 'groove_applied' in new_note:
                del new_note['groove_applied']
            
            result.append(new_note)
        
        return result
    
    def blend_grooves(
        self,
        notes: List[Dict[str, Any]],
        templates: List[GrooveTemplate],
        weights: Optional[List[float]] = None
    ) -> List[Dict[str, Any]]:
        """
        Blend multiple groove templates together.
        
        Useful for creating hybrid feels (e.g., 70% boom-bap + 30% swing).
        """
        if not templates:
            return notes
        
        # Default equal weights
        if weights is None:
            weights = [1.0 / len(templates)] * len(templates)
        
        # Normalize weights
        total = sum(weights)
        weights = [w / total for w in weights]
        
        beats_per_bar = 4
        ticks_per_bar = self.ticks_per_beat * beats_per_bar
        
        result = []
        for note in notes:
            new_note = dict(note)
            new_note['original_tick'] = note.get('tick', 0)
            new_note['original_velocity'] = note.get('velocity', 64)
            
            tick = note.get('tick', 0)
            velocity = note.get('velocity', 64)
            
            # Blend offsets from all templates
            total_timing = 0
            total_velocity = 0
            total_accent = 0
            
            for template, weight in zip(templates, weights):
                bars = template.bars or 1
                position = (tick % (ticks_per_bar * bars)) / (ticks_per_bar * bars)
                timing_offset, velocity_offset, accent = template.get_offset_at_position(position)
                
                total_timing += timing_offset * weight
                total_velocity += velocity_offset * weight
                total_accent += accent * weight
            
            # Apply blended groove
            new_note['tick'] = tick + int(total_timing)
            new_note['velocity'] = max(1, min(127, int(velocity * total_accent + total_velocity)))
            
            result.append(new_note)
        
        return result


# =============================================================================
# PRESET GROOVES
# =============================================================================

def _create_boom_bap_groove() -> GrooveTemplate:
    """Classic boom-bap feel with push on 2 and 4."""
    template = GrooveTemplate(
        name="Boom Bap",
        resolution=GrooveResolution.SIXTEENTH,
        bars=1,
        swing_amount=0.15,
        genre="boom_bap",
        source="preset"
    )
    
    # Clear default points
    template.points = []
    
    # 16 subdivisions per bar
    # Kick tends to be slightly late, snare slightly early
    offsets = [
        (0.0, 5, 10, 1.3),     # 1 - strong downbeat
        (0.0625, 0, -5, 0.8),   # e
        (0.125, 8, 0, 0.9),     # + (off-beat pushed)
        (0.1875, 0, -5, 0.7),   # a
        (0.25, -5, 5, 1.1),     # 2 - snare pull
        (0.3125, 0, -5, 0.8),   # e
        (0.375, 10, 0, 0.9),    # + (swing)
        (0.4375, 0, -5, 0.7),   # a
        (0.5, 3, 8, 1.2),       # 3
        (0.5625, 0, -5, 0.8),   # e
        (0.625, 8, 0, 0.9),     # +
        (0.6875, 0, -5, 0.7),   # a
        (0.75, -8, 5, 1.15),    # 4 - snare pull
        (0.8125, 0, -5, 0.8),   # e
        (0.875, 12, 0, 0.9),    # +
        (0.9375, 0, -5, 0.7),   # a
    ]
    
    for pos, timing, velocity, accent in offsets:
        template.points.append(GroovePoint(
            position=pos,
            timing_offset_ticks=timing,
            velocity_offset=velocity,
            accent=accent
        ))
    
    return template


def _create_trap_groove() -> GrooveTemplate:
    """Modern trap feel - machine tight but with subtle push."""
    template = GrooveTemplate(
        name="Trap",
        resolution=GrooveResolution.SIXTEENTH,
        bars=1,
        swing_amount=0.0,  # Trap is usually straight
        genre="trap",
        source="preset"
    )
    
    template.points = []
    
    # Trap is mostly quantized but with slight dynamics
    for i in range(16):
        pos = i / 16
        
        # Slight push on hi-hats (every other)
        timing = 2 if i % 2 == 1 else 0
        
        # Strong accents on 1 and 3
        if i == 0 or i == 8:
            accent = 1.25
            velocity = 10
        elif i == 4 or i == 12:  # 2 and 4
            accent = 1.1
            velocity = 5
        else:
            accent = 0.85
            velocity = -5
        
        template.points.append(GroovePoint(
            position=pos,
            timing_offset_ticks=timing,
            velocity_offset=velocity,
            accent=accent
        ))
    
    return template


def _create_lofi_groove() -> GrooveTemplate:
    """Lo-fi hip-hop lazy feel."""
    template = GrooveTemplate(
        name="Lo-Fi",
        resolution=GrooveResolution.SIXTEENTH,
        bars=1,
        swing_amount=0.25,
        genre="lofi",
        source="preset"
    )
    
    template.points = []
    
    # Lo-fi has a lazy, behind-the-beat feel
    for i in range(16):
        pos = i / 16
        
        # Everything slightly late
        base_late = 8
        
        # More swing on off-beats
        if i % 2 == 1:
            timing = base_late + 12
        else:
            timing = base_late
        
        # Soft dynamics
        if i % 4 == 0:
            accent = 1.1
            velocity = 5
        else:
            accent = 0.9
            velocity = -8
        
        template.points.append(GroovePoint(
            position=pos,
            timing_offset_ticks=timing,
            velocity_offset=velocity,
            accent=accent
        ))
    
    return template


def _create_house_groove() -> GrooveTemplate:
    """House/dance straight feel with driving 4/4."""
    template = GrooveTemplate(
        name="House",
        resolution=GrooveResolution.SIXTEENTH,
        bars=1,
        swing_amount=0.0,
        genre="house",
        source="preset"
    )
    
    template.points = []
    
    for i in range(16):
        pos = i / 16
        
        # Tight timing, slight push on off-beats
        timing = 3 if i % 2 == 1 else 0
        
        # Strong on all quarter notes
        if i % 4 == 0:
            accent = 1.2
            velocity = 12
        elif i % 2 == 0:
            accent = 1.0
            velocity = 0
        else:
            accent = 0.85
            velocity = -10
        
        template.points.append(GroovePoint(
            position=pos,
            timing_offset_ticks=timing,
            velocity_offset=velocity,
            accent=accent
        ))
    
    return template


def _create_gfunk_groove() -> GrooveTemplate:
    """G-funk lazy swing feel."""
    template = GrooveTemplate(
        name="G-Funk",
        resolution=GrooveResolution.SIXTEENTH,
        bars=1,
        swing_amount=0.2,
        genre="g_funk",
        source="preset"
    )
    
    template.points = []
    
    for i in range(16):
        pos = i / 16
        
        # G-funk has a relaxed, behind-beat feel
        base_late = 6
        if i % 2 == 1:
            timing = base_late + 10  # Swing
        else:
            timing = base_late
        
        # Accents on 2 and 4 (snare)
        if i == 4 or i == 12:
            accent = 1.15
            velocity = 8
        elif i == 0 or i == 8:
            accent = 1.1
            velocity = 5
        else:
            accent = 0.9
            velocity = -5
        
        template.points.append(GroovePoint(
            position=pos,
            timing_offset_ticks=timing,
            velocity_offset=velocity,
            accent=accent
        ))
    
    return template


def _create_eskista_groove() -> GrooveTemplate:
    """Ethiopian eskista shoulder-dance rhythm (6/8 feel)."""
    template = GrooveTemplate(
        name="Eskista",
        resolution=GrooveResolution.TRIPLET_8,  # 12 subdivisions for 6/8
        bars=1,
        swing_amount=0.0,  # Triplet feel, not swing
        genre="eskista",
        source="preset"
    )
    
    template.points = []
    
    # 12 subdivisions for compound meter
    # Strong accents in groups of 3
    for i in range(12):
        pos = i / 12
        
        # First of each group of 3 is accented
        if i % 3 == 0:
            accent = 1.25
            velocity = 15
            timing = 0
        elif i % 3 == 1:
            accent = 0.85
            velocity = -10
            timing = 5  # Slight push
        else:
            accent = 0.75
            velocity = -15
            timing = 3
        
        template.points.append(GroovePoint(
            position=pos,
            timing_offset_ticks=timing,
            velocity_offset=velocity,
            accent=accent
        ))
    
    return template


def _create_drill_groove() -> GrooveTemplate:
    """UK/Chicago drill aggressive slide feel."""
    template = GrooveTemplate(
        name="Drill",
        resolution=GrooveResolution.SIXTEENTH,
        bars=1,
        swing_amount=0.05,  # Very slight
        genre="drill",
        source="preset"
    )
    
    template.points = []
    
    for i in range(16):
        pos = i / 16
        
        # Drill has a driving, slightly ahead feel
        timing = -3 if i % 4 == 0 else 0
        
        # Very hard accents
        if i % 4 == 0:
            accent = 1.3
            velocity = 15
        elif i % 2 == 0:
            accent = 1.0
            velocity = 0
        else:
            accent = 0.8
            velocity = -10
        
        template.points.append(GroovePoint(
            position=pos,
            timing_offset_ticks=timing,
            velocity_offset=velocity,
            accent=accent
        ))
    
    return template


# -------------------------------------------------------------------------
# New preset grooves (Sprint 2 — Task 2.3)
# -------------------------------------------------------------------------

def _create_neo_soul_groove() -> GrooveTemplate:
    """Neo-soul: heavily behind-beat, lazy hi-hats, 16th resolution."""
    template = GrooveTemplate(
        name="Neo Soul",
        resolution=GrooveResolution.SIXTEENTH,
        bars=1,
        swing_amount=0.35,
        genre="neo_soul",
        source="preset",
    )
    template.points = []

    for i in range(16):
        pos = i / 16

        # Beats 2 & 4 (indices 4, 12) drag slightly late
        if i in (4, 12):
            timing = 18   # ~20ms at 120 BPM
            accent = 1.3
            velocity = 12
        elif i in (0, 8):
            timing = 5
            accent = 1.15
            velocity = 8
        elif i % 2 == 1:
            # Hi-hat off-beats: lazy ±variance
            timing = random.choice([8, 12, 15])
            accent = 0.55
            velocity = -15
        else:
            timing = 6
            accent = 0.85
            velocity = -5

        template.points.append(GroovePoint(
            position=pos,
            timing_offset_ticks=timing,
            velocity_offset=velocity,
            accent=accent,
        ))

    return template


def _create_gospel_groove() -> GrooveTemplate:
    """Gospel: shuffle with strong backbeat, quarter-note drive."""
    template = GrooveTemplate(
        name="Gospel",
        resolution=GrooveResolution.SIXTEENTH,
        bars=1,
        swing_amount=0.40,
        genre="gospel",
        source="preset",
    )
    template.points = []

    for i in range(16):
        pos = i / 16

        if i == 0:
            timing = -3   # push beat 1 slightly early
            accent = 1.2
            velocity = 10
        elif i in (4, 12):
            timing = 0    # beats 2 & 4 on grid (strong backbeat)
            accent = 1.4
            velocity = 18
        elif i in (8,):
            timing = -2
            accent = 1.15
            velocity = 8
        elif i % 2 == 1:
            timing = 14   # swing on off-beats
            accent = 0.75
            velocity = -10
        else:
            timing = 2
            accent = 0.9
            velocity = 0

        template.points.append(GroovePoint(
            position=pos,
            timing_offset_ticks=timing,
            velocity_offset=velocity,
            accent=accent,
        ))

    return template


def _create_jazz_groove() -> GrooveTemplate:
    """Jazz: triplet swing on 8ths, very dynamic ride pattern."""
    template = GrooveTemplate(
        name="Jazz",
        resolution=GrooveResolution.SIXTEENTH,
        bars=1,
        swing_amount=0.55,
        genre="jazz",
        source="preset",
    )
    template.points = []

    for i in range(16):
        pos = i / 16

        # Triplet swing: delay every other 8th
        if i % 2 == 1:
            timing = 22   # triplet swing offset
            accent = 0.7
            velocity = -12
        elif i % 4 == 0:
            timing = 0
            accent = 1.4
            velocity = 15
        else:
            timing = 0
            accent = 0.5
            velocity = -20

        template.points.append(GroovePoint(
            position=pos,
            timing_offset_ticks=timing,
            velocity_offset=velocity,
            accent=accent,
        ))

    return template


def _create_rnb_groove() -> GrooveTemplate:
    """R&B: smooth pocket, slight behind-beat snare."""
    template = GrooveTemplate(
        name="R&B",
        resolution=GrooveResolution.SIXTEENTH,
        bars=1,
        swing_amount=0.25,
        genre="rnb",
        source="preset",
    )
    template.points = []

    for i in range(16):
        pos = i / 16

        if i in (4, 12):
            timing = 8    # snare slightly behind
            accent = 1.1
            velocity = 8
        elif i in (0, 8):
            timing = 0    # kick on grid
            accent = 1.05
            velocity = 5
        elif i % 2 == 1:
            timing = 6
            accent = 0.7
            velocity = -10
        else:
            timing = 3
            accent = 0.85
            velocity = -3

        template.points.append(GroovePoint(
            position=pos,
            timing_offset_ticks=timing,
            velocity_offset=velocity,
            accent=accent,
        ))

    return template


def _create_ambient_groove() -> GrooveTemplate:
    """Ambient: very loose floating feel, soft dynamics."""
    template = GrooveTemplate(
        name="Ambient",
        resolution=GrooveResolution.SIXTEENTH,
        bars=1,
        swing_amount=0.10,
        genre="ambient",
        source="preset",
    )
    template.points = []

    for i in range(16):
        pos = i / 16
        # Wide timing variance ±~20 ticks
        timing = random.choice([-15, -8, 0, 8, 15])

        if i % 4 == 0:
            accent = 0.9
            velocity = 0
        else:
            accent = 0.5 + random.random() * 0.4
            velocity = random.randint(-18, -5)

        template.points.append(GroovePoint(
            position=pos,
            timing_offset_ticks=timing,
            velocity_offset=velocity,
            accent=accent,
        ))

    return template


def _create_deep_house_groove() -> GrooveTemplate:
    """Deep house: four-on-floor with subtle push, consistent dynamics."""
    template = GrooveTemplate(
        name="Deep House",
        resolution=GrooveResolution.SIXTEENTH,
        bars=1,
        swing_amount=0.08,
        genre="deep_house",
        source="preset",
    )
    template.points = []

    for i in range(16):
        pos = i / 16

        if i % 4 == 0:
            # Kick dead on grid
            timing = 0
            accent = 1.1
            velocity = 8
        elif i % 2 == 1:
            # Hi-hat slightly ahead
            timing = -3
            accent = 0.85
            velocity = -5
        else:
            timing = 0
            accent = 0.95
            velocity = 0

        template.points.append(GroovePoint(
            position=pos,
            timing_offset_ticks=timing,
            velocity_offset=velocity,
            accent=accent,
        ))

    return template


def _create_afrobeat_groove() -> GrooveTemplate:
    """Afrobeat: polyrhythmic feel, strong downbeat, cross-rhythmic hi-hat."""
    template = GrooveTemplate(
        name="Afrobeat",
        resolution=GrooveResolution.SIXTEENTH,
        bars=1,
        swing_amount=0.20,
        genre="afrobeat",
        source="preset",
    )
    template.points = []

    # Cross-rhythmic accents: groupings of 3 over 16th grid
    cross_accents = {0, 3, 6, 9, 12, 15}

    for i in range(16):
        pos = i / 16

        if i == 0:
            timing = 0
            accent = 1.3
            velocity = 15
        elif i in cross_accents:
            timing = 5
            accent = 1.15
            velocity = 8
        elif i % 2 == 1:
            timing = 8
            accent = 0.8
            velocity = -8
        else:
            timing = 3
            accent = 0.9
            velocity = -3

        template.points.append(GroovePoint(
            position=pos,
            timing_offset_ticks=timing,
            velocity_offset=velocity,
            accent=accent,
        ))

    return template


def _create_classical_groove() -> GrooveTemplate:
    """Classical: metronomic precision with subtle rubato."""
    template = GrooveTemplate(
        name="Classical",
        resolution=GrooveResolution.SIXTEENTH,
        bars=1,
        swing_amount=0.0,
        genre="classical",
        source="preset",
    )
    template.points = []

    for i in range(16):
        pos = i / 16

        # Near-zero timing offsets (±2 ticks ≈ rubato)
        timing = random.choice([-2, -1, 0, 1, 2])

        if i % 4 == 0:
            accent = 1.2
            velocity = 10
        elif i % 2 == 0:
            accent = 1.0
            velocity = 0
        else:
            accent = 0.7
            velocity = -8

        template.points.append(GroovePoint(
            position=pos,
            timing_offset_ticks=timing,
            velocity_offset=velocity,
            accent=accent,
        ))

    return template


# Preset groove registry
PRESET_GROOVES: Dict[str, GrooveTemplate] = {}


def _init_presets():
    """Initialize preset grooves."""
    global PRESET_GROOVES
    PRESET_GROOVES = {
        'boom_bap': _create_boom_bap_groove(),
        'trap': _create_trap_groove(),
        'lofi': _create_lofi_groove(),
        'house': _create_house_groove(),
        'g_funk': _create_gfunk_groove(),
        'eskista': _create_eskista_groove(),
        'drill': _create_drill_groove(),
        'neo_soul': _create_neo_soul_groove(),
        'gospel': _create_gospel_groove(),
        'jazz': _create_jazz_groove(),
        'rnb': _create_rnb_groove(),
        'ambient': _create_ambient_groove(),
        'deep_house': _create_deep_house_groove(),
        'afrobeat': _create_afrobeat_groove(),
        'classical': _create_classical_groove(),
    }


def get_preset_groove(name: str) -> Optional[GrooveTemplate]:
    """
    Get a preset groove template by name.
    
    Available presets: boom_bap, trap, lofi, house, g_funk, eskista, drill,
    neo_soul, gospel, jazz, rnb, ambient, deep_house, afrobeat, classical
    """
    if not PRESET_GROOVES:
        _init_presets()
    
    template = PRESET_GROOVES.get(name.lower())
    if template:
        return template.copy()  # Return a copy to prevent modification
    return None


def get_groove_for_genre(genre: str) -> Optional[GrooveTemplate]:
    """
    Get the most appropriate groove template for a genre.
    
    Maps genre names to groove presets with fallbacks.
    
    See also:
        get_timing_offset(): Get per-instrument timing offsets for a genre.
        apply_timing_offsets(): Apply per-instrument timing offsets to notes.
    """
    if not PRESET_GROOVES:
        _init_presets()
    
    # Direct match
    if genre.lower() in PRESET_GROOVES:
        return PRESET_GROOVES[genre.lower()].copy()
    
    # Genre to groove mapping
    genre_map = {
        'trap_soul': 'trap',
        'rnb': 'rnb',
        'r&b': 'rnb',
        'neo_soul': 'neo_soul',
        'ethiopian_traditional': 'eskista',
        'ethio_jazz': 'eskista',
        'uk_drill': 'drill',
        'chicago_drill': 'drill',
        'west_coast': 'g_funk',
        'gospel': 'gospel',
        'jazz': 'jazz',
        'ambient': 'ambient',
        'deep_house': 'deep_house',
        'afrobeats': 'afrobeat',
        'afrobeat': 'afrobeat',
        'classical': 'classical',
    }
    
    mapped = genre_map.get(genre.lower())
    if mapped and mapped in PRESET_GROOVES:
        return PRESET_GROOVES[mapped].copy()
    
    # Default to boom_bap for hip-hop styles
    if any(x in genre.lower() for x in ['hip', 'hop', 'rap', 'beat']):
        return PRESET_GROOVES.get('boom_bap', GrooveTemplate(name="default")).copy()
    
    return None


def list_preset_grooves() -> List[str]:
    """List all available preset groove names."""
    if not PRESET_GROOVES:
        _init_presets()
    return list(PRESET_GROOVES.keys())


# Initialize presets on module load
_init_presets()


# =============================================================================
# GENRE-SPECIFIC PER-INSTRUMENT TIMING OFFSETS (P3-T6)
# =============================================================================

# Genre-specific per-instrument timing offsets in ticks (at 480 PPQ)
# Positive = behind the beat (lay back), Negative = ahead of beat (push)
GENRE_TIMING_OFFSETS: Dict[str, Dict[str, int]] = {
    "neo_soul": {
        "drums": 0,          # drums on grid
        "bass": 8,           # slightly behind for warmth
        "keys": -5,          # slightly ahead for presence
        "lead": -3,
        "strings": 10,       # strings laid back
    },
    "trap": {
        "drums": 0,
        "bass": 0,           # tight to grid for 808
        "keys": -8,          # hi-hats push forward
        "lead": -5,
        "strings": 5,
    },
    "house": {
        "drums": 0,
        "bass": 3,           # slight push on bass
        "keys": -4,
        "lead": -2,
        "strings": 6,
    },
    "lo_fi": {
        "drums": 12,         # everything loose/behind
        "bass": 15,
        "keys": 8,
        "lead": 10,
        "strings": 12,
    },
    "jazz": {
        "drums": 0,
        "bass": 5,           # walking bass sits behind
        "keys": -8,          # comping slightly ahead
        "lead": -3,
        "strings": 0,
    },
    "gospel": {
        "drums": 0,
        "bass": 6,
        "keys": -4,          # organ pushes slightly
        "lead": -2,
        "strings": 8,
    },
    "boom_bap": {
        "drums": 0,
        "bass": 10,          # boom-bap bass lays way back
        "keys": 5,           # samples drift slightly
        "lead": 3,
        "strings": 8,
    },
    "rnb": {
        "drums": 0,
        "bass": 6,
        "keys": -3,
        "lead": -5,
        "strings": 8,
    },
    "funk": {
        "drums": 0,
        "bass": -5,          # funk bass pushes AHEAD
        "keys": -8,          # clavinet on top
        "lead": -3,
        "strings": 5,
    },
    "ethiopian": {
        "drums": 0,          # kebero anchors
        "bass": 3,
        "keys": -6,          # krar slightly ahead
        "lead": -4,          # masenqo dances ahead
        "strings": 0,
    },
    "ambient": {
        "drums": 15,         # everything floaty
        "bass": 12,
        "keys": 10,
        "lead": 8,
        "strings": 20,       # strings very loose
    },
    "drill": {
        "drums": 0,
        "bass": 0,           # tight
        "keys": -10,
        "lead": -8,
        "strings": 5,
    },
}

# Genre alias mapping for timing offsets
_TIMING_GENRE_ALIASES: Dict[str, str] = {
    "trap_soul": "neo_soul",
    "ethio_jazz": "ethiopian",
    "deep_house": "house",
    "tech_house": "house",
    "classic_house": "house",
    "lofi": "lo_fi",
    "g_funk": "funk",
}


def get_timing_offset(genre: str, instrument: str) -> int:
    """Get the genre-specific timing offset for an instrument in ticks.

    Positive = behind the beat (laid back), Negative = ahead (pushing).
    Returns 0 if genre/instrument not found.

    Args:
        genre: Genre name (e.g. 'neo_soul', 'trap', 'jazz').
        instrument: Instrument role (e.g. 'drums', 'bass', 'keys', 'lead', 'strings').

    Returns:
        Timing offset in ticks at 480 PPQ.
    """
    genre_key = _TIMING_GENRE_ALIASES.get(genre, genre)
    offsets = GENRE_TIMING_OFFSETS.get(genre_key, {})
    return offsets.get(instrument, 0)


def apply_timing_offsets(
    notes: List[Dict[str, Any]],
    genre: str,
    instrument: str,
) -> List[Dict[str, Any]]:
    """Apply genre-specific timing offset to all notes.

    Non-destructive: returns a new list with adjusted tick values.
    Supports notes keyed by either ``tick`` or ``start``.

    Args:
        notes: List of note dicts (must contain 'tick' or 'start' key).
        genre: Genre name.
        instrument: Instrument role.

    Returns:
        New list of note dicts with timing offsets applied.
    """
    offset = get_timing_offset(genre, instrument)
    if offset == 0:
        return notes
    result = []
    for note in notes:
        adjusted = dict(note)
        if "tick" in adjusted:
            adjusted["tick"] = max(0, adjusted["tick"] + offset)
        elif "start" in adjusted:
            adjusted["start"] = max(0, adjusted["start"] + offset)
        result.append(adjusted)
    return result


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def extract_groove(
    source: str,
    bpm: Optional[float] = None,
    name: Optional[str] = None
) -> GrooveTemplate:
    """
    Convenience function to extract groove from file.
    
    Auto-detects file type (MIDI vs audio).
    """
    extractor = GrooveExtractor()
    
    source_lower = source.lower()
    if source_lower.endswith(('.mid', '.midi')):
        result = extractor.extract_from_midi(source, name=name)
    else:
        result = extractor.extract_from_audio(source, bpm=bpm, name=name)
    
    return result.template


def apply_groove(
    notes: List[Dict[str, Any]],
    groove_name_or_template: Union[str, GrooveTemplate],
    intensity: float = 1.0
) -> List[Dict[str, Any]]:
    """
    Convenience function to apply groove to notes.
    
    Args:
        notes: List of note dicts
        groove_name_or_template: Preset name or GrooveTemplate
        intensity: Groove intensity (0.0-1.0)
    """
    if isinstance(groove_name_or_template, str):
        template = get_preset_groove(groove_name_or_template)
        if not template:
            template = get_groove_for_genre(groove_name_or_template)
        if not template:
            raise ValueError(f"Unknown groove: {groove_name_or_template}")
    else:
        template = groove_name_or_template
    
    applicator = GrooveApplicator()
    return applicator.apply(notes, template, intensity=intensity)


# =============================================================================
# MODULE TEST
# =============================================================================

if __name__ == '__main__':
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    
    print("=== Groove Templates Module Test ===\n")
    
    # Test preset grooves
    print("Available presets:", list_preset_grooves())
    
    # Get boom_bap groove
    groove = get_preset_groove('boom_bap')
    print(f"\nBoom Bap groove: {groove.name}")
    print(f"  Resolution: {groove.resolution.name}")
    print(f"  Swing: {groove.swing_amount:.2f}")
    print(f"  Points: {len(groove.points)}")
    
    # Test serialization
    groove_dict = groove.to_dict()
    groove_restored = GrooveTemplate.from_dict(groove_dict)
    assert groove_restored.name == groove.name
    assert len(groove_restored.points) == len(groove.points)
    print("  Serialization: OK")
    
    # Test groove application
    test_notes = [
        {'tick': 0, 'velocity': 100, 'note': 36},
        {'tick': 480, 'velocity': 80, 'note': 38},
        {'tick': 960, 'velocity': 100, 'note': 36},
        {'tick': 1440, 'velocity': 80, 'note': 38},
    ]
    
    applicator = GrooveApplicator()
    grooved = applicator.apply(test_notes, groove)
    
    print("\nGroove application test:")
    for orig, new in zip(test_notes, grooved):
        offset = new['tick'] - orig['tick']
        vel_change = new['velocity'] - orig['velocity']
        print(f"  Tick {orig['tick']:4d} -> {new['tick']:4d} (offset: {offset:+3d}), "
              f"Vel {orig['velocity']:3d} -> {new['velocity']:3d} (change: {vel_change:+3d})")
    
    # Test groove removal
    restored = applicator.remove_groove(grooved)
    for orig, rest in zip(test_notes, restored):
        assert orig['tick'] == rest['tick'], "Groove removal failed"
    print("  Groove removal: OK")
    
    # Test genre mapping
    for genre in ['trap', 'lofi', 'g_funk', 'eskista', 'trap_soul']:
        template = get_groove_for_genre(genre)
        if template:
            print(f"\nGenre '{genre}' -> {template.name} (swing: {template.swing_amount:.2f})")
    
    # Test eskista compound meter
    eskista = get_preset_groove('eskista')
    print(f"\nEskista groove:")
    print(f"  Resolution: {eskista.resolution.name} (12 subdivisions)")
    print(f"  First 4 points:")
    for p in eskista.points[:4]:
        print(f"    pos={p.position:.3f}, timing={p.timing_offset_ticks:+3d}, "
              f"vel={p.velocity_offset:+3d}, accent={p.accent:.2f}")
    
    print("\n✅ Groove Templates module test complete!")
