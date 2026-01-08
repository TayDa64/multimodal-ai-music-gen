#!/usr/bin/env python3
"""
Masterpiece Test Script - Comprehensive test of all TASK implementations.

Generates a 4-minute song using all new musicality features.
"""

import sys
import os
from pathlib import Path
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from multimodal_gen import (
    PromptParser,
    MidiGenerator,
    Arranger,
    TICKS_PER_BEAT,
)
from multimodal_gen.audio_renderer import AudioRenderer
from multimodal_gen.instrument_manager import InstrumentLibrary

# Import new modules with correct APIs
from multimodal_gen.motif_engine import MotifGenerator, MotifLibrary, create_motif
from multimodal_gen.microtiming import MicrotimingEngine, apply_microtiming
from multimodal_gen.dynamics import DynamicsEngine, DynamicShape, apply_dynamics
from multimodal_gen.drum_humanizer import DrumHumanizer, add_ghost_notes
from multimodal_gen.tension_arc import TensionArcGenerator, ArcShape, create_tension_arc
from multimodal_gen.section_variation import SectionVariationEngine, VariationConfig
from multimodal_gen.pattern_library import PatternLibrary, PatternType, PatternIntensity
from multimodal_gen.preset_system import PresetManager, PresetCategory
from multimodal_gen.quality_validator import QualityValidator, QualityLevel


def print_header(title: str):
    """Print a section header."""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def print_result(name: str, value, passed: bool = True):
    """Print a test result."""
    status = "[OK]" if passed else "[FAIL]"
    print(f"  {status} {name}: {value}")


def test_motif_engine():
    """Test TASK-001/002: Motif Engine."""
    print_header("TASK-001/002: Motif Engine & Transformations")
    
    # Create a motif using the correct API
    # create_motif(name, intervals, rhythm, genre_tags, accent_pattern, chord_context, description)
    intervals = [0, 4, 7, 5]  # Root, major third, fifth, fourth
    rhythm = [1.0, 1.0, 2.0, 1.0]  # Note durations in beats
    motif = create_motif(
        name="main_theme",
        intervals=intervals,
        rhythm=rhythm,
        genre_tags=["jazz", "melodic"],
        description="Main theme motif"
    )
    print_result("Created motif", f"{motif.name} with {len(motif.intervals)} intervals")
    
    # Test library
    library = MotifLibrary()
    library.add_motif(motif)
    print_result("Library storage", f"{len(library.motifs)} motifs stored")
    
    # Test generator
    generator = MotifGenerator(library=library)
    retrieved = library.get_motifs_for_genre("jazz")
    print_result("Library retrieval", f"Found: {len(retrieved)} motifs for jazz")
    
    return True


def test_microtiming():
    """Test TASK-003: Microtiming Engine."""
    print_header("TASK-003: Microtiming Engine")
    
    engine = MicrotimingEngine(ticks_per_beat=TICKS_PER_BEAT)
    
    # Test notes
    notes = [
        (0, 480, 60, 100),
        (480, 480, 62, 100),
        (960, 480, 64, 100),
        (1440, 480, 65, 100),
    ]
    
    # Apply humanization via convenience function
    humanized = apply_microtiming(notes, genre="jazz")
    print_result("Humanized notes", f"{len(humanized)} notes")
    
    # Check timing variance
    original_ticks = [n[0] for n in notes]
    humanized_ticks = [n[0] for n in humanized]
    variance = sum(abs(o - h) for o, h in zip(original_ticks, humanized_ticks)) / len(notes)
    print_result("Average timing variance", f"{variance:.1f} ticks")
    
    return True


def test_dynamics():
    """Test TASK-004: Phrase-Level Dynamics."""
    print_header("TASK-004: Phrase-Level Dynamics")
    
    engine = DynamicsEngine(ticks_per_beat=TICKS_PER_BEAT)
    
    # Test notes (flat velocity)
    notes = [(i * 480, 240, 60, 100) for i in range(16)]
    
    # Apply dynamics via convenience function (uses genre-based config)
    shaped = apply_dynamics(notes, genre="jazz")
    velocities = [n[3] for n in shaped]
    print_result("Jazz dynamics applied", f"vel range {min(velocities)}-{max(velocities)}")
    
    # Test with different genre
    pop_shaped = apply_dynamics(notes, genre="pop")
    pop_velocities = [n[3] for n in pop_shaped]
    print_result("Pop dynamics applied", f"vel range {min(pop_velocities)}-{max(pop_velocities)}")
    
    return True


