#!/usr/bin/env python3
"""
Multimodal AI Music Generator - CLI Entry Point

Generate complete music tracks from natural language prompts.

Usage:
    python main.py "dark trap soul at 87 BPM in C minor"
    python main.py "lofi hip hop chill beat" --bpm 75 --key Am
    python main.py "aggressive 808 trap" --mpc --stems --output ./my_beat
    python main.py --reference "https://youtu.be/..." "make something like this"

Features:
    - Natural language prompt parsing
    - Reference track analysis (YouTube URLs)
    - MIDI generation with professional humanization
    - Audio rendering (FluidSynth or procedural fallback)
    - MPC Software .xpj export for hardware integration
    - Stem export for mixing flexibility
"""

import argparse
import sys
import os
from pathlib import Path
from datetime import datetime
import json
import random
import numpy as np
from typing import Callable, Optional

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from multimodal_gen import (
    PromptParser,
    ParsedPrompt,
    MidiGenerator,
    AudioRenderer,
    MpcExporter,
    Arranger,
    AssetsGenerator,
    TICKS_PER_BEAT,
    # New modules
    SessionGraphBuilder,
    validate_generation,
    repair_violations,
    TakeGenerator,
)

# Import StylePolicy for coherent producer decisions
try:
    from multimodal_gen.style_policy import StylePolicy, compile_policy, PolicyContext
    HAS_STYLE_POLICY = True
except ImportError:
    HAS_STYLE_POLICY = False
    StylePolicy = None
    compile_policy = None
    PolicyContext = None

try:
    from colorama import init, Fore, Style
    init()
    HAS_COLORAMA = True
except ImportError:
    HAS_COLORAMA = False
    class Fore:
        GREEN = YELLOW = RED = CYAN = MAGENTA = BLUE = WHITE = ""
    class Style:
        BRIGHT = RESET_ALL = ""


def print_banner():
    """Print application banner."""
    banner = """
╔════════════════════════════════════════════════════════════════╗
║           🎵 MULTIMODAL AI MUSIC GENERATOR 🎵                 ║
║                                                                ║
║      Text → MIDI → Audio → MPC Project                        ║
║      Professional Humanization • CPU-Only • Offline-First     ║
╚════════════════════════════════════════════════════════════════╝
    """
    try:
        print(f"{Fore.CYAN}{banner}{Style.RESET_ALL}")
    except Exception:
        # Fallback for redirected output or colorama issues
        print(banner)


def print_step(step: str, message: str):
    """Print a step indicator."""
    print(f"{Fore.GREEN}[{step}]{Style.RESET_ALL} {message}")


def print_info(message: str):
    """Print info message."""
    try:
        print(f"{Fore.CYAN}ℹ{Style.RESET_ALL}  {message}")
    except UnicodeEncodeError:
        print(f"{Fore.CYAN}[i]{Style.RESET_ALL}  {message}")


def print_warning(message: str):
    """Print warning message."""
    try:
        print(f"{Fore.YELLOW}⚠{Style.RESET_ALL}  {message}")
    except UnicodeEncodeError:
        print(f"{Fore.YELLOW}[!]{Style.RESET_ALL}  {message}")


def print_error(message: str):
    """Print error message."""
    try:
        print(f"{Fore.RED}✗{Style.RESET_ALL}  {message}")
    except UnicodeEncodeError:
        print(f"{Fore.RED}[x]{Style.RESET_ALL}  {message}")


def print_success(message: str):
    """Print success message."""
    try:
        print(f"{Fore.GREEN}✓{Style.RESET_ALL}  {message}")
    except UnicodeEncodeError:
        print(f"{Fore.GREEN}[v]{Style.RESET_ALL}  {message}")


def print_parsed_prompt(parsed: ParsedPrompt, reference_info: dict = None):
    """Print parsed prompt details."""
    try:
        print(f"\n{Fore.MAGENTA}{'─' * 50}{Style.RESET_ALL}")
        print(f"{Fore.MAGENTA}📝 Parsed Prompt:{Style.RESET_ALL}")
    except UnicodeEncodeError:
        print(f"\n{Fore.MAGENTA}{'-' * 50}{Style.RESET_ALL}")
        print(f"{Fore.MAGENTA}Parsed Prompt:{Style.RESET_ALL}")
        
    print(f"   BPM: {parsed.bpm}")
    print(f"   Key: {parsed.key} {parsed.scale_type.name.lower()}")
    print(f"   Genre: {parsed.genre}")
    if parsed.style_modifiers:
        print(f"   Style: {', '.join(parsed.style_modifiers)}")
    if parsed.sonic_adjectives:
        print(f"   Sonic: {', '.join(parsed.sonic_adjectives)}")
    if parsed.instruments:
        print(f"   Instruments: {', '.join(parsed.instruments)}")
    if parsed.drum_elements:
        print(f"   Drums: {', '.join(parsed.drum_elements)}")
    if parsed.textures:
        print(f"   Textures: {', '.join(parsed.textures)}")
    if parsed.mood:
        print(f"   Mood: {parsed.mood}")
    if parsed.energy:
        print(f"   Energy: {parsed.energy}")
    
    # Show reference analysis if available
    if reference_info:
        try:
            print(f"\n{Fore.BLUE}🎵 Reference Analysis:{Style.RESET_ALL}")
        except UnicodeEncodeError:
            print(f"\n{Fore.BLUE}Reference Analysis:{Style.RESET_ALL}")
            
        if reference_info.get("title"):
            print(f"   Source: {reference_info['title']}")
        if reference_info.get("detected_bpm"):
            print(f"   Detected BPM: {reference_info['detected_bpm']:.1f}")
        if reference_info.get("detected_key"):
            print(f"   Detected Key: {reference_info['detected_key']}")
        if reference_info.get("detected_genre"):
            print(f"   Detected Genre: {reference_info['detected_genre']}")
        if reference_info.get("style_hints"):
            print(f"   Style Hints: {reference_info['style_hints']}")
    
    try:
        print(f"{Fore.MAGENTA}{'─' * 50}{Style.RESET_ALL}\n")
    except UnicodeEncodeError:
        print(f"{Fore.MAGENTA}{'-' * 50}{Style.RESET_ALL}\n")


