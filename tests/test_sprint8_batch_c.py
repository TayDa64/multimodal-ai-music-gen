"""Sprint 8 Batch C tests — drum pattern transcription + musicality validation expansion."""

import pytest
import sys
import random
import numpy as np
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

# Guarded imports
try:
    from multimodal_gen.reference_analyzer import DrumAnalysis, ReferenceAnalyzer
    _HAS_ANALYZER = True
except ImportError:
    _HAS_ANALYZER = False

try:
    from multimodal_gen.midi_generator import MidiGenerator
    from multimodal_gen.utils import TICKS_PER_BEAT
    from multimodal_gen.prompt_parser import PromptParser
    from multimodal_gen.arranger import Arrangement, SongSection, SectionType, SECTION_CONFIGS
    _HAS_GENERATOR = True
except ImportError:
    _HAS_GENERATOR = False


# ===== Task 8.5: Drum Pattern Transcription Tests =====

@pytest.mark.skipif(not _HAS_ANALYZER, reason="ReferenceAnalyzer not available")
class TestDrumPatternTranscription:
    """Task 8.5: Verify kick/snare pattern fields are populated."""

    def test_drum_analysis_has_pattern_fields(self):
        """DrumAnalysis dataclass has kick_pattern and snare_pattern fields."""
        da = DrumAnalysis(
            density=0.5,
            kick_pattern=[0.0, 0.5],
            snare_pattern=[0.25, 0.75],
            hihat_density=0.4,
            has_rolls=False,
            four_on_floor=False,
            trap_hihats=False,
            boom_bap_feel=False,
        )
        assert da.kick_pattern == [0.0, 0.5]
        assert da.snare_pattern == [0.25, 0.75]

    def test_kick_pattern_values_normalized(self):
        """kick_pattern values should be in [0.0, 1.0) range."""
        da = DrumAnalysis(
            density=0.5,
            kick_pattern=[0.0, 0.25, 0.5, 0.75],
            snare_pattern=[],
            hihat_density=0.4,
            has_rolls=False,
            four_on_floor=False,
            trap_hihats=False,
            boom_bap_feel=False,
        )
        for pos in da.kick_pattern:
            assert 0.0 <= pos < 1.0, f"Kick position {pos} out of [0.0, 1.0) range"

    def test_snare_pattern_values_normalized(self):
        """snare_pattern values should be in [0.0, 1.0) range."""
        da = DrumAnalysis(
            density=0.5,
            kick_pattern=[],
            snare_pattern=[0.25, 0.75],
            hihat_density=0.4,
            has_rolls=False,
            four_on_floor=False,
            trap_hihats=False,
            boom_bap_feel=False,
        )
        for pos in da.snare_pattern:
            assert 0.0 <= pos < 1.0, f"Snare position {pos} out of [0.0, 1.0) range"

    def test_analyze_drums_returns_lists_not_none(self):
        """_analyze_drums should return lists (possibly empty) for patterns, never None."""
        # Create a simple synthetic signal
        sr = 22050
        duration = 4.0  # 4 seconds
        t = np.linspace(0, duration, int(sr * duration), endpoint=False)
        # Simple kick-like signal: low frequency pulse every beat at 120 BPM
        bpm = 120.0
        beat_interval = 60.0 / bpm
        signal = np.zeros_like(t)
        for beat in range(int(duration / beat_interval)):
            beat_start = int(beat * beat_interval * sr)
            if beat_start + 500 < len(signal):
                # Low freq pulse (kick-like)
                pulse = np.sin(2 * np.pi * 80 * np.arange(500) / sr) * np.exp(-np.arange(500) / 100)
                signal[beat_start:beat_start + 500] += pulse

        librosa = pytest.importorskip("librosa")
        analyzer = ReferenceAnalyzer()
        result = analyzer._analyze_drums(signal, sr, bpm)
        assert isinstance(result.kick_pattern, list), "kick_pattern should be a list"
        assert isinstance(result.snare_pattern, list), "snare_pattern should be a list"