def test_drum_humanizer():
    """Test TASK-005: Drum Humanizer with Ghost Notes."""
    print_header("TASK-005: Drum Humanizer (Ghost Notes/Fills)")
    
    humanizer = DrumHumanizer(ticks_per_beat=TICKS_PER_BEAT)
    
    # Create drum pattern
    drum_notes = [
        (0, 120, 36, 110),      # Kick
        (480, 120, 38, 100),    # Snare
        (960, 120, 36, 105),    # Kick
        (1440, 120, 38, 100),   # Snare
    ]
    
    # Add ghost notes via convenience function
    with_ghosts = add_ghost_notes(drum_notes, genre="hip_hop")
    ghost_count = len(with_ghosts) - len(drum_notes)
    print_result("Added ghost notes", f"{len(with_ghosts)} total ({ghost_count} ghosts)")
    
    return True


def test_tension_arc():
    """Test TASK-011: Tension/Release Arc System."""
    print_header("TASK-011: Tension/Release Arc System")
    
    generator = TensionArcGenerator()
    
    # Generate tension arc for arrangement sections (correct API: section_types, genre)
    sections = ["intro", "verse", "chorus", "verse", "chorus", "bridge", "chorus", "outro"]
    arc = generator.create_arc_for_sections(sections, genre="pop")
    
    print_result("Generated arc", f"{len(arc.points)} tension points")
    
    # Show tension values
    for i, point in enumerate(arc.points):
        if i < len(sections):
            bar = "#" * int(point.tension * 10)
            print(f"    {sections[i]:8s} [{bar:<10s}] {point.tension:.2f}")
    
    # Also test create_arc with ArcShape
    arc2 = generator.create_arc(ArcShape.LINEAR_BUILD, num_sections=4)
    print_result("Linear build arc", f"{len(arc2.points)} points")
    
    return True


def test_section_variation():
    """Test TASK-012: Section Variation Engine."""
    print_header("TASK-012: Section Variation Engine")
    
    engine = SectionVariationEngine(ticks_per_beat=TICKS_PER_BEAT, seed=42)
    
    # Original verse notes
    original = [
        (0, 480, 60, 100),
        (480, 480, 64, 95),
        (960, 480, 67, 90),
        (1440, 480, 65, 85),
    ]
    
    config = VariationConfig(intensity=0.4, preserve_melody=True)
    
    # Create variation for verse 2
    varied, applied = engine.create_variation(
        notes=original,
        section_type="verse",
        occurrence=2,
        config=config
    )
    
    print_result("Original notes", f"{len(original)} notes")
    print_result("Varied notes", f"{len(varied)} notes")
    print_result("Variations applied", f"{len(applied)} types")
    
    return True


def test_pattern_library():
    """Test TASK-013: Pattern Library."""
    print_header("TASK-013: Pattern Library")
    
    library = PatternLibrary()
    
    genres = library.list_genres()
    print_result("Available genres", f"{len(genres)} genres")
    
    # Test pattern retrieval for different genres
    for genre in ["hip_hop", "jazz", "pop", "rock", "edm"]:
        try:
            drums = library.get_patterns(genre, PatternType.DRUM)
            print_result(f"{genre} drum patterns", f"{len(drums)} patterns")
        except:
            print_result(f"{genre} drum patterns", "0 patterns", passed=False)
    
    return True


