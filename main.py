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
)

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
    print(f"{Fore.CYAN}{banner}{Style.RESET_ALL}")


def print_step(step: str, message: str):
    """Print a step indicator."""
    print(f"{Fore.GREEN}[{step}]{Style.RESET_ALL} {message}")


def print_info(message: str):
    """Print info message."""
    print(f"{Fore.CYAN}ℹ{Style.RESET_ALL}  {message}")


def print_warning(message: str):
    """Print warning message."""
    print(f"{Fore.YELLOW}⚠{Style.RESET_ALL}  {message}")


def print_error(message: str):
    """Print error message."""
    print(f"{Fore.RED}✗{Style.RESET_ALL}  {message}")


def print_success(message: str):
    """Print success message."""
    print(f"{Fore.GREEN}✓{Style.RESET_ALL}  {message}")


def print_parsed_prompt(parsed: ParsedPrompt, reference_info: dict = None):
    """Print parsed prompt details."""
    print(f"\n{Fore.MAGENTA}{'─' * 50}{Style.RESET_ALL}")
    print(f"{Fore.MAGENTA}📝 Parsed Prompt:{Style.RESET_ALL}")
    print(f"   BPM: {parsed.bpm}")
    print(f"   Key: {parsed.key} {parsed.scale_type.name.lower()}")
    print(f"   Genre: {parsed.genre}")
    if parsed.style_modifiers:
        print(f"   Style: {', '.join(parsed.style_modifiers)}")
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
        print(f"\n{Fore.BLUE}🎵 Reference Analysis:{Style.RESET_ALL}")
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
    
    print(f"{Fore.MAGENTA}{'─' * 50}{Style.RESET_ALL}\n")


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


