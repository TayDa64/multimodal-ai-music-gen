"""Sprint 2 Acceptance Test — 5 genre multi-track MIDI generation + QualityValidator critics.

Runs OfflineConductor (with MidiGenerator fallback) for five genres,
validates each with QualityValidator, and reports VLC / BKAS / ADC scores.
"""

import sys
import os
import traceback

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(__file__))

from mido import MidiFile, MidiTrack, Message, MetaMessage


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def extract_notes(midi: MidiFile):
    """Extract (start_tick, duration_ticks, pitch, velocity) tuples from MIDI."""
    all_notes = []
    drum_notes = []
    for track in midi.tracks:
        abs_tick = 0
        pending = {}
        is_drum = False
        for msg in track:
            abs_tick += msg.time
            if msg.type == 'track_name' and 'drum' in msg.name.lower():
                is_drum = True
            if msg.type == 'note_on' and msg.velocity > 0:
                pending[(msg.channel, msg.note)] = (abs_tick, msg.velocity)
            elif msg.type in ('note_off', 'note_on') and (msg.type == 'note_off' or msg.velocity == 0):
                key = (msg.channel, msg.note if msg.type == 'note_off' else msg.note)
                if key in pending:
                    start, vel = pending.pop(key)
                    dur = abs_tick - start
                    note = (start, dur, msg.note if msg.type == 'note_off' else msg.note, vel)
                    all_notes.append(note)
                    if is_drum or msg.channel == 9:
                        drum_notes.append(note)
    return all_notes, drum_notes


def tracks_to_midi(tracks_dict, bpm=120):
    """Convert conductor tracks Dict[str, List[NoteEvent]] to a mido.MidiFile."""
    mid = MidiFile(ticks_per_beat=480)

    # Tempo track
    tempo_track = MidiTrack()
    import mido
    tempo_track.append(mido.MetaMessage('set_tempo', tempo=mido.bpm2tempo(bpm), time=0))
    mid.tracks.append(tempo_track)

    for track_name, note_events in tracks_dict.items():
        t = MidiTrack()
        t.append(MetaMessage('track_name', name=track_name, time=0))

        # Determine channel
        is_drum = track_name.lower() in ('drums', 'kebero', 'atamo')
        channel = 9 if is_drum else 0

        # Build absolute-time message list
        msgs = []
        for ne in note_events:
            start = int(ne.start_tick)
            dur = int(ne.duration_ticks)
            pitch = int(ne.pitch)
            vel = int(ne.velocity)
            msgs.append((start, 'note_on', pitch, vel, channel))
            msgs.append((start + dur, 'note_off', pitch, 0, channel))

        msgs.sort(key=lambda m: m[0])

        prev = 0
        for abs_t, kind, pitch, vel, ch in msgs:
            delta = abs_t - prev
            if kind == 'note_on':
                t.append(Message('note_on', note=pitch, velocity=vel, channel=ch, time=delta))
            else:
                t.append(Message('note_off', note=pitch, velocity=vel, channel=ch, time=delta))
            prev = abs_t

        mid.tracks.append(t)

    return mid


# ---------------------------------------------------------------------------
# Genre test configs
# ---------------------------------------------------------------------------

GENRES = [
    {
        "name": "neo_soul",
        "prompt": "neo soul groove at 90 bpm in C minor",
        "key": "C",
        "genre_tag": "neo_soul",
    },
    {
        "name": "trap",
        "prompt": "trap beat at 140 bpm in F# minor",
        "key": "F#",
        "genre_tag": "trap",
    },
    {
        "name": "house",
        "prompt": "house groove at 124 bpm in A minor",
        "key": "A",
        "genre_tag": "house",
    },
    {
        "name": "lofi",
        "prompt": "lofi chill at 80 bpm in D major",
        "key": "D",
        "genre_tag": "lofi",
    },
    {
        "name": "ethiopian",
        "prompt": "ethiopian traditional at 100 bpm in A minor",
        "key": "A",
        "genre_tag": "ethiopian",
    },
]

PASS_THRESHOLD = 0.6   # normalized_score >= 0.6 → pass


# ---------------------------------------------------------------------------
# Main test
# ---------------------------------------------------------------------------