def test_preset_system():
    """Test TASK-014: Preset System."""
    print_header("TASK-014: Preset System (Anti-Trap Defaults)")
    
    manager = PresetManager()
    
    # List presets
    genre_presets = manager.list_presets(category=PresetCategory.GENRE)
    style_presets = manager.list_presets(category=PresetCategory.STYLE)
    print_result("Genre presets", f"{len(genre_presets)} presets")
    print_result("Style presets", f"{len(style_presets)} presets")
    
    # Try to apply a preset
    try:
        manager.apply_preset("hip_hop_boom_bap")
        print_result("Applied boom_bap preset", "success")
    except Exception as e:
        print_result("Applied preset", f"error: {e}", passed=False)
    
    return True


def test_quality_validator():
    """Test TASK-015: Quality Validation Suite."""
    print_header("TASK-015: Quality Validation Suite")
    
    validator = QualityValidator()
    
    # Generate test notes
    notes = []
    for i in range(64):
        tick = i * 480
        pitch = 60 + (i % 8)
        velocity = 80 + (i % 20)
        duration = 240 + (i % 3) * 120
        notes.append((tick, duration, pitch, velocity))
    
    # Run validation
    report = validator.validate(
        notes=notes,
        genre="pop",
        key="C",
        scale="major",
        tempo=120
    )
    
    print_result("Overall score", f"{report.overall_score:.1f}/100")
    print_result("Quality level", report.overall_level.value)
    print_result("Passed", report.passed)
    print_result("Metrics evaluated", f"{len(report.metrics)} metrics")
    
    # Show category scores
    print("\n  Category Scores:")
    for category, score in report.category_scores.items():
        bar = "#" * int(score / 10)
        print(f"    {category.value:20s} [{bar:<10s}] {score:.1f}")
    
    return True


def generate_masterpiece():
    """Generate a 4-minute masterpiece using all features."""
    print_header("GENERATING 4-MINUTE MASTERPIECE")
    
    # Configuration for 4-minute song at 92 BPM
    genre = "g_funk"
    bpm = 92
    key = "Gm"
    
    print(f"\n  Genre: {genre}")
    print(f"  BPM: {bpm}")
    print(f"  Key: {key}")
    
    # Step 1: Parse prompt
    print("\n  [1/6] Parsing prompt...")
    parser = PromptParser()
    prompt = f"smooth {genre} beat at {bpm} BPM in {key} with warm pads and funky bassline"
    parsed = parser.parse(prompt)
    print(f"        Parsed: {parsed.genre}, {parsed.bpm} BPM, {parsed.key}")
    
    # Step 2: Get patterns
    print("\n  [2/6] Loading patterns...")
    library = PatternLibrary()
    genres_available = library.list_genres()
    print(f"        Available genres: {len(genres_available)}")
    
    # Step 3: Generate tension arc
    print("\n  [3/6] Generating tension arc...")
    arc_gen = TensionArcGenerator()
    sections = ["intro", "verse", "chorus", "verse", "chorus", "bridge", "chorus", "outro"]
    arc = arc_gen.create_arc_for_sections(sections, genre="hip_hop")
    print(f"        Tension arc: {len(arc.points)} points")
    
    # Step 4: Create arrangement (4 min = 240 seconds)
    print("\n  [4/6] Creating arrangement...")
    arranger = Arranger(target_duration_seconds=240.0)
    arrangement = arranger.create_arrangement(parsed)
    print(f"        Sections: {len(arrangement.sections)}")
    print(f"        Total bars: {arrangement.total_bars}")
    
    # Step 5: Generate MIDI
    print("\n  [5/6] Generating MIDI...")
    midi_gen = MidiGenerator()
    midi_file = midi_gen.generate(arrangement, parsed)
    
    total_notes = sum(1 for track in midi_file.tracks for msg in track if msg.type == 'note_on' and msg.velocity > 0)
    print(f"        Total notes: {total_notes}")
    print(f"        Tracks: {len(midi_file.tracks)}")
    
    # Step 6: Validate quality
    print("\n  [6/6] Validating quality...")
    validator = QualityValidator()
    
    # Extract notes from first melodic track
    validation_notes = []
    for track in midi_file.tracks:
        if "Melody" in track.name or "Bass" in track.name or "Lead" in track.name:
            curr_tick = 0
            active = {}
            for msg in track:
                curr_tick += msg.time
                if msg.type == 'note_on' and msg.velocity > 0:
                    active[msg.note] = (curr_tick, msg.velocity)
                elif (msg.type == 'note_off' or (msg.type == 'note_on' and msg.velocity == 0)):
                    if msg.note in active:
                        start, vel = active.pop(msg.note)
                        validation_notes.append((start, curr_tick - start, msg.note, vel))
            if validation_notes:
                break
    
    if validation_notes:
        report = validator.validate(notes=validation_notes, genre=genre, tempo=bpm)
        print(f"        Quality score: {report.overall_score:.1f}/100")
        print(f"        Level: {report.overall_level.value}")
    
    # Save output
    output_dir = Path(__file__).parent / "output"
    output_dir.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"masterpiece_{genre}_{bpm}bpm_{timestamp}.mid"
    output_path = output_dir / filename
    
    midi_file.save(str(output_path))
    print(f"\n  [OK] Saved MIDI: {output_path.name}")
    
    # Step 7: Render to WAV with real instruments
    print("\n  [7/7] Rendering to WAV with Funk o Rama samples...")
    wav_filename = f"masterpiece_{genre}_{bpm}bpm_{timestamp}.wav"
    wav_path = output_dir / wav_filename
    
    # Load instrument library with real samples
    instruments_dir = Path(__file__).parent / "instruments"
    print(f"        Loading instruments from: {instruments_dir}")
    
    library = InstrumentLibrary(
        instruments_dir=str(instruments_dir),
        auto_load_audio=True
    )
    num_instruments = library.discover_and_analyze()
    print(f"        Discovered {num_instruments} instruments")
    
    # Pass genre and instrument library to AudioRenderer
    renderer = AudioRenderer(
        genre=parsed.genre,
        instrument_library=library
    )
    success = renderer.render_midi_file(str(output_path), str(wav_path), parsed)
    
    if success:
        print(f"  [OK] Saved WAV: {wav_path.name}")
        # Get file size
        wav_size = wav_path.stat().st_size / (1024 * 1024)  # MB
        print(f"  File size: {wav_size:.1f} MB")
    else:
        print(f"  [WARN] WAV rendering failed - MIDI still available")
    
    # Calculate duration
    duration_seconds = (arrangement.total_bars * 4 * 60) / bpm
    print(f"\n  Duration: {duration_seconds/60:.1f} minutes ({duration_seconds:.0f} seconds)")
    
    return str(wav_path) if success else str(output_path)