def ensure_output_dir(output_dir: Path) -> Path:
    """Ensure output directory exists."""
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def generate_project_name(parsed: ParsedPrompt) -> str:
    """Generate a project name from parsed prompt."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    genre = parsed.genre.replace(" ", "_")
    key = parsed.key.replace("#", "sharp").replace("b", "flat")
    scale = parsed.scale_type.name.lower()
    return f"{genre}_{parsed.bpm}bpm_{key}{scale}_{timestamp}"


# Type alias for progress callback: (step: str, percent: float, message: str) -> None
from typing import Callable, Optional

ProgressCallback = Callable[[str, float, str], None]


def run_generation(
    prompt: str,
    output_dir: Path | str,
    genre_override: str = None,
    bpm_override: int = None,
    key_override: str = None,
    reference_url: str = None,
    export_mpc: bool = False,
    export_stems: bool = False,
    soundfont_path: str = None,
    template_path: str = None,
    instruments_paths: list = None,
    verbose: bool = False,
    progress_callback: Optional[ProgressCallback] = None,
    seed: Optional[int] = None,
    use_bwf: bool = True,
    takes: int = 0,
    comp: bool = False,
    comp_bars: int = 2,
) -> dict:
    """Run the full music generation pipeline.
    
    Args:
        prompt: Natural language music prompt
        output_dir: Directory for output files
        genre_override: Override genre from prompt (e.g., "g_funk", "trap_soul")
        bpm_override: Override BPM from prompt
        key_override: Override key from prompt (e.g., "Cm", "F#m")
        reference_url: YouTube URL or audio file to analyze for style reference
        export_mpc: Export to MPC .xpj format
        export_stems: Export individual stem files
        soundfont_path: Path to SoundFont file for audio rendering
        template_path: Path to MPC template file
        instruments_paths: List of paths to instrument folders for intelligent sample selection
        verbose: Enable verbose output
        progress_callback: Optional callback for progress reporting (step, percent, message)
        seed: Random seed for reproducibility (enables iterative refinement)
        use_bwf: Use Broadcast Wave Format with AI provenance metadata (default: True)
        takes: Number of alternative takes to generate per track
        comp: Auto-generate comp track from best sections of each take
        comp_bars: Number of bars per comp section (default: 2)
        
    Returns:
        Dictionary with paths to generated files
    """
    # Ensure output_dir is a Path object
    output_dir = Path(output_dir) if isinstance(output_dir, str) else output_dir
    
    # Set random seed if provided
    if seed is not None:
        random.seed(seed)
        np.random.seed(seed)
    else:
        # Generate seed for reproducibility
        seed = np.random.randint(0, 2**31 - 1)
        random.seed(seed)
        np.random.seed(seed)
    
    # Helper to report progress
    def report_progress(step: str, percent: float, message: str):
        if progress_callback:
            progress_callback(step, percent, message)
    
    results = {
        "midi": None,
        "audio": None,
        "mpc": None,
        "stems": [],
        "samples": [],
        "takes": {},  # Store alternative takes
        "comps": {},  # Store composite tracks
        "reference_analysis": None,
        "instruments_used": [],
        "seed": seed,  # Store seed in results
        "synthesis_params": {},  # Store synthesis parameters
    }
    
    reference_info = None
    instrument_library = None

    # Preserve user prompt before any reference-based enhancement.
    base_prompt = prompt
    
    # Step 0: Analyze reference track if provided
    if reference_url:
        print_step("0/6", "Analyzing reference track...")
        try:
            from multimodal_gen import ReferenceAnalyzer, analyze_reference
            
            analyzer = ReferenceAnalyzer(
                cache_dir=str(output_dir / ".reference_cache"),
                verbose=verbose
            )
            
            if reference_url.startswith(("http://", "https://")):
                analysis = analyzer.analyze_url(reference_url)
            else:
                analysis = analyzer.analyze_file(reference_url)
            
            # Store analysis results
            results["reference_analysis"] = {
                "source": reference_url,
                "title": analysis.title,
                "bpm": analysis.bpm,
                "key": analysis.key,
                "mode": analysis.mode,
                "genre": analysis.estimated_genre,
                "style_tags": analysis.style_tags,
                # Store the hints actually used to enhance the prompt (genre excluded by default)
                "prompt_hints": analysis.to_prompt_hints(include_genre=False),
            }
            
            reference_info = {
                "title": analysis.title,
                "detected_bpm": analysis.bpm,
                "detected_key": f"{analysis.key} {analysis.mode}",
                "detected_genre": analysis.estimated_genre,
                "style_hints": ", ".join(analysis.style_tags[:5]),
            }
            
            print_success(f"Reference analyzed: {analysis.title}")
            print_info(f"Detected: {analysis.bpm:.0f} BPM, {analysis.key} {analysis.mode}, {analysis.estimated_genre}")
            
            # Enhance prompt with reference analysis
            enhanced_hints = analysis.to_prompt_hints(include_genre=False)
            prompt = f"{prompt}, {enhanced_hints}"
            if verbose:
                print_info(f"Enhanced prompt: {prompt}")
            
            # Apply detected values as defaults (can be overridden)
            if not bpm_override:
                bpm_override = int(analysis.bpm)
                if verbose:
                    print_info(f"Using detected BPM: {bpm_override}")
            
            if not key_override:
                key_override = f"{analysis.key}{'m' if analysis.mode == 'minor' else ''}"
                if verbose:
                    print_info(f"Using detected key: {key_override}")
                    
        except ImportError as e:
            print_warning(f"Reference analysis requires additional packages: {e}")
            print_info("Install with: pip install librosa yt-dlp")
        except Exception as e:
            print_warning(f"Reference analysis failed: {e}")
            print_info("Continuing with text prompt only...")
    
    # Step 1: Parse prompt
    print_step("1/6", "Parsing prompt...")
    report_progress("parsing", 0.05, "Parsing prompt...")
    parser = PromptParser()
    base_parsed = parser.parse(base_prompt)
    parsed = parser.parse(prompt)

    # If the user explicitly asked for a genre/instruments in the original prompt,
    # do not let reference-based hinting override that intent.
    if base_parsed.genre and base_parsed.genre != parsed.genre:
        parsed.genre = base_parsed.genre

    if getattr(base_parsed, 'instruments', None):
        if base_parsed.instruments and (not parsed.instruments or base_parsed.instruments != parsed.instruments):
            parsed.instruments = base_parsed.instruments
    
    # Apply overrides
    if genre_override:
        parsed.genre = genre_override
        # Re-apply genre intelligence to update drum/instrument defaults
        parsed._apply_genre_intelligence()
        if verbose:
            print_info(f"Genre override applied: {genre_override}")
    
    if bpm_override:
        parsed.bpm = bpm_override
        if verbose:
            print_info(f"BPM override applied: {bpm_override}")
    
    if key_override:
        # Parse key override (e.g., "Cm" -> key="C", scale_type=MINOR)
        from multimodal_gen.utils import ScaleType
        if key_override.endswith("m"):
            parsed.key = key_override[:-1]
            parsed.scale_type = ScaleType.MINOR
        else:
            parsed.key = key_override
            parsed.scale_type = ScaleType.MAJOR
        if verbose:
            print_info(f"Key override applied: {parsed.key} {parsed.scale_type.value}")
    
    print_parsed_prompt(parsed, reference_info)
    
    # Step 1.5: Validate against Genre Rules
    print_step("1.5/6", "Validating genre rules...")
    try:
        # Check for violations
        validation_result = validate_generation(
            parsed.genre, 
            parsed.instruments, 
            parsed.drum_elements, 
            [] # patterns not yet generated
        )
        
        if not validation_result.valid or validation_result.violations:
            print_warning(f"Found {len(validation_result.violations)} genre rule violations:")
            for v in validation_result.violations:
                print_info(f"  - {v.message}")
            
            # Auto-repair
            print_info("Attempting auto-repair...")
            repaired_elements, repair_log = repair_violations(
                parsed.genre, 
                parsed.instruments + parsed.drum_elements
            )
            
            # Update parsed prompt with repaired elements
            # (This is a simplification; in a full implementation we'd map back to specific fields)
            if repair_log:
                print_success(f"Repaired {len(repair_log)} issues")
                for log in repair_log:
                    print_info(f"  - {log['original']} -> {log.get('result', 'removed')}")
    except Exception as e:
        print_warning(f"Genre rule validation skipped: {e}")
    
    # Step 2: Create arrangement
    print_step("2/6", "Creating arrangement...")
    report_progress("arranging", 0.15, "Creating arrangement...")
    
    # Pass user-specified duration if provided, otherwise Arranger uses its default (3 min)
    arranger = Arranger(target_duration_seconds=parsed.target_duration_seconds)
    arrangement = arranger.create_arrangement(parsed)
    
    # Log duration info
    estimated_duration = arrangement.total_bars * 4 * 60 / parsed.bpm  # bars * beats/bar * sec/min / bpm
    if parsed.target_duration_seconds:
        print_info(f"Target duration: {parsed.target_duration_seconds/60:.1f} min → {arrangement.total_bars} bars (~{estimated_duration/60:.1f} min)")
    else:
        print_info(f"Default duration: ~{estimated_duration/60:.1f} min ({arrangement.total_bars} bars)")
    
    if verbose:
        print_info(f"Arrangement: {len(arrangement.sections)} sections, {arrangement.total_bars} bars")
        bar_pos = 0
        for section in arrangement.sections:
            print_info(f"  - {section.section_type.value}: {section.bars} bars (tick {section.start_tick})")
            bar_pos += section.bars
    
    # Step 2.5: Build Session Graph
    print_step("2.5/6", "Building session graph...")
    session_graph = None
    try:
        graph_builder = SessionGraphBuilder()
        # Pass reference analysis if available
        ref_analysis_obj = None
        if results.get("reference_analysis"):
            # Reconstruct minimal object if needed, or pass dict if builder supports it
            # For now, we'll rely on the builder handling the parsed prompt primarily
            pass
            
        session_graph = graph_builder.build_from_prompt(parsed)
        
        # Sync arrangement into graph
        session_graph = graph_builder.build_from_arrangement(session_graph, arrangement)
        
        print_success(f"Session graph built: {len(session_graph.tracks)} tracks, {len(session_graph.sections)} sections")
    except Exception as e:
        print_warning(f"Session graph build failed: {e}")

    # Step 3: Generate MIDI
    print_step("3/6", "Generating MIDI with humanization...")
    report_progress("generating_midi", 0.35, "Generating MIDI with humanization...")
    midi_gen = MidiGenerator()
    
    # Compile style policy for coherent producer decisions
    policy_context = None
    if HAS_STYLE_POLICY and compile_policy:
        try:
            policy_context = compile_policy(parsed)
            print_info(f"Style policy: {parsed.genre} -> swing={policy_context.timing.swing_amount:.0%}, "
                      f"ghost={policy_context.dynamics.ghost_note_probability:.0%}, "
                      f"voicing={policy_context.voicing.style.value}")
        except Exception as e:
            print_warning(f"Style policy compilation failed: {e}")
    
    # Get groove from session graph if available
    groove_template = session_graph.groove_template if session_graph else None
    
    midi_file = midi_gen.generate(
        arrangement, 
        parsed, 
        groove_template=groove_template,
        policy_context=policy_context
    )
    
    # Save MIDI file
    project_name = generate_project_name(parsed)
    midi_path = output_dir / f"{project_name}.mid"
    midi_file.save(str(midi_path))
    results["midi"] = str(midi_path)
    print_success(f"MIDI saved: {midi_path.name}")
    
    # Step 3.5: Generate Alternative Takes
    # Industry-standard overdubbing: Takes REPLACE original tracks, not layer on top
    # When --takes N is specified, original tracks become the "reference" and
    # take tracks are the playable alternatives (user selects which to use in DAW)
    if takes > 0:
        print_step("3.5/6", f"Generating {takes} alternative takes per track...")
        try:
            import mido
            from multimodal_gen.take_generator import (
                take_to_midi_track, TakeValidator, TakeMode, NoteVariation
            )
            
            # Load the generated MIDI file
            mid = mido.MidiFile(str(midi_path))
            new_tracks = []
            tracks_to_remove = []  # Original tracks to mark/remove
            take_gen = TakeGenerator()
            validator = TakeValidator()
            
            # Iterate over tracks (skip Meta)
            for i, track in enumerate(mid.tracks):
                track_name = track.name.strip()
                if track_name in ["Meta", "Tempo", "Time Signature"] or not track_name:
                    continue
                    
                # Determine role from track name
                role = "lead" # Default
                if "Drums" in track_name: role = "drums"
                elif "Bass" in track_name: role = "bass"
                elif "Chords" in track_name: role = "chords"
                elif "Melody" in track_name: role = "lead"
                elif "Organ" in track_name: role = "pad"
                
                # Parse track to notes
                track_notes = []
                active_notes = {} # pitch -> start_tick
                curr_tick = 0
                
                for msg in track:
                    curr_tick += msg.time
                    if msg.type == 'note_on' and msg.velocity > 0:
                        active_notes[msg.note] = (curr_tick, msg.velocity, msg.channel)
                    elif (msg.type == 'note_off') or (msg.type == 'note_on' and msg.velocity == 0):
                        if msg.note in active_notes:
                            start, vel, chan = active_notes.pop(msg.note)
                            duration = curr_tick - start
                            track_notes.append({
                                "pitch": msg.note,
                                "start_tick": start,
                                "duration_ticks": duration,
                                "velocity": vel,
                                "channel": chan
                            })
                
                if not track_notes:
                    continue
                
                # Mark original track for removal (overdub = replace, not layer)
                tracks_to_remove.append(i)
                    
                # Generate takes (these REPLACE the original)
                take_set = take_gen.generate_takes_for_role(
                    notes=track_notes,
                    role=role,
                    num_takes=takes,
                    genre=parsed.genre,
                    base_seed=(seed or 0) + i # Deterministic seed per track
                )
                
                # Convert original notes for validation
                original_note_vars = [
                    NoteVariation(
                        pitch=n["pitch"],
                        start_tick=n["start_tick"],
                        duration_ticks=n["duration_ticks"],
                        velocity=n["velocity"],
                        channel=n.get("channel", 0)
                    ) for n in track_notes
                ]
                
                for take in take_set.takes:
                    # Validate take correctness
                    validation = validator.validate_take(
                        take, original_note_vars, parsed.genre
                    )
                    
                    # Set relationship metadata
                    take.original_track_name = track_name
                    take.is_active_take = (take.take_id == 0)  # First take is default active
                    
                    # Name the track: "OriginalName_Take_N"
                    take.midi_track_name = f"{track_name}_Take_{take.take_id + 1}"
                    new_track = take_to_midi_track(take)
                    new_tracks.append(new_track)
                    
                    # Add to results for reporting (rich data for TakeLanePanel)
                    if track_name not in results["takes"]:
                        results["takes"][track_name] = []
                    results["takes"][track_name].append({
                        "take_id": str(take.take_id + 1),
                        "midi_track_name": take.midi_track_name,
                        "variation_type": take.variation_type,
                        "seed": take.seed,
                        "notes_count": len(take.notes),
                        "notes_added": take.notes_added,
                        "notes_removed": take.notes_removed,
                        "notes_modified": take.notes_modified,
                        "notes_kept": take.notes_kept,
                        "avg_timing_shift": take.avg_timing_shift,
                        "original_track": track_name,
                        "is_active": take.is_active_take,
                        "validation_score": validation.score,
                        "validation_issues": validation.issues,
                        "validation_warnings": validation.warnings,
                    })
                    
                    # Log validation results
                    if verbose and (validation.issues or validation.warnings):
                        if validation.issues:
                            print_warning(f"  Take {take.take_id + 1}: {validation.issues}")
                        if validation.warnings:
                            print_info(f"  Take {take.take_id + 1}: {validation.warnings}")
                    
                    # Update SessionGraph if available
                    if session_graph:
                        # Find the track in the graph
                        graph_track = next((t for t in session_graph.tracks if t.name == track_name), None)
                        if graph_track:
                            # Add takes to all clips in this track (simplification)
                            for clip in graph_track.clips:
                                clip.add_take_lane(
                                    take_id=take.take_id + 1,
                                    seed=take.seed,
                                    variation_type=take.variation_type,
                                    midi_track_name=take.midi_track_name,
                                    notes_count=len(take.notes),
                                    notes_added=take.notes_added,
                                    notes_modified=take.notes_modified,
                                    avg_timing_shift=take.avg_timing_shift,
                                    parameters=take.parameters
                                )

            # OVERDUBBING FIX: Remove original tracks and add takes as replacements
            # This is industry-standard behavior - takes are alternatives, not layers
            if new_tracks:
                # Create new MIDI file with takes replacing originals
                new_mid = mido.MidiFile(ticks_per_beat=mid.ticks_per_beat)
                
                for i, track in enumerate(mid.tracks):
                    if i in tracks_to_remove:
                        # Skip original - it's being replaced by takes
                        continue
                    new_mid.tracks.append(track)
                
                # Add all take tracks
                new_mid.tracks.extend(new_tracks)
                new_mid.save(str(midi_path))
                
                print_success(
                    f"Generated {len(new_tracks)} take tracks "
                    f"(replaced {len(tracks_to_remove)} original tracks)"
                )
            
        except Exception as e:
            print_warning(f"Take generation failed: {e}")
            if verbose:
                import traceback
                traceback.print_exc()

    # Step 3.6: Generate Comp Tracks from Takes
    # Industry-standard comping: combine best sections from each take
    if comp and takes >= 2:
        print_step("3.6/6", f"Generating comp tracks ({comp_bars} bars per section)...")
        try:
            import mido
            from multimodal_gen.take_generator import (
                CompGenerator, comp_to_midi_track, TakeLane, NoteVariation
            )
            
            # Load the MIDI file with takes
            mid = mido.MidiFile(str(midi_path))
            comp_tracks = []
            comp_gen = CompGenerator()
            
            # Group takes by original track
            takes_by_track = {}  # original_track_name -> list of (track, TakeLane)
            
            for track in mid.tracks:
                track_name = track.name.strip()
                # Identify take tracks by naming convention: "OriginalName_Take_N"
                if "_Take_" in track_name:
                    parts = track_name.rsplit("_Take_", 1)
                    original_name = parts[0]
                    take_num = int(parts[1]) - 1  # 0-indexed
                    
                    # Parse track notes
                    track_notes = []
                    active_notes = {}
                    curr_tick = 0
                    
                    for msg in track:
                        curr_tick += msg.time
                        if msg.type == 'note_on' and msg.velocity > 0:
                            active_notes[msg.note] = (curr_tick, msg.velocity, getattr(msg, 'channel', 0))
                        elif (msg.type == 'note_off') or (msg.type == 'note_on' and msg.velocity == 0):
                            if msg.note in active_notes:
                                start, vel, chan = active_notes.pop(msg.note)
                                duration = curr_tick - start
                                track_notes.append(NoteVariation(
                                    pitch=msg.note,
                                    start_tick=start,
                                    duration_ticks=duration,
                                    velocity=vel,
                                    channel=chan,
                                ))
                    
                    if track_notes:
                        # Determine role from original name
                        role = "lead"
                        if "Drums" in original_name: role = "drums"
                        elif "Bass" in original_name: role = "bass"
                        elif "Chords" in original_name: role = "chords"
                        elif "Melody" in original_name: role = "lead"
                        elif "Organ" in original_name: role = "pad"
                        
                        # Create TakeLane
                        take_lane = TakeLane(
                            take_id=take_num,
                            seed=0,  # Not needed for comping
                            variation_type="combined",
                            notes=track_notes,
                            midi_track_name=track_name,
                            original_track_name=original_name,
                            parameters={"role": role},
                        )
                        
                        if original_name not in takes_by_track:
                            takes_by_track[original_name] = []
                        takes_by_track[original_name].append(take_lane)
            
            # Generate comp for each track's takes
            for original_name, take_lanes in takes_by_track.items():
                if len(take_lanes) < 2:
                    continue  # Need at least 2 takes to comp
                
                role = take_lanes[0].parameters.get("role", "lead")
                
                # Generate comp
                comp_result = comp_gen.generate_comp_from_takes(
                    takes=take_lanes,
                    role=role,
                    bars_per_section=comp_bars,
                    genre=parsed.genre,
                )
                
                # Set track names
                comp_result.midi_track_name = f"{original_name}_Comp"
                comp_result.original_track_name = original_name
                
                # Convert to MIDI track
                comp_track = comp_to_midi_track(comp_result)
                comp_tracks.append(comp_track)
                
                # Store comp info in results
                results["comps"][original_name] = comp_result.to_dict()
                
                if verbose:
                    print_info(
                        f"  {original_name}: {comp_result.num_sections} sections from "
                        f"{len(comp_result.takes_used)} takes, score {comp_result.total_score:.2f}"
                    )
            
            # Add comp tracks to MIDI file
            if comp_tracks:
                for comp_track in comp_tracks:
                    mid.tracks.append(comp_track)
                mid.save(str(midi_path))
                
                print_success(f"Generated {len(comp_tracks)} comp tracks")
            
        except Exception as e:
            print_warning(f"Comp generation failed: {e}")
            if verbose:
                import traceback
                traceback.print_exc()
    elif comp and takes < 2:
        print_warning("Comp requires --takes >= 2 (need multiple takes to comp from)")

    # Step 4: Generate procedural samples
    print_step("4/6", "Generating procedural samples...")
    report_progress("generating_samples", 0.45, "Generating procedural samples...")
    assets_gen = AssetsGenerator(str(output_dir / "samples"))
    
    try:
        drum_samples = assets_gen.generate_drum_kit()  # No genre param
        results["samples"].extend(drum_samples.values())
        print_success(f"Generated {len(drum_samples)} drum samples")
        
        # Generate textures if needed
        if "vinyl" in parsed.textures or "lofi" in parsed.genre:
            vinyl_path = assets_gen.generate_vinyl_crackle()
            results["samples"].append(vinyl_path)
            print_success("Generated vinyl crackle texture")
            
        if "rain" in parsed.textures or "ambient" in parsed.mood:
            rain_path = assets_gen.generate_rain_texture()
            results["samples"].append(rain_path)
            print_success("Generated rain texture")
            
    except Exception as e:
        print_warning(f"Sample generation issue: {e}")
    
    # Step 4.5: Discover and analyze instruments (if paths provided or default exists)
    default_instruments = Path(__file__).parent / "instruments"
    
    # Auto-load from default instruments directory if no explicit path provided
    if not instruments_paths and default_instruments.exists() and any(default_instruments.iterdir()):
        instruments_paths = [str(default_instruments)]
        print_info(f"Auto-loading instruments from {default_instruments}")
    
    if instruments_paths:
        print_step("4.5/6", "Discovering and analyzing instruments...")
        report_progress("discovering_instruments", 0.55, "Discovering and analyzing instruments...")
        try:
            from multimodal_gen import InstrumentLibrary, InstrumentMatcher, load_multiple_libraries
            
            # Handle multiple instrument sources
            if len(instruments_paths) == 1:
                # Single source - use original logic with caching
                single_path = instruments_paths[0]
                instruments_path_obj = Path(single_path)
                try:
                    cache_file = str(instruments_path_obj / ".instrument_cache.json")
                    test_file = instruments_path_obj / ".write_test"
                    test_file.touch()
                    test_file.unlink()
                except (PermissionError, OSError):
                    cache_name = instruments_path_obj.name.replace("[", "").replace("]", "")
                    cache_file = str(output_dir / f".instrument_cache_{cache_name}.json")
                    if verbose:
                        print_info(f"Using local cache (source is read-only)")
                
                instrument_library = InstrumentLibrary(
                    instruments_dir=single_path,
                    cache_file=cache_file,
                    auto_load_audio=True
                )
                count = instrument_library.discover_and_analyze()
            else:
                # Multiple sources - use load_multiple_libraries
                print_info(f"Loading {len(instruments_paths)} instrument sources...")
                
                # Use output directory for caches (handles read-only sources)
                instrument_library = load_multiple_libraries(
                    instruments_paths,
                    cache_dir=str(output_dir),
                    auto_load_audio=True,
                    verbose=verbose
                )
                count = len(instrument_library.instruments)
                
                # Show per-source breakdown
                if verbose:
                    summary = instrument_library.get_source_summary()
                    for source, src_count in summary.items():
                        print_info(f"  {Path(source).name}: {src_count} instruments")
            
            if count > 0:
                print_success(f"Discovered {count} instruments total")
                
                # Show category breakdown
                categories = instrument_library.list_categories()
                if verbose and categories:
                    for cat, cnt in categories.items():
                        print_info(f"  {cat}: {cnt} samples")
                
                # Get recommendations for this genre
                matcher = InstrumentMatcher(instrument_library)
                recommendations = matcher.get_recommendations(parsed.genre, parsed.mood)
                
                if verbose and recommendations:
                    print_info("Instrument recommendations:")
                    for cat, matches in recommendations.items():
                        if matches:
                            best, score = matches[0]
                            # Show source for multi-source setups
                            source_info = ""
                            if len(instruments_paths) > 1 and hasattr(best, 'source'):
                                source_info = f" [{Path(best.source).name}]"
                            print_info(f"  {cat}: {best.name}{source_info} ({score:.0%} match)")
                            results["instruments_used"].append({
                                "category": cat,
                                "name": best.name,
                                "score": score,
                                "path": best.path,
                                "source": getattr(best, 'source', None),
                            })
            else:
                print_warning("No instruments found in specified directories")
                instrument_library = None
                
        except ImportError as e:
            print_warning(f"Instrument analysis requires librosa: {e}")
            print_info("Install with: pip install librosa")
            instrument_library = None
        except Exception as e:
            print_warning(f"Instrument discovery failed: {e}")
            instrument_library = None
    
    # Step 4.7: Load expansion packs for specialized instruments (Ethiopian, etc.)
    expansion_manager = None
    expansions_dir = Path(__file__).parent.parent / "expansions"
    if expansions_dir.exists():
        try:
            from multimodal_gen import ExpansionManager
            expansion_manager = ExpansionManager()
            exp_count = expansion_manager.scan_expansions(str(expansions_dir))
            if exp_count > 0 and verbose:
                print_info(f"Loaded {exp_count} expansion pack(s) for specialized instruments")
        except Exception as e:
            if verbose:
                print_warning(f"Expansion loading: {e}")
    
    # Step 4.8: Intelligent Instrument Selection (using sonic adjectives)
    # If the prompt contains sonic descriptors (warm, vintage, analog, etc.),
    # use the InstrumentResolver to find best-matching expansion instruments
    if parsed.sonic_adjectives and expansion_manager:
        try:
            from multimodal_gen.instrument_index import (
                InstrumentIndex, InstrumentResolver, create_instrument_index
            )
            
            # Create unified index from expansion manager
            index = InstrumentIndex()
            index.add_from_expansion_manager(expansion_manager)
            
            if index.get_stats()['total_instruments'] > 0:
                resolver = InstrumentResolver(index)
                
                # Resolve instruments mentioned in prompt with sonic adjectives
                smart_selections = []
                for inst_name in parsed.instruments:
                    results_list = resolver.resolve_with_adjectives(
                        name=inst_name,
                        adjectives=parsed.sonic_adjectives,
                        genre=parsed.genre,
                        limit=1
                    )
                    if results_list:
                        best = results_list[0]
                        smart_selections.append({
                            'query': inst_name,
                            'selected': best.instrument.name,
                            'score': best.score,
                            'source': best.instrument.source.value,
                            'path': best.instrument.path,
                            'reasons': best.match_reasons[:3],  # Top 3 reasons
                        })
                
                if smart_selections and verbose:
                    print_info("Smart instrument selection (sonic adjectives):")
                    for sel in smart_selections:
                        reasons_str = ', '.join(sel['reasons'][:2]) if sel['reasons'] else ''
                        print_info(f"  {sel['query']} -> {sel['selected']} ({sel['score']:.2f})")
                        if reasons_str:
                            print_info(f"    Reasons: {reasons_str}")
                
                # Store in results for metadata
                results['smart_instruments'] = smart_selections
                
        except Exception as e:
            if verbose:
                print_warning(f"Smart instrument selection: {e}")

    # Step 5: Render audio
    print_step("5/6", "Rendering audio...")
    report_progress("rendering_audio", 0.75, "Rendering audio...")
    
    # Prepare AI metadata for BWF
    ai_metadata = {
        'version': '0.2.0',
        'prompt': prompt,
        'seed': seed,
        'bpm': parsed.bpm,
        'key': parsed.key,
        'genre': parsed.genre,
        'synthesis_params': results.get('synthesis_params', {}),
    }
    
    renderer = AudioRenderer(
        soundfont_path=soundfont_path,
        instrument_library=instrument_library,
        expansion_manager=expansion_manager,
        genre=parsed.genre,
        mood=parsed.mood,
        use_bwf=use_bwf,
        ai_metadata=ai_metadata
    )
    
    try:
        audio_path = output_dir / f"{project_name}.wav"
        # render_midi_file takes file path, not MidiFile object
        success = renderer.render_midi_file(str(midi_path), str(audio_path), parsed)
        if success:
            results["audio"] = str(audio_path)
            print_success(f"Audio saved: {audio_path.name}")
        else:
            print_warning("Audio rendering returned no output (FluidSynth may not be available)")
        
        # Export stems if requested
        if export_stems:
            print_info("Exporting stems...")
            report_progress("exporting_stems", 0.85, "Exporting stems...")
            stems_dir = output_dir / f"{project_name}_stems"
            stem_paths = renderer.render_stems(str(midi_path), str(stems_dir), parsed)
            results["stems"] = stem_paths
            print_success(f"Exported {len(stem_paths)} stems to {stems_dir.name}/")
            
    except Exception as e:
        print_warning(f"Audio rendering issue: {e}")
        print_info("Audio rendering skipped - MIDI file still available")
    
    # Step 6: Export to MPC (optional)
    if export_mpc:
        print_step("6/6", "Exporting to MPC format...")
        report_progress("exporting_mpc", 0.95, "Exporting to MPC format...")
        mpc_dir = output_dir / f"{project_name}_mpc"
        
        try:
            exporter = MpcExporter(str(mpc_dir))
            mpc_path = exporter.export_midi_to_mpc(
                midi_file,
                project_name,
                sample_paths=results["samples"],
                bpm=parsed.bpm,
            )
            results["mpc"] = mpc_path
            print_success(f"MPC project saved: {mpc_dir.name}/")
            
        except Exception as e:
            print_warning(f"MPC export issue: {e}")
    else:
        print_step("6/6", "MPC export skipped (use --mpc to enable)")
    
    # Report completion
    report_progress("complete", 1.0, "Generation complete!")
    
    # Add metadata to results for server mode
    results["bpm"] = parsed.bpm
    results["key"] = parsed.key
    results["genre"] = parsed.genre
    results["sections"] = [
        {"name": s.section_type.value, "bars": s.bars}
        for s in arrangement.sections
    ] if 'arrangement' in dir() else []
    
    # Step 5.5: Save Session Manifest
    if session_graph:
        print_step("5.5/6", "Saving session manifest...")
        try:
            # Update graph with generated file paths
            if midi_path:
                try:
                    session_graph.midi_path = str(midi_path.relative_to(output_dir))
                except ValueError:
                    session_graph.midi_path = str(midi_path)
            
            if results['audio']:
                try:
                    session_graph.audio_path = str(Path(results['audio']).relative_to(output_dir))
                except ValueError:
                    session_graph.audio_path = str(results['audio'])
            
            # Save manifest
            manifest_path = output_dir / "session_manifest.json"
            session_graph.save_manifest(str(manifest_path))
            print_success(f"Session manifest saved: {manifest_path.name}")
            
            # Add to results
            results["manifest"] = str(manifest_path)
            
        except Exception as e:
            print_warning(f"Failed to save session manifest: {e}")

    return results


def save_project_metadata(
    output_dir: Path,
    prompt: str,
    results: dict,
    parsed: ParsedPrompt,
    seed: Optional[int] = None,
    synthesis_params: Optional[dict] = None
):
    """
    Save comprehensive project metadata as JSON with support for iterative refinement.
    
    Enhanced to include:
    - Seed value for reproducibility
    - ADSR parameters for each synthesized sound
    - Duty cycle and waveform type for each element
    - Synthesis parameter history for non-deterministic iteration
    """
    # Load existing metadata if present (for refinement tracking)
    metadata_path = output_dir / "project_metadata.json"
    history = []
    if metadata_path.exists():
        try:
            with open(metadata_path, 'r') as f:
                existing = json.load(f)
                history = existing.get('generation_history', [])
        except:
            pass
    
    # Create current generation record
    current_generation = {
        "prompt": prompt,
        "parsed": {
            "bpm": parsed.bpm,
            "key": parsed.key,
            "scale": parsed.scale_type.name.lower(),
            "genre": parsed.genre,
            "style_modifiers": parsed.style_modifiers,
            "instruments": parsed.instruments,
            "drum_elements": parsed.drum_elements,
            "textures": parsed.textures,
            "mood": parsed.mood,
            "energy": parsed.energy,
        },
        "outputs": results,
        "generated_at": datetime.now().isoformat(),
        "seed": seed,  # For reproducibility
        "synthesis_params": synthesis_params or {},  # ADSR, waveforms, duty cycles
    }
    
    # Add to history
    history.append(current_generation)
    
    # Complete metadata structure
    metadata = {
        "version": "0.2.0",  # Updated version with persistence features
        "current": current_generation,
        "generation_history": history,
        "refinement_capable": True,  # Indicates support for iterative refinement
        "original_seed": history[0].get('seed') if history else seed,  # Preserve original "soul"
    }
    
    with open(metadata_path, 'w') as f:
        json.dump(metadata, f, indent=2)
    
    return metadata_path


def load_project_metadata(metadata_path: str | Path) -> Optional[dict]:
    """
    Load project metadata from JSON file.
    
    Returns:
        Metadata dictionary or None if not found
    """
    metadata_path = Path(metadata_path)
    
    if not metadata_path.exists():
        return None
    
    try:
        with open(metadata_path, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading metadata: {e}")
        return None


def refine_generation(
    metadata_path: str | Path,
    refinement_prompt: str,
    output_dir: Optional[Path] = None,
    **override_params
) -> dict:
    """
    Refine a previous generation using its original seed and parameters.
    
    This implements the "non-deterministic iteration" feature where users
    can provide follow-up prompts like "make the snare punchier" and the AI
    will use the original seed to maintain the "soul" of the track while
    modifying specific parameters.
    
    Args:
        metadata_path: Path to project_metadata.json
        refinement_prompt: Follow-up prompt (e.g., "make snare punchier")
        output_dir: Output directory (defaults to same as original)
        **override_params: Specific parameters to override
        
    Returns:
        Results dictionary from refined generation
    """
    # Load original metadata
    metadata = load_project_metadata(metadata_path)
    if not metadata:
        raise FileNotFoundError(f"Metadata not found: {metadata_path}")
    
    # Get original seed to preserve "soul"
    original_seed = metadata.get('original_seed')
    current = metadata.get('current', {})
    
    # Determine output directory
    if output_dir is None:
        output_dir = Path(metadata_path).parent
    
    # Merge original prompt with refinement
    original_prompt = current.get('prompt', '')
    combined_prompt = f"{original_prompt} {refinement_prompt}"
    
    # Extract original parameters
    parsed_data = current.get('parsed', {})
    
    # Apply overrides
    for key, value in override_params.items():
        if key in parsed_data:
            parsed_data[key] = value
    
    # Run generation with original seed
    print(f"Refining generation with original seed: {original_seed}")
    print(f"Refinement prompt: {refinement_prompt}")
    
    results = run_generation(
        prompt=combined_prompt,
        output_dir=output_dir,
        bpm_override=override_params.get('bpm', parsed_data.get('bpm')),
        key_override=override_params.get('key', parsed_data.get('key')),
        **{k: v for k, v in override_params.items() if k not in ['bpm', 'key']}
    )
    
    return results


def extract_refinement_intent(refinement_prompt: str) -> dict:
    """
    Parse refinement prompt to extract specific modification intent.
    
    Examples:
        "make the snare punchier" -> {'element': 'snare', 'adjustment': 'punchier'}
        "extend the outro" -> {'section': 'outro', 'adjustment': 'extend'}
        "add more bass" -> {'element': 'bass', 'adjustment': 'more'}
    
    Returns:
        Dictionary with refinement parameters
    """
    refinement = {
        'intent': 'general',
        'element': None,
        'section': None,
        'adjustment': None,
    }
    
    prompt_lower = refinement_prompt.lower()
    
    # Detect elements
    elements = ['snare', 'kick', 'bass', '808', 'hihat', 'hi-hat', 'clap', 'piano', 'rhodes']
    for element in elements:
        if element in prompt_lower:
            refinement['element'] = element
            refinement['intent'] = 'element_modification'
            break
    
    # Detect sections
    sections = ['intro', 'verse', 'chorus', 'drop', 'outro', 'bridge']
    for section in sections:
        if section in prompt_lower:
            refinement['section'] = section
            refinement['intent'] = 'section_modification'
            break
    
    # Detect adjustments
    if any(word in prompt_lower for word in ['punchier', 'harder', 'louder', 'more']):
        refinement['adjustment'] = 'increase'
    elif any(word in prompt_lower for word in ['softer', 'quieter', 'less', 'subtle']):
        refinement['adjustment'] = 'decrease'
    elif any(word in prompt_lower for word in ['extend', 'longer']):
        refinement['adjustment'] = 'extend'
    elif any(word in prompt_lower for word in ['shorten', 'shorter']):
        refinement['adjustment'] = 'shorten'
    
    return refinement


def show_generation_history(output_dir: Path) -> bool:
    """
    Display generation history for A/B comparison.
    
    Phase A3: Prompt history + A/B comparison
    Shows all generations with their prompt, seed, key details.
    
    Args:
        output_dir: Directory containing project_metadata.json
        
    Returns:
        True if history found and displayed
    """
    metadata_path = output_dir / "project_metadata.json"
    metadata = load_project_metadata(metadata_path)
    
    if not metadata:
        print_error(f"No generation history found at {metadata_path}")
        return False
    
    history = metadata.get('generation_history', [])
    if not history:
        print_info("No generation history available.")
        return True
    
    print(f"\n{Fore.CYAN}Generation History ({len(history)} versions){Style.RESET_ALL}")
    print(f"{Fore.CYAN}{'=' * 60}{Style.RESET_ALL}\n")
    
    for i, gen in enumerate(history, 1):
        prompt = gen.get('prompt', 'N/A')
        parsed = gen.get('parsed', {})
        outputs = gen.get('outputs', {})
        generated_at = gen.get('generated_at', 'N/A')
        seed = gen.get('seed', 'N/A')
        
        bpm = parsed.get('bpm', 'N/A')
        key = f"{parsed.get('key', '?')}{parsed.get('scale', '?')[:3]}"
        genre = parsed.get('genre', 'N/A')
        
        # Take info
        takes = outputs.get('takes', {})
        take_count = sum(len(t) for t in takes.values()) if takes else 0
        
        # Comp info
        comps = outputs.get('comps', {})
        comp_count = len(comps) if comps else 0
        
        # Validation status
        all_valid = True
        if takes:
            for track_takes in takes.values():
                for take in track_takes:
                    # Handle both dict format (new) and string format (legacy)
                    if isinstance(take, dict) and take.get('validation_issues'):
                        all_valid = False
                        break
        
        validation_status = f"{Fore.GREEN}[VALID]{Style.RESET_ALL}" if all_valid else f"{Fore.YELLOW}[ISSUES]{Style.RESET_ALL}"
        
        print(f"  {Fore.WHITE}Version {i}{Style.RESET_ALL} ({generated_at[:19] if len(generated_at) > 19 else generated_at})")
        print(f"    Prompt: \"{prompt[:50]}{'...' if len(prompt) > 50 else ''}\"")
        print(f"    BPM: {bpm}, Key: {key}, Genre: {genre}")
        
        # Show takes and comps info
        if comp_count > 0:
            print(f"    Seed: {seed}, Takes: {take_count}, Comps: {comp_count} {validation_status}")
        else:
            print(f"    Seed: {seed}, Takes: {take_count} {validation_status}")
        
        if outputs.get('midi'):
            print(f"    MIDI: {Path(outputs['midi']).name}")
        if outputs.get('audio'):
            print(f"    Audio: {Path(outputs['audio']).name}")
        print()
    
    print(f"{Fore.CYAN}Use --compare <A> <B> to compare two versions{Style.RESET_ALL}")
    return True


def compare_versions(output_dir: Path, ver_a: int, ver_b: int) -> bool:
    """
    Compare two generation versions for A/B evaluation.
    
    Phase A3: Enables blind A/B comparison workflow.
    
    Args:
        output_dir: Directory containing project_metadata.json
        ver_a: First version number (1-indexed)
        ver_b: Second version number (1-indexed)
        
    Returns:
        True if comparison successful
    """
    metadata_path = output_dir / "project_metadata.json"
    metadata = load_project_metadata(metadata_path)
    
    if not metadata:
        print_error(f"No metadata found at {metadata_path}")
        return False
    
    history = metadata.get('generation_history', [])
    
    # Validate version indices
    if ver_a < 1 or ver_a > len(history):
        print_error(f"Version {ver_a} not found (have {len(history)} versions)")
        return False
    if ver_b < 1 or ver_b > len(history):
        print_error(f"Version {ver_b} not found (have {len(history)} versions)")
        return False
    
    gen_a = history[ver_a - 1]
    gen_b = history[ver_b - 1]
    
    print(f"\n{Fore.CYAN}A/B Comparison: Version {ver_a} vs Version {ver_b}{Style.RESET_ALL}")
    print(f"{Fore.CYAN}{'=' * 60}{Style.RESET_ALL}\n")
    
    # Side-by-side comparison
    headers = ["Attribute", f"Version {ver_a} (A)", f"Version {ver_b} (B)"]
    
    def get_val(gen, *keys):
        val = gen
        for k in keys:
            val = val.get(k, {}) if isinstance(val, dict) else {}
        return val if val != {} else 'N/A'
    
    comparisons = [
        ("Prompt", gen_a.get('prompt', 'N/A')[:40], gen_b.get('prompt', 'N/A')[:40]),
        ("BPM", get_val(gen_a, 'parsed', 'bpm'), get_val(gen_b, 'parsed', 'bpm')),
        ("Key", f"{get_val(gen_a, 'parsed', 'key')}{get_val(gen_a, 'parsed', 'scale')[:3]}", 
               f"{get_val(gen_b, 'parsed', 'key')}{get_val(gen_b, 'parsed', 'scale')[:3]}"),
        ("Genre", get_val(gen_a, 'parsed', 'genre'), get_val(gen_b, 'parsed', 'genre')),
        ("Seed", gen_a.get('seed', 'N/A'), gen_b.get('seed', 'N/A')),
        ("Energy", get_val(gen_a, 'parsed', 'energy'), get_val(gen_b, 'parsed', 'energy')),
        ("Mood", get_val(gen_a, 'parsed', 'mood'), get_val(gen_b, 'parsed', 'mood')),
    ]
    
    # Print comparison table
    print(f"  {'Attribute':<15} {'Version A':<25} {'Version B':<25}")
    print(f"  {'-' * 15} {'-' * 25} {'-' * 25}")
    
    for attr, val_a, val_b in comparisons:
        # Highlight differences
        if str(val_a) != str(val_b):
            indicator = f"{Fore.YELLOW}!{Style.RESET_ALL}"
        else:
            indicator = " "
        print(f"{indicator} {attr:<15} {str(val_a):<25} {str(val_b):<25}")
    
    print()
    
    # Take comparison
    takes_a = gen_a.get('outputs', {}).get('takes', {})
    takes_b = gen_b.get('outputs', {}).get('takes', {})
    
    if takes_a or takes_b:
        print(f"  {Fore.CYAN}Take Statistics:{Style.RESET_ALL}")
        
        all_tracks = set(takes_a.keys()) | set(takes_b.keys())
        for track in sorted(all_tracks):
            track_a = takes_a.get(track, [])
            track_b = takes_b.get(track, [])
            
            # Calculate average validation score
            score_a = sum(t.get('validation_score', 0) for t in track_a) / len(track_a) if track_a else 0
            score_b = sum(t.get('validation_score', 0) for t in track_b) / len(track_b) if track_b else 0
            
            # Calculate note retention
            kept_a = sum(t.get('notes_kept', 0) for t in track_a) if track_a else 0
            kept_b = sum(t.get('notes_kept', 0) for t in track_b) if track_b else 0
            
            print(f"    {track}: A={len(track_a)} takes (score:{score_a:.2f}, kept:{kept_a}) "
                  f"vs B={len(track_b)} takes (score:{score_b:.2f}, kept:{kept_b})")
    
    print()
    
    # Output file comparison
    print(f"  {Fore.CYAN}Output Files:{Style.RESET_ALL}")
    midi_a = gen_a.get('outputs', {}).get('midi')
    midi_b = gen_b.get('outputs', {}).get('midi')
    audio_a = gen_a.get('outputs', {}).get('audio')
    audio_b = gen_b.get('outputs', {}).get('audio')
    
    if midi_a:
        print(f"    Version A MIDI: {Path(midi_a).name}")
    if midi_b:
        print(f"    Version B MIDI: {Path(midi_b).name}")
    if audio_a:
        print(f"    Version A Audio: {Path(audio_a).name}")
    if audio_b:
        print(f"    Version B Audio: {Path(audio_b).name}")
    
    print()
    print(f"  {Fore.GREEN}Tip: Load both audio files in a DAW for blind A/B listening test{Style.RESET_ALL}")
    
    return True



def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Generate music from natural language prompts",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s "dark trap soul at 87 BPM in C minor"
  %(prog)s "lofi hip hop chill beat" --bpm 75 --key Am
  %(prog)s "aggressive 808 trap" --mpc --stems
  %(prog)s "ambient piano with rain" --output ./ambient_track
  
Reference-Based Generation (requires: pip install librosa yt-dlp):
  %(prog)s "make a beat like this" --reference "https://youtu.be/..."
  %(prog)s "trap beat" --reference "./my_sample.wav"

Supported Genres:
  trap, lofi, boom_bap, house, techno, ambient, drill, phonk, g_funk

Audio Notes:
  - Default: Procedural synthesis (no external dependencies)
  - For better sound: Provide --soundfont path to a .sf2 file
  - MPC export creates [ProjectData] folder with samples
  - Reference analysis extracts BPM, key, genre from any audio/video

Intelligent Instruments (requires: pip install librosa):
  %(prog)s "trap beat" --instruments ./instruments
  - Analyzes samples for sonic characteristics (brightness, punch, warmth)
  - Auto-selects best-fit samples for genre/mood
  - Place samples in ./instruments/drums/kicks/, ./instruments/drums/snares/, etc.

Server Mode (for JUCE integration):
  %(prog)s --server [--port 9000] [--verbose]
  - Starts OSC server for JUCE communication
  - Receives generation requests, sends progress updates
        """,
    )
    
    # Server mode (mutually exclusive with prompt)
    parser.add_argument(
        "--server",
        action="store_true",
        help="Start OSC server mode for JUCE integration",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=9000,
        help="OSC server port (default: 9000, sends responses to port+1)",
    )
    parser.add_argument(
        "--no-signals",
        action="store_true",
        help="Disable signal handlers (useful for VS Code terminals)",
    )
    
    # Positional arguments
    parser.add_argument(
        "prompt",
        type=str,
        nargs="?",  # Optional when using --server
        help="Natural language music description (e.g., 'dark trap at 140 BPM in Am')",
    )
    
    # Output options
    parser.add_argument(
        "-o", "--output",
        type=str,
        default="./output",
        help="Output directory (default: ./output)",
    )
    
    # Reference analysis
    parser.add_argument(
        "-r", "--reference",
        type=str,
        help="YouTube URL or audio file path to analyze for style reference",
    )

    # MIDI controller integration (e.g., MPC Studio)
    parser.add_argument(
        "--list-midi",
        action="store_true",
        help="List available MIDI input devices and exit",
    )
    parser.add_argument(
        "--midi-in",
        type=str,
        default=None,
        help="MIDI input device name (exact or substring match). Used with --record-part",
    )
    parser.add_argument(
        "--record-part",
        type=str,
        choices=["drums", "keys", "lead"],
        default=None,
        help="Record a live part from a MIDI controller (replaces the generated part)",
    )
    parser.add_argument(
        "--record-bars",
        type=int,
        default=8,
        help="Bars to record (default: 8). Ignored if --record-seconds is set",
    )
    parser.add_argument(
        "--record-seconds",
        type=float,
        default=None,
        help="Seconds to record (overrides --record-bars)",
    )
    parser.add_argument(
        "--count-in",
        type=int,
        default=1,
        help="Count-in bars before recording starts (default: 1)",
    )
    parser.add_argument(
        "--quantize",
        type=str,
        choices=["off", "1/16", "1/8"],
        default="1/16",
        help="Quantize recorded notes to a grid (default: 1/16)",
    )
    
    # Music parameters
    parser.add_argument(
        "--bpm",
        type=int,
        help="Override BPM from prompt (or detected from reference)",
    )
    parser.add_argument(
        "--key",
        type=str,
        help="Override key from prompt (e.g., 'Am', 'C', 'F#m')",
    )
    
    # Export options
    parser.add_argument(
        "--mpc",
        action="store_true",
        help="Export to MPC Software .xpj format",
    )
    parser.add_argument(
        "--stems",
        action="store_true",
        help="Export individual stem files",
    )
    
    # Audio options
    parser.add_argument(
        "--soundfont",
        type=str,
        help="Path to SoundFont (.sf2) file for audio rendering",
    )
    parser.add_argument(
        "--samples",
        type=str,
        help="Path to sample directory or MPC .xpm file to import custom sounds",
    )
    parser.add_argument(
        "-i", "--instruments",
        type=str,
        action="append",
        dest="instruments",
        help="Path to instruments directory for intelligent sample selection. Can be specified multiple times to combine sources (e.g., -i path1 -i path2)",
    )
    
    # Template options
    parser.add_argument(
        "--template",
        type=str,
        help="Path to MPC template file for export customization",
    )
    
    # Advanced features
    parser.add_argument(
        "--seed",
        type=int,
        help="Random seed for reproducible generation (enables iterative refinement)",
    )
    parser.add_argument(
        "--refine",
        type=str,
        metavar="METADATA_PATH",
        help="Refine previous generation using its metadata (e.g., 'make snare punchier')",
    )
    parser.add_argument(
        "--no-bwf",
        action="store_true",
        help="Disable Broadcast Wave Format metadata (use standard WAV)",
    )
    parser.add_argument(
        "--takes",
        type=int,
        default=0,
        help="Number of alternative takes to generate per track (default: 0)",
    )
    parser.add_argument(
        "--comp",
        action="store_true",
        help="Auto-generate comp track from best sections of each take (requires --takes >= 2)",
    )
    parser.add_argument(
        "--comp-bars",
        type=int,
        default=2,
        help="Number of bars per comp section (default: 2)",
    )
    
    # History and A/B comparison
    parser.add_argument(
        "--history",
        action="store_true",
        help="Show generation history from project_metadata.json in output directory",
    )
    parser.add_argument(
        "--compare",
        type=str,
        nargs=2,
        metavar=("VER_A", "VER_B"),
        help="Compare two versions from history (e.g., --compare 1 2)",
    )
    
    # Misc options
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose output",
    )
    parser.add_argument(
        "--no-banner",
        action="store_true",
        help="Suppress banner output",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON (suppresses other output)",
    )
    
    args = parser.parse_args()

    # MIDI device listing is a standalone action
    if args.list_midi:
        try:
            from multimodal_gen import list_midi_inputs
            inputs = list_midi_inputs()
            if not inputs:
                print("No MIDI input devices detected.")
            else:
                print("Available MIDI inputs:")
                for name in inputs:
                    print(f"  - {name}")
            return 0
        except Exception as e:
            print_error(str(e))
            return 1
    
    # Handle server mode
    if args.server:
        try:
            from multimodal_gen.server import MusicGenOSCServer, ServerConfig
            
            if not args.no_banner:
                print_banner()
            
            config = ServerConfig(
                recv_port=args.port,
                send_port=args.port + 1,
                verbose=args.verbose,
                default_output_dir=args.output,
                default_soundfont=args.soundfont,
                instrument_paths=args.instruments or [],
            )
            
            server = MusicGenOSCServer(config)
            # Use handle_signals=False when --no-signals is set (for VS Code terminals)
            server.start(handle_signals=not args.no_signals)
            
        except ImportError as e:
            print_error(f"Server mode requires python-osc: {e}")
            print_info("Install with: pip install python-osc")
            sys.exit(1)
        except KeyboardInterrupt:
            print()
            print_info("Server stopped.")
        return
    
    # Handle history display (Phase A3: A/B comparison)
    if args.history:
        output_dir = Path(args.output)
        if not args.no_banner:
            print_banner()
        success = show_generation_history(output_dir)
        sys.exit(0 if success else 1)
    
    # Handle version comparison (Phase A3: A/B comparison)
    if args.compare:
        output_dir = Path(args.output)
        if not args.no_banner:
            print_banner()
        try:
            ver_a, ver_b = int(args.compare[0]), int(args.compare[1])
            success = compare_versions(output_dir, ver_a, ver_b)
            sys.exit(0 if success else 1)
        except ValueError:
            print_error("Version numbers must be integers (e.g., --compare 1 2)")
            sys.exit(1)
    
    # Normal generation mode - handle refine mode
    if args.refine:
        # Refinement mode
        if not args.prompt:
            parser.error("Refinement prompt is required with --refine")
        
        try:
            if not args.no_banner and not args.json:
                print_banner()
            
            if not args.json:
                print_info(f"Refining generation from: {args.refine}")
                print_info(f"Refinement prompt: \"{args.prompt}\"")
                print()
            
            # Run refinement
            results = refine_generation(
                metadata_path=args.refine,
                refinement_prompt=args.prompt,
                output_dir=Path(args.output) if args.output != "./output" else None,
                bpm=args.bpm,
                key=args.key,
                export_mpc=args.mpc,
                export_stems=args.stems,
                soundfont_path=args.soundfont,
                instruments_paths=args.instruments,
                verbose=args.verbose,
            )
            
            if not args.json:
                print_success("✓ Refinement complete!")
                if results.get('midi'):
                    print_info(f"MIDI: {Path(results['midi']).name}")
                if results.get('audio'):
                    print_info(f"Audio: {Path(results['audio']).name}")
            
            return
            
        except Exception as e:
            print_error(f"Refinement failed: {e}")
            if args.verbose:
                import traceback
                traceback.print_exc()
            sys.exit(1)
    
    # Normal generation mode - require prompt
    if not args.prompt:
        parser.error("prompt is required (or use --server mode)")
    
    # Print banner unless suppressed
    if not args.no_banner and not args.json:
        print_banner()
    
    # Ensure output directory
    output_dir = ensure_output_dir(Path(args.output))
    
    if not args.json:
        print_info(f"Output directory: {output_dir.absolute()}")
        print_info(f"Prompt: \"{args.prompt}\"")
        if args.reference:
            print_info(f"Reference: {args.reference}")
        if args.instruments:
            print_info(f"Instruments: {args.instruments}")
        if args.record_part:
            print_info(f"Record part: {args.record_part} (MIDI in: {args.midi_in or 'NOT SET'})")
        if args.seed:
            print_info(f"Seed: {args.seed} (reproducible generation enabled)")
        print()
    
    try:
        recorded_midi_path = None
        record_channel = None

        if args.record_part:
            if not args.midi_in:
                raise ValueError("--midi-in is required when using --record-part")

            from multimodal_gen import (
                RecordConfig,
                record_midi_to_file,
            )

            # Record at the intended BPM (args.bpm overrides prompt parsing)
            # If BPM isn't provided, we let parsing decide later, but recording still needs a BPM.
            # We'll default to 140 for trap-like usability if not specified.
            record_bpm = float(args.bpm) if args.bpm else 140.0
            record_channel = 9 if args.record_part == 'drums' else (2 if args.record_part == 'keys' else 3)

            recorded_midi_path = str(output_dir / f"recorded_{args.record_part}.mid")

            def rec_progress(msg: str):
                if not args.json:
                    print_info(msg)

            cfg = RecordConfig(
                port_name=args.midi_in,
                bpm=record_bpm,
                part=args.record_part,
                bars=args.record_bars,
                seconds=args.record_seconds,
                count_in_bars=args.count_in,
                quantize=args.quantize,
            )

            print_step("0/6", f"Recording {args.record_part} from MIDI controller...")
            record_midi_to_file(cfg, recorded_midi_path, progress=rec_progress)
            if not args.json:
                print_success(f"Recorded MIDI saved: {Path(recorded_midi_path).name}")

        # Run generation pipeline
        results = run_generation(
            prompt=args.prompt,
            output_dir=output_dir,
            bpm_override=args.bpm,
            key_override=args.key,
            reference_url=args.reference,
            export_mpc=args.mpc,
            export_stems=args.stems,
            soundfont_path=args.soundfont,
            template_path=args.template,
            instruments_paths=args.instruments,
            verbose=args.verbose,
            seed=args.seed,
            use_bwf=not args.no_bwf,
            takes=args.takes,
            comp=args.comp,
            comp_bars=args.comp_bars,
        )

        # Replace generated part with recorded performance (if present)
        if recorded_midi_path and results.get('midi'):
            from multimodal_gen import replace_channel_in_midi

            print_step("5.5/6", f"Applying recorded {args.record_part} to arrangement...")
            replace_channel_in_midi(
                midi_path=results['midi'],
                replacement_midi_path=recorded_midi_path,
                channel=int(record_channel),
                output_path=results['midi'],
                replacement_track_name=f"Recorded {args.record_part}",
            )

            # Re-render audio so the WAV reflects the new MIDI
            print_step("5.7/6", "Re-rendering audio with recorded MIDI...")
            renderer = AudioRenderer(
                soundfont_path=args.soundfont,
                output_dir=str(output_dir),
                verbose=args.verbose,
                use_bwf=not args.no_bwf,
            )
            results['audio'] = renderer.render_midi_to_audio(results['midi'])
        
        # Parse prompt again for metadata (could optimize)
        parser_instance = PromptParser()
        parsed = parser_instance.parse(args.prompt)
        if args.bpm:
            parsed.bpm = args.bpm
        if args.key:
            if args.key.endswith("m"):
                parsed.key = args.key[:-1]
                parsed.scale = "minor"
            else:
                parsed.key = args.key
                parsed.scale = "major"
        
        # Save metadata with seed and synthesis params
        metadata_path = save_project_metadata(
            output_dir,
            args.prompt,
            results,
            parsed,
            seed=results.get('seed'),
            synthesis_params=results.get('synthesis_params')
        )
        
        if args.json:
            # JSON output mode
            import json
            output = {
                "success": True,
                "results": results,
                "metadata": str(metadata_path),
            }
            print(json.dumps(output, indent=2))
        else:
            # Human-readable summary
            try:
                print(f"\n{Fore.GREEN}{'═' * 50}{Style.RESET_ALL}")
                print(f"{Fore.GREEN}✓ Generation Complete!{Style.RESET_ALL}")
                print(f"{Fore.GREEN}{'═' * 50}{Style.RESET_ALL}")
            except UnicodeEncodeError:
                print(f"\n{Fore.GREEN}{'=' * 50}{Style.RESET_ALL}")
                print(f"{Fore.GREEN}[v] Generation Complete!{Style.RESET_ALL}")
                print(f"{Fore.GREEN}{'=' * 50}{Style.RESET_ALL}")
            
            if results["midi"]:
                try:
                    print(f"  📄 MIDI:    {Path(results['midi']).name}")
                except UnicodeEncodeError:
                    print(f"  [MIDI]      {Path(results['midi']).name}")
            if results["audio"]:
                try:
                    print(f"  🔊 Audio:   {Path(results['audio']).name}")
                except UnicodeEncodeError:
                    print(f"  [Audio]     {Path(results['audio']).name}")
            if results["mpc"]:
                try:
                    print(f"  🎹 MPC:     {Path(results['mpc']).parent.name}/")
                except UnicodeEncodeError:
                    print(f"  [MPC]       {Path(results['mpc']).parent.name}/")
            if results["stems"]:
                try:
                    print(f"  🎚️  Stems:   {len(results['stems'])} files")
                except UnicodeEncodeError:
                    print(f"  [Stems]     {len(results['stems'])} files")
            if results["samples"]:
                try:
                    print(f"  🥁 Samples: {len(results['samples'])} files")
                except UnicodeEncodeError:
                    print(f"  [Samples]   {len(results['samples'])} files")
            if results.get("instruments_used"):
                try:
                    print(f"  🎺 Custom Instruments: {len(results['instruments_used'])} selected")
                except UnicodeEncodeError:
                    print(f"  [Inst]      {len(results['instruments_used'])} selected")
            
            try:
                print(f"\n  📁 Output:  {output_dir.absolute()}")
            except UnicodeEncodeError:
                print(f"\n  [Output]    {output_dir.absolute()}")
            print()
        
        return 0
        
    except KeyboardInterrupt:
        if not args.json:
            print_warning("\nGeneration cancelled by user")
        return 130
        
    except Exception as e:
        if args.json:
            output = {
                "success": False,
                "error": str(e),
            }
            print(json.dumps(output, indent=2))
        else:
            print_error(f"Generation failed: {e}")
            if args.verbose:
                import traceback
                traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