def run_acceptance_test():
    from multimodal_gen.prompt_parser import parse_prompt
    from multimodal_gen.arranger import Arranger, create_arrangement
    from multimodal_gen.quality_validator import QualityValidator

    validator = QualityValidator()
    results = []

    for cfg in GENRES:
        label = cfg["name"]
        prompt = cfg["prompt"]
        key = cfg["key"]
        genre = cfg["genre_tag"]

        print(f"\n{'='*60}")
        print(f"  Genre: {label}")
        print(f"  Prompt: {prompt}")
        print(f"{'='*60}")

        # Step 1 — parse
        parsed = parse_prompt(prompt)
        print(f"  Parsed → genre={parsed.genre}, bpm={parsed.bpm}, key={parsed.key}")

        # Step 2 — arrange
        arrangement = create_arrangement(parsed)
        print(f"  Arrangement → {len(arrangement.sections)} sections")

        # Step 3 — generate MIDI (conductor first, MidiGenerator fallback)
        midi = None
        method = ""
        num_tracks = 0
        try:
            from multimodal_gen.agents.conductor_offline import OfflineConductor
            conductor = OfflineConductor(verbose=False, use_agents=True)
            score = conductor.create_score(parsed, conductor.research_style(parsed))
            ensemble = conductor.assemble_ensemble(parsed, conductor.research_style(parsed))
            tracks = conductor.conduct_performance(score, ensemble)
            num_tracks = len(tracks)
            bpm = parsed.bpm or 120
            midi = tracks_to_midi(tracks, bpm=bpm)
            method = "OfflineConductor"
            print(f"  Generated via {method} → {num_tracks} tracks")
        except Exception as exc:
            print(f"  OfflineConductor failed: {exc}")
            try:
                from multimodal_gen.midi_generator import MidiGenerator
                midi = MidiGenerator(use_physics_humanization=False).generate(arrangement, parsed)
                method = "MidiGenerator(fallback)"
                num_tracks = len(midi.tracks) - 1  # minus tempo track
                print(f"  Generated via {method} → {num_tracks} tracks")
            except Exception as exc2:
                print(f"  MidiGenerator fallback also failed: {exc2}")
                traceback.print_exc()
                results.append({
                    "genre": label,
                    "tracks": 0,
                    "vlc": None,
                    "bkas": None,
                    "adc": None,
                    "critics_passed": 0,
                    "overall": 0.0,
                    "error": str(exc2),
                })
                continue

        # Step 4 — extract notes
        all_notes, drum_notes = extract_notes(midi)
        print(f"  Extracted {len(all_notes)} notes total, {len(drum_notes)} drum notes")

        if not all_notes:
            print("  WARNING: No notes extracted — skipping validation")
            results.append({
                "genre": label,
                "tracks": num_tracks,
                "vlc": None,
                "bkas": None,
                "adc": None,
                "critics_passed": 0,
                "overall": 0.0,
                "error": "no notes",
            })
            continue

        # Step 5 — validate
        report = validator.validate(
            all_notes,
            key=key,
            genre=genre,
            ticks_per_beat=480,
            reference_notes=drum_notes,
        )

        # Step 6 — pull VLC / BKAS / ADC
        vlc_score = None
        bkas_score = None
        adc_score = None

        for m in report.metrics:
            if m.name == "Voice Leading Cost (VLC)":
                vlc_score = m.normalized_score
            elif m.name == "Bass-Kick Alignment (BKAS)":
                bkas_score = m.normalized_score
            elif m.name == "Arrangement Density Curve (ADC)":
                adc_score = m.normalized_score

        critics_passed = sum(
            1 for s in (vlc_score, bkas_score, adc_score)
            if s is not None and s >= PASS_THRESHOLD
        )

        print(f"  VLC  = {vlc_score:.2f}" if vlc_score is not None else "  VLC  = N/A")
        print(f"  BKAS = {bkas_score:.2f}" if bkas_score is not None else "  BKAS = N/A")
        print(f"  ADC  = {adc_score:.2f}" if adc_score is not None else "  ADC  = N/A")
        print(f"  Critics passed: {critics_passed}/3   Overall: {report.overall_score:.2f}")

        results.append({
            "genre": label,
            "tracks": num_tracks,
            "vlc": vlc_score,
            "bkas": bkas_score,
            "adc": adc_score,
            "critics_passed": critics_passed,
            "overall": report.overall_score,
            "error": None,
        })

    # ---------------------------------------------------------------------------
    # Summary table
    # ---------------------------------------------------------------------------
    print("\n\n" + "=" * 90)
    print("  SPRINT 2 ACCEPTANCE TEST — SUMMARY")
    print("=" * 90)
    header = f"{'Genre':<12} | {'Tracks':>6} | {'VLC':>6} | {'BKAS':>6} | {'ADC':>6} | {'Pass':>5} | {'Overall':>7}"
    print(header)
    print("-" * len(header))

    genres_passing = 0
    for r in results:
        vlc_s = f"{r['vlc']:.2f}" if r['vlc'] is not None else "  N/A"
        bkas_s = f"{r['bkas']:.2f}" if r['bkas'] is not None else "  N/A"
        adc_s = f"{r['adc']:.2f}" if r['adc'] is not None else "  N/A"
        overall_s = f"{r['overall']:.2f}"
        passed = f"{r['critics_passed']}/3"
        row = f"{r['genre']:<12} | {r['tracks']:>6} | {vlc_s:>6} | {bkas_s:>6} | {adc_s:>6} | {passed:>5} | {overall_s:>7}"
        print(row)
        if r['critics_passed'] >= 3:
            genres_passing += 1

    print("-" * len(header))
    print(f"\n  Result: {genres_passing}/5 genres pass 3+ critics")
    verdict = "PASS" if genres_passing >= 3 else "FAIL"
    print(f"  Sprint 2 Acceptance: ** {verdict} **\n")

    return genres_passing


if __name__ == "__main__":
    run_acceptance_test()