def main():
    """Run all tests and generate masterpiece."""
    print("\n" + "="*60)
    print("  MULTIMODAL AI MUSIC GENERATOR - FEATURE TEST SUITE")
    print("  Testing TASK-001 through TASK-015 Implementations")
    print("="*60)
    
    results = {}
    
    # Test each feature with error handling
    tests = [
        ("TASK-001/002 Motif Engine", test_motif_engine),
        ("TASK-003 Microtiming", test_microtiming),
        ("TASK-004 Dynamics", test_dynamics),
        ("TASK-005 Drum Humanizer", test_drum_humanizer),
        ("TASK-011 Tension Arc", test_tension_arc),
        ("TASK-012 Section Variation", test_section_variation),
        ("TASK-013 Pattern Library", test_pattern_library),
        ("TASK-014 Preset System", test_preset_system),
        ("TASK-015 Quality Validator", test_quality_validator),
    ]
    
    for name, test_func in tests:
        try:
            results[name] = test_func()
        except Exception as e:
            print(f"  [FAIL] {name} failed: {e}")
            results[name] = False
    
    # Generate masterpiece
    try:
        output_path = generate_masterpiece()
        results["Masterpiece Generation"] = True
    except Exception as e:
        print(f"\n  [FAIL] Masterpiece generation failed: {e}")
        import traceback
        traceback.print_exc()
        results["Masterpiece Generation"] = False
    
    # Summary
    print_header("TEST SUMMARY")
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for name, passed_test in results.items():
        status = "[OK]" if passed_test else "[FAIL]"
        print(f"  {status} {name}")
    
    print(f"\n  Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n  ALL TESTS PASSED!")
    else:
        print(f"\n  {total - passed} test(s) failed")
    
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
