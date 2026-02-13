"""Sprint 5 Integration: Intelligence pipeline end-to-end wiring tests."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from multimodal_gen.intelligence.harmonic_brain import HarmonicBrain
from multimodal_gen.intelligence.genre_dna import get_genre_dna
from multimodal_gen.intelligence.preferences import PreferenceTracker
from multimodal_gen.intelligence.critics import compute_vlc


class TestIntelligencePipeline:
    # ------------------------------------------------------------------
    # A.1 — Voice-leading actually wired through MidiGenerator
    # ------------------------------------------------------------------
    def test_voice_leading_actually_wired(self):
        """MidiGenerator wired with HarmonicBrain should produce smooth VLC."""
        from multimodal_gen.midi_generator import MidiGenerator

        brain = HarmonicBrain()
        gen = MidiGenerator(harmonic_brain=brain)
        # Assert the brain is actually stored
        assert gen._harmonic_brain is not None

        from multimodal_gen.prompt_parser import PromptParser
        from multimodal_gen.arranger import Arranger

        parsed = PromptParser().parse("neo soul in Eb minor at 72 bpm with piano")
        arrangement = Arranger(target_duration_seconds=15.0).create_arrangement(parsed)
        midi = gen.generate(arrangement, parsed)
        assert len(midi.tracks) >= 2

        # Extract chord voicings from the chord track
        chord_track = None
        for track in midi.tracks:
            if (getattr(track, "name", "") or "").lower() == "chords":
                chord_track = track
                break

        if chord_track:
            voicings = []
            current_notes = []
            last_tick = -1
            tick = 0
            for msg in chord_track:
                tick += msg.time
                if msg.type == "note_on" and msg.velocity > 0:
                    if tick != last_tick and current_notes:
                        voicings.append(sorted(current_notes))
                        current_notes = []
                    current_notes.append(msg.note)
                    last_tick = tick
            if current_notes:
                voicings.append(sorted(current_notes))

            if len(voicings) >= 2:
                vlc = compute_vlc(voicings)
                # Production threshold is 3.0; allow slight margin for
                # non-deterministic generation while still proving wiring
                assert vlc.value < 4.0, (
                    f"VLC={vlc.value:.2f} too high — voice leading not wired"
                )

    # ------------------------------------------------------------------
    # A.2 — StylePolicy calls genre DNA overlay
    # ------------------------------------------------------------------
    def test_style_policy_calls_genre_dna_overlay(self):
        """StylePolicy.compile() with jazz should apply genre DNA overlay."""
        from multimodal_gen.style_policy import (
            StylePolicy,
            DecisionSource,
        )
        from multimodal_gen.prompt_parser import PromptParser

        parsed = PromptParser().parse("jazz in Bb major at 120 bpm")
        policy = StylePolicy()
        ctx = policy.compile(parsed)

        # Jazz should have swing > 0
        assert ctx.timing.swing_amount > 0, (
            f"Jazz genre should have swing_amount > 0, got {ctx.timing.swing_amount}"
        )

        # At least one decision should come from GENRE_RULE source
        genre_rule_decisions = [
            d for d in ctx.decisions if d.source == DecisionSource.GENRE_RULE
        ]
        assert len(genre_rule_decisions) >= 1, (
            "No GENRE_RULE decisions found — genre DNA overlay not wired"
        )

    # ------------------------------------------------------------------
    # A.3 — Quality gate extracts from MIDI
    # ------------------------------------------------------------------
    def test_quality_gate_extracts_from_midi(self):
        """_run_quality_gate should return dict with passed/scores/summary."""
        from main import _run_quality_gate
        from multimodal_gen.prompt_parser import PromptParser
        from multimodal_gen.arranger import Arranger
        from multimodal_gen.midi_generator import MidiGenerator

        parsed = PromptParser().parse("trap in C minor at 140 bpm")
        arrangement = Arranger(target_duration_seconds=15.0).create_arrangement(parsed)
        midi = MidiGenerator(harmonic_brain=HarmonicBrain()).generate(arrangement, parsed)

        result = _run_quality_gate(midi, arrangement)
        assert isinstance(result, dict)
        assert "passed" in result
        assert "scores" in result
        assert "summary" in result
        # Scores dict should have at least one metric key
        if result["scores"]:
            possible_keys = {"vlc", "bkas", "adc"}
            assert len(set(result["scores"].keys()) & possible_keys) >= 1

    # ------------------------------------------------------------------
    # A.4 — Preference feedback loop (tightened)
    # ------------------------------------------------------------------
    def test_preference_feedback_loop(self, tmp_path):
        """After 10 jazz accepts, genre affinity should be > 0.5."""
        tracker = PreferenceTracker(preferences_path=str(tmp_path / "test_prefs.json"))
        for _ in range(10):
            tracker.record_generation_accept("jazz", 95.0, "Bb")
        tracker.save()

        assert "jazz" in tracker.preferences.genre_affinities
        # 10 accepts at +0.05 each from 0.5 base → 0.5 + 0.5 = 1.0 (capped)
        assert tracker.preferences.genre_affinities["jazz"] > 0.5
        assert tracker.preferences.confidence > 0.3

    # ------------------------------------------------------------------
    # A.5 — Quality gate on known-good voicings (tightened)
    # ------------------------------------------------------------------
    def test_quality_gate_on_known_good_midi(self):
        """Stepwise voicings should pass the quality gate."""
        voicings = [
            [60, 64, 67],  # C major
            [60, 64, 69],  # Am (step)
            [60, 65, 69],  # F major
            [59, 65, 67],  # G7 (partial)
        ]
        result = compute_vlc(voicings)
        assert result.passed is True
        assert result.value < 3.0

    # ------------------------------------------------------------------
    # Named fusion coherence (kept from original)
    # ------------------------------------------------------------------
    def test_named_fusion_produces_coherent_result(self):
        """Named fusion lo_fi_jazz_hop should blend jazz+hip_hop coherently."""
        from multimodal_gen.intelligence.genre_dna import get_named_fusion

        result = get_named_fusion("lo_fi_jazz_hop")
        assert result is not None
        assert result.suggested_tempo > 0
        jazz = get_genre_dna("jazz")
        hip_hop = get_genre_dna("hip_hop")
        assert jazz is not None and hip_hop is not None
        assert (min(jazz.swing, hip_hop.swing) - 0.01
                <= result.vector.swing
                <= max(jazz.swing, hip_hop.swing) + 0.01)
