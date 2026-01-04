import mido
import sys
import os

# Find a recent MIDI file
output_dir = 'output'
midi_files = [f for f in os.listdir(output_dir) if f.endswith('.mid')]
if not midi_files:
    print("No MIDI files found")
    sys.exit(1)

midi_file = os.path.join(output_dir, sorted(midi_files)[-1])
print(f"Analyzing: {midi_file}")

mid = mido.MidiFile(midi_file)
print(f"Tracks: {len(mid.tracks)}")

for i, track in enumerate(mid.tracks):
    note_on_count = sum(1 for m in track if m.type == 'note_on' and m.velocity > 0)
    track_name = track.name if hasattr(track, 'name') and track.name else f"Track {i}"
    print(f"  Track {i} ({track_name}): {note_on_count} note_on events, {len(track)} total messages")