def run_generation(
    prompt: str,
    output_dir: Path,
    bpm_override: int = None,
    key_override: str = None,
    reference_url: str = None,
    export_mpc: bool = False,
    export_stems: bool = False,
    soundfont_path: str = None,
    template_path: str = None,
    instruments_path: str = None,
    verbose: bool = False,
) -> dict:
    """Run the full music generation pipeline.
    
    Args:
        prompt: Natural language music prompt
        output_dir: Directory for output files
        bpm_override: Override BPM from prompt
        key_override: Override key from prompt (e.g., "Cm", "F#m")
        reference_url: YouTube URL or audio file to analyze for style reference
        export_mpc: Export to MPC .xpj format
        export_stems: Export individual stem files
        soundfont_path: Path to SoundFont file for audio rendering
        template_path: Path to MPC template file
        instruments_path: Path to instruments folder for intelligent sample selection
        verbose: Enable verbose output
        
    Returns:
        Dictionary with paths to generated files
    """
    results = {
        "midi": None,
        "audio": None,
        "mpc": None,
        "stems": [],
        "samples": [],
        "reference_analysis": None,
        "instruments_used": [],
    }
    
    reference_info = None
    instrument_library = None
    
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
                "prompt_hints": analysis.to_prompt_hints(),
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
            enhanced_hints = analysis.to_prompt_hints()
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
    parser = PromptParser()
    parsed = parser.parse(prompt)
    
    # Apply overrides
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
    
    # Step 2: Create arrangement
    print_step("2/6", "Creating arrangement...")
    arranger = Arranger()
    arrangement = arranger.create_arrangement(parsed)
    
    if verbose:
        print_info(f"Arrangement: {len(arrangement.sections)} sections, {arrangement.total_bars} bars")
        bar_pos = 0
        for section in arrangement.sections:
            print_info(f"  - {section.section_type.value}: {section.bars} bars (tick {section.start_tick})")
            bar_pos += section.bars
    
    # Step 3: Generate MIDI
    print_step("3/6", "Generating MIDI with humanization...")
    midi_gen = MidiGenerator()
    midi_file = midi_gen.generate(arrangement, parsed)
    
    # Save MIDI file
    project_name = generate_project_name(parsed)
    midi_path = output_dir / f"{project_name}.mid"
    midi_file.save(str(midi_path))
    results["midi"] = str(midi_path)
    print_success(f"MIDI saved: {midi_path.name}")
    
    # Step 4: Generate procedural samples
    print_step("4/6", "Generating procedural samples...")
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
    
    # Step 4.5: Discover and analyze instruments (if path provided)
    if instruments_path:
        print_step("4.5/6", "Discovering and analyzing instruments...")
        try:
            from multimodal_gen import InstrumentLibrary, InstrumentMatcher
            
            # Use local cache if instruments dir is read-only (e.g., Program Files)
            instruments_path_obj = Path(instruments_path)
            try:
                # Try to use cache in instruments directory
                cache_file = str(instruments_path_obj / ".instrument_cache.json")
                # Test if writable
                test_file = instruments_path_obj / ".write_test"
                test_file.touch()
                test_file.unlink()
            except (PermissionError, OSError):
                # Fall back to local cache in output directory
                cache_name = instruments_path_obj.name.replace("[", "").replace("]", "")
                cache_file = str(output_dir / f".instrument_cache_{cache_name}.json")
                if verbose:
                    print_info(f"Using local cache (source is read-only)")
            
            instrument_library = InstrumentLibrary(
                instruments_dir=instruments_path,
                cache_file=cache_file,
                auto_load_audio=True
            )
            
            count = instrument_library.discover_and_analyze()
            
            if count > 0:
                print_success(f"Discovered {count} instruments")
                
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
                            print_info(f"  {cat}: {best.name} ({score:.0%} match)")
                            results["instruments_used"].append({
                                "category": cat,
                                "name": best.name,
                                "score": score,
                                "path": best.path,
                            })
            else:
                print_warning("No instruments found in specified directory")
                instrument_library = None
                
        except ImportError as e:
            print_warning(f"Instrument analysis requires librosa: {e}")
            print_info("Install with: pip install librosa")
            instrument_library = None
        except Exception as e:
            print_warning(f"Instrument discovery failed: {e}")
            instrument_library = None
    else:
        # Check for default instruments directory
        default_instruments = Path(__file__).parent / "instruments"
        if default_instruments.exists() and any(default_instruments.iterdir()):
            print_info(f"Tip: Add samples to {default_instruments} or use --instruments <path>")
    
    # Step 5: Render audio
    print_step("5/6", "Rendering audio...")
    renderer = AudioRenderer(
        soundfont_path=soundfont_path,
        instrument_library=instrument_library,
        genre=parsed.genre,
        mood=parsed.mood
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
    
    return results


def save_project_metadata(output_dir: Path, prompt: str, results: dict, parsed: ParsedPrompt):
    """Save project metadata as JSON."""
    metadata = {
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
        "version": "0.1.0",
    }
    
    metadata_path = output_dir / "project_metadata.json"
    with open(metadata_path, 'w') as f:
        json.dump(metadata, f, indent=2)
    
    return metadata_path


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
        """,
    )
    
    # Positional arguments
    parser.add_argument(
        "prompt",
        type=str,
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
        help="Path to instruments directory for intelligent sample selection (analyzes samples and picks best fit for genre/mood)",
    )
    
    # Template options
    parser.add_argument(
        "--template",
        type=str,
        help="Path to MPC template file for export customization",
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
        print()
    
    try:
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
            instruments_path=args.instruments,
            verbose=args.verbose,
        )
        
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
        
        # Save metadata
        metadata_path = save_project_metadata(output_dir, args.prompt, results, parsed)
        
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
            print(f"\n{Fore.GREEN}{'═' * 50}{Style.RESET_ALL}")
            print(f"{Fore.GREEN}✓ Generation Complete!{Style.RESET_ALL}")
            print(f"{Fore.GREEN}{'═' * 50}{Style.RESET_ALL}")
            
            if results["midi"]:
                print(f"  📄 MIDI:    {Path(results['midi']).name}")
            if results["audio"]:
                print(f"  🔊 Audio:   {Path(results['audio']).name}")
            if results["mpc"]:
                print(f"  🎹 MPC:     {Path(results['mpc']).parent.name}/")
            if results["stems"]:
                print(f"  🎚️  Stems:   {len(results['stems'])} files")
            if results["samples"]:
                print(f"  🥁 Samples: {len(results['samples'])} files")
            if results.get("instruments_used"):
                print(f"  🎺 Custom Instruments: {len(results['instruments_used'])} selected")
            
            print(f"\n  📁 Output:  {output_dir.absolute()}")
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