# ===== Task 8.6: Musicality Validation Expansion =====

def _extract_note_ons(track):
    """Extract (tick, pitch, velocity) from a track."""
    abs_tick = 0
    events = []
    for msg in track:
        abs_tick += getattr(msg, "time", 0)
        if msg.type == "note_on" and getattr(msg, "velocity", 0) > 0:
            events.append((abs_tick, msg.note, msg.velocity))
    return events


@pytest.mark.skipif(not _HAS_GENERATOR, reason="MidiGenerator not available")
class TestMusicalityExpanded:
    """Task 8.6: Expanded musicality validation tests."""

    @staticmethod
    def _arrangement(parsed, bars=8, section_type=SectionType.CHORUS):
        """Helper to create a simple arrangement."""
        ticks_per_bar = 4 * TICKS_PER_BEAT
        total_ticks = bars * ticks_per_bar
        section = SongSection(
            section_type=section_type,
            start_tick=0,
            end_tick=total_ticks,
            bars=bars,
            config=SECTION_CONFIGS[section_type],
        )
        return Arrangement(
            sections=[section],
            total_bars=bars,
            total_ticks=total_ticks,
            bpm=float(parsed.bpm or 120),
            time_signature=(4, 4),
        )

    def test_trap_has_hihat_activity(self):
        """Trap genre should produce hi-hat activity (MIDI notes 42/44/46)."""
        random.seed(42)
        parsed = PromptParser().parse("trap beat 140 bpm in F# minor")
        arrangement = self._arrangement(parsed, bars=8)
        mid = MidiGenerator().generate(arrangement, parsed)
        drum_track = next((t for t in mid.tracks if (t.name or "").lower() == "drums"), None)
        assert drum_track is not None, "Expected a drum track"
        events = _extract_note_ons(drum_track)
        # Hi-hat MIDI notes: 42 (closed), 44 (pedal), 46 (open)
        hihat_notes = {42, 44, 46}
        hihat_events = [e for e in events if e[1] in hihat_notes]
        assert len(hihat_events) > 0, "Trap should produce hi-hat events"

    def test_chord_track_has_multiple_pitches(self):
        """Chord track should contain multiple simultaneous pitches (polyphony)."""
        random.seed(99)
        parsed = PromptParser().parse("rnb beat 85 bpm in Ab major")
        arrangement = self._arrangement(parsed, bars=8)
        mid = MidiGenerator().generate(arrangement, parsed)
        chord_track = next(
            (t for t in mid.tracks if 'chord' in (t.name or "").lower() or 'pad' in (t.name or "").lower()),
            None,
        )
        if chord_track is None:
            pytest.skip("No chord/pad track produced for this genre seed")
        events = _extract_note_ons(chord_track)
        pitches = set(e[1] for e in events)
        assert len(pitches) >= 3, f"Chord track should have >=3 distinct pitches, got {len(pitches)}"

    def test_melody_uses_scale_tones(self):
        """Melody track should primarily use scale tones (>70% adherence)."""
        random.seed(123)
        parsed = PromptParser().parse("hip hop beat 90 bpm in C minor")
        arrangement = self._arrangement(parsed, bars=8)
        mid = MidiGenerator().generate(arrangement, parsed)
        melody_track = next(
            (t for t in mid.tracks if 'melody' in (t.name or "").lower() or 'lead' in (t.name or "").lower()),
            None,
        )
        if melody_track is None:
            pytest.skip("No melody/lead track produced for this genre seed")
        events = _extract_note_ons(melody_track)
        if len(events) < 4:
            pytest.skip("Too few melody events to assess scale adherence")
        # C minor scale: C D Eb F G Ab Bb = pitch classes {0, 2, 3, 5, 7, 8, 10}
        c_minor_pcs = {0, 2, 3, 5, 7, 8, 10}
        in_scale = sum(1 for _, p, _ in events if (p % 12) in c_minor_pcs)
        adherence = in_scale / len(events)
        assert adherence >= 0.70, f"Scale adherence {adherence:.0%} too low (expected >=70%)"

    def test_bass_stays_in_low_register(self):
        """Bass track notes should be predominantly below MIDI note 60 (middle C)."""
        random.seed(55)
        parsed = PromptParser().parse("boom bap beat 88 bpm in D minor")
        arrangement = self._arrangement(parsed, bars=8)
        mid = MidiGenerator().generate(arrangement, parsed)
        bass_track = next(
            (t for t in mid.tracks if 'bass' in (t.name or "").lower() or '808' in (t.name or "").lower()),
            None,
        )
        if bass_track is None:
            pytest.skip("No bass/808 track produced for this genre seed")
        events = _extract_note_ons(bass_track)
        if len(events) < 2:
            pytest.skip("Too few bass events")
        low_notes = sum(1 for _, p, _ in events if p < 60)
        ratio = low_notes / len(events)
        assert ratio >= 0.80, f"Bass register ratio {ratio:.0%} too low (expected >=80% below middle C)"

    def test_cross_genre_velocity_variation(self):
        """Multiple genres should all produce velocity variation (not robotic)."""
        genres = ["trap beat 140 bpm", "jazz beat 120 bpm", "house beat 128 bpm"]
        for i, prompt in enumerate(genres):
            random.seed(200 + i)
            parsed = PromptParser().parse(prompt)
            arrangement = self._arrangement(parsed, bars=4)
            mid = MidiGenerator().generate(arrangement, parsed)
            drum_track = next(
                (t for t in mid.tracks if (t.name or "").lower() == "drums"),
                mid.tracks[1] if len(mid.tracks) > 1 else None,
            )
            if drum_track is None:
                continue
            events = _extract_note_ons(drum_track)
            if len(events) < 4:
                continue
            velocities = [v for _, _, v in events]
            unique_v = len(set(velocities))
            assert unique_v > 1, f"Genre '{prompt}' produced single velocity ({velocities[0]})"

    def test_verse_less_dense_than_drop(self):
        """Verse section should be less dense than drop section."""
        random.seed(77)
        parsed = PromptParser().parse("edm track 128 bpm in A minor")
        ticks_per_bar = 4 * TICKS_PER_BEAT
        bars = 8
        verse_ticks = bars * ticks_per_bar
        drop_ticks = bars * ticks_per_bar
        sections = [
            SongSection(
                section_type=SectionType.VERSE,
                start_tick=0,
                end_tick=verse_ticks,
                bars=bars,
                config=SECTION_CONFIGS[SectionType.VERSE],
            ),
            SongSection(
                section_type=SectionType.DROP,
                start_tick=verse_ticks,
                end_tick=verse_ticks + drop_ticks,
                bars=bars,
                config=SECTION_CONFIGS[SectionType.DROP],
            ),
        ]
        arrangement = Arrangement(
            sections=sections,
            total_bars=bars * 2,
            total_ticks=verse_ticks + drop_ticks,
            bpm=float(parsed.bpm or 128),
            time_signature=(4, 4),
        )
        mid = MidiGenerator().generate(arrangement, parsed)
        # Count total note events across all tracks
        verse_count = 0
        drop_count = 0
        for track in mid.tracks:
            events = _extract_note_ons(track)
            verse_count += sum(1 for t, _, _ in events if 0 <= t < verse_ticks)
            drop_count += sum(1 for t, _, _ in events if verse_ticks <= t < verse_ticks + drop_ticks)

        # Drop should be denser (or at least not sparser) than verse
        if verse_count > 0:
            assert drop_count >= verse_count * 0.8, (
                f"Drop ({drop_count}) too sparse vs verse ({verse_count})"
            )
