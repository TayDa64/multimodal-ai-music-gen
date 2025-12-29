"""MIDI input recording utilities.

This module enables using external MIDI controllers (e.g., Akai MPC Studio)
with the generator workflow.

Design goals:
- Uses pygame.midi for cross-platform MIDI device access (pre-built Windows binaries).
- Simple CLI integration: list inputs, record a part for N bars/seconds.
- Output a standard MIDI file aligned to the target BPM.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable, List, Optional, Tuple, Dict, Any

import mido
from mido import MidiFile, MidiTrack, Message, MetaMessage

# pygame.midi is our MIDI device backend (has pre-built Windows wheels)
try:
    import pygame.midi as pm
    HAS_PYGAME_MIDI = True
except ImportError:
    HAS_PYGAME_MIDI = False
    pm = None


class MidiRecordingError(RuntimeError):
    pass


@dataclass
class MidiDeviceInfo:
    """Information about a MIDI device."""
    device_id: int
    name: str
    is_input: bool
    is_output: bool
    is_opened: bool = False

    def __str__(self) -> str:
        direction = "IN" if self.is_input else "OUT"
        return f"[{self.device_id}] {self.name} ({direction})"


@dataclass
class RecordConfig:
    port_name: str  # Can be device name or ID as string
    bpm: float
    part: str  # drums|keys|lead
    bars: Optional[int] = 8
    seconds: Optional[float] = None
    count_in_bars: int = 1
    ticks_per_beat: int = 480
    quantize: str = "off"  # off|1/16|1/8
    channel: Optional[int] = None
    program: Optional[int] = None


def _ensure_pygame_midi() -> None:
    """Initialize pygame.midi if available."""
    if not HAS_PYGAME_MIDI:
        raise MidiRecordingError(
            "pygame is required for MIDI device access. Install with: pip install pygame"
        )
    if not pm.get_init():
        pm.init()


def _get_all_devices() -> List[MidiDeviceInfo]:
    """Get all MIDI devices (input and output)."""
    _ensure_pygame_midi()
    devices = []
    count = pm.get_count()
    for i in range(count):
        info = pm.get_device_info(i)
        # info = (interface, name, is_input, is_output, is_opened)
        name = info[1].decode("utf-8", errors="replace") if isinstance(info[1], bytes) else str(info[1])
        devices.append(MidiDeviceInfo(
            device_id=i,
            name=name,
            is_input=bool(info[2]),
            is_output=bool(info[3]),
            is_opened=bool(info[4]),
        ))
    return devices


def list_midi_inputs() -> List[str]:
    """Return available MIDI input port names with device IDs."""
    try:
        devices = _get_all_devices()
        return [f"[{d.device_id}] {d.name}" for d in devices if d.is_input]
    except Exception as exc:
        raise MidiRecordingError(
            f"Unable to list MIDI inputs: {exc}. Ensure pygame is installed (pip install pygame)."
        ) from exc


def list_midi_devices_detailed() -> Dict[str, List[MidiDeviceInfo]]:
    """Return detailed info about all MIDI devices."""
    devices = _get_all_devices()
    return {
        "inputs": [d for d in devices if d.is_input],
        "outputs": [d for d in devices if d.is_output],
    }


def _find_input_device(port_name: str) -> int:
    """Find a MIDI input device by name or ID. Returns device ID."""
    devices = _get_all_devices()
    inputs = [d for d in devices if d.is_input]

    if not inputs:
        raise MidiRecordingError(
            "No MIDI input devices found. Ensure your MPC is connected and powered on."
        )

    # Try exact ID match first (e.g., "3" or "[3]")
    clean_id = port_name.strip("[]")
    if clean_id.isdigit():
        dev_id = int(clean_id)
        for d in inputs:
            if d.device_id == dev_id:
                return dev_id
        raise MidiRecordingError(
            f"MIDI device ID {dev_id} not found or not an input. Available: {[str(d) for d in inputs]}"
        )

    # Try exact name match
    for d in inputs:
        if d.name == port_name:
            return d.device_id

    # Try substring match (case-insensitive)
    port_lower = port_name.lower()
    matches = [d for d in inputs if port_lower in d.name.lower()]
    if len(matches) == 1:
        return matches[0].device_id
    elif len(matches) > 1:
        raise MidiRecordingError(
            f"Ambiguous MIDI input '{port_name}' matches multiple devices: {[str(d) for d in matches]}. "
            f"Use device ID instead (e.g., --midi-in 3)"
        )
    else:
        raise MidiRecordingError(
            f"MIDI input '{port_name}' not found. Available inputs: {[str(d) for d in inputs]}"
        )


def _seconds_to_ticks(seconds: float, bpm: float, ticks_per_beat: int) -> int:
    beats = seconds * bpm / 60.0
    return int(round(beats * ticks_per_beat))


def _quantize_tick(tick: int, grid: int) -> int:
    if grid <= 0:
        return tick
    return int(round(tick / grid) * grid)


def record_midi_to_file(
    cfg: RecordConfig,
    output_path: str,
    progress: Optional[Callable[[str], None]] = None,
) -> str:
    """Record MIDI from a live input and save to a MIDI file.

    Uses pygame.midi for device access.
    Notes:
    - Uses wall-clock timing and converts to ticks at cfg.bpm.
    - Writes a single track with tempo meta and (optional) program change.
    """
    _ensure_pygame_midi()

    if cfg.part not in {"drums", "keys", "lead"}:
        raise ValueError("part must be one of: drums, keys, lead")

    # Decide default channel/program by part to match generator conventions
    if cfg.channel is None:
        cfg.channel = 9 if cfg.part == "drums" else (2 if cfg.part == "keys" else 3)
    if cfg.program is None:
        cfg.program = 0 if cfg.part == "keys" else (80 if cfg.part == "lead" else None)

    # Find the device
    device_id = _find_input_device(cfg.port_name)
    device_info = pm.get_device_info(device_id)
    device_name = device_info[1].decode("utf-8", errors="replace") if isinstance(device_info[1], bytes) else str(device_info[1])

    # Compute target duration
    if cfg.seconds is None:
        if not cfg.bars or cfg.bars <= 0:
            raise ValueError("bars must be > 0 when seconds is not provided")
        seconds_per_bar = (60.0 / cfg.bpm) * 4.0
        total_seconds = cfg.bars * seconds_per_bar
    else:
        total_seconds = float(cfg.seconds)

    if cfg.count_in_bars < 0:
        cfg.count_in_bars = 0

    if progress:
        progress(f"MIDI input: [{device_id}] {device_name}")

    # Prepare MIDI container
    mid = MidiFile(ticks_per_beat=cfg.ticks_per_beat)
    track = MidiTrack()
    mid.tracks.append(track)

    tempo = mido.bpm2tempo(cfg.bpm)
    track.append(MetaMessage("set_tempo", tempo=tempo, time=0))
    track.append(MetaMessage("time_signature", numerator=4, denominator=4, time=0))
    track.append(MetaMessage("track_name", name=f"Recorded {cfg.part}", time=0))
    if cfg.program is not None:
        track.append(Message("program_change", program=int(cfg.program), channel=int(cfg.channel), time=0))

    # Count-in (no MIDI click; just a helpful pause)
    if cfg.count_in_bars > 0:
        seconds_per_bar = (60.0 / cfg.bpm) * 4.0
        if progress:
            progress(f"Count-in: {cfg.count_in_bars} bar(s) ({cfg.count_in_bars * seconds_per_bar:.1f}s)...")
        time.sleep(cfg.count_in_bars * seconds_per_bar)

    if progress:
        progress(f"🔴 Recording {cfg.part} for ~{total_seconds:.1f}s... Play now!")

    messages: List[Tuple[int, Message]] = []
    start = time.perf_counter()

    try:
        midi_in = pm.Input(device_id)
    except Exception as exc:
        raise MidiRecordingError(
            f"Failed to open MIDI input [{device_id}] {device_name}. "
            f"It may be in use by another application (like MPC Software). "
            f"Close other MIDI apps and try again. Error: {exc}"
        ) from exc

    try:
        while True:
            now = time.perf_counter()
            elapsed = now - start
            if elapsed >= total_seconds:
                break

            # Poll for MIDI events
            if midi_in.poll():
                events = midi_in.read(32)  # Read up to 32 events at a time
                for event in events:
                    data, timestamp = event
                    status = data[0]
                    # Parse status byte
                    msg_type = status & 0xF0
                    channel = status & 0x0F

                    if msg_type == 0x90 and len(data) >= 3:
                        # Note On
                        note, velocity = data[1], data[2]
                        if velocity == 0:
                            msg = Message("note_off", note=note, velocity=0, channel=int(cfg.channel))
                        else:
                            msg = Message("note_on", note=note, velocity=velocity, channel=int(cfg.channel))
                        tick = _seconds_to_ticks(elapsed, cfg.bpm, cfg.ticks_per_beat)
                        messages.append((tick, msg))

                    elif msg_type == 0x80 and len(data) >= 3:
                        # Note Off
                        note = data[1]
                        msg = Message("note_off", note=note, velocity=0, channel=int(cfg.channel))
                        tick = _seconds_to_ticks(elapsed, cfg.bpm, cfg.ticks_per_beat)
                        messages.append((tick, msg))

                    elif msg_type == 0xB0 and len(data) >= 3:
                        # Control Change
                        control, value = data[1], data[2]
                        msg = Message("control_change", control=control, value=value, channel=int(cfg.channel))
                        tick = _seconds_to_ticks(elapsed, cfg.bpm, cfg.ticks_per_beat)
                        messages.append((tick, msg))

                    elif msg_type == 0xE0 and len(data) >= 3:
                        # Pitch Wheel
                        lsb, msb = data[1], data[2]
                        pitch = ((msb << 7) | lsb) - 8192
                        msg = Message("pitchwheel", pitch=pitch, channel=int(cfg.channel))
                        tick = _seconds_to_ticks(elapsed, cfg.bpm, cfg.ticks_per_beat)
                        messages.append((tick, msg))

            # Light sleep to avoid spinning
            time.sleep(0.001)

    finally:
        midi_in.close()

    if progress:
        progress(f"✅ Recording complete. Captured {len(messages)} MIDI events.")

    if not messages:
        raise MidiRecordingError(
            "No MIDI events were recorded. Verify:\n"
            "  1. MPC pads are lit and responding\n"
            "  2. MPC is in Controller Mode (not Standalone)\n"
            "  3. You're using the correct MIDI port (try 'Public' port for pads)\n"
            "  4. No other app has exclusive access to the MPC"
        )

    # Optional quantize (note events only)
    grid = 0
    if cfg.quantize == "1/16":
        grid = cfg.ticks_per_beat // 4
    elif cfg.quantize == "1/8":
        grid = cfg.ticks_per_beat // 2

    if grid > 0:
        quantized: List[Tuple[int, Message]] = []
        for tick, msg in messages:
            if msg.type in {"note_on", "note_off"}:
                tick = _quantize_tick(tick, grid)
            quantized.append((tick, msg))
        messages = quantized

    # Sort and convert to delta times
    messages.sort(key=lambda x: (x[0], 0 if x[1].type == "note_off" else 1))

    prev = 0
    for tick, msg in messages:
        delta = max(0, int(tick - prev))
        track.append(msg.copy(time=delta))
        prev = tick

    track.append(MetaMessage("end_of_track", time=0))
    mid.save(output_path)
    return output_path


def replace_channel_in_midi(
    midi_path: str,
    replacement_midi_path: str,
    channel: int,
    output_path: Optional[str] = None,
    replacement_track_name: str = "Recorded",
) -> str:
    """Replace all note/control data on a given channel with a replacement track.

    This is used to swap in your live MPC performance for drums/keys/lead.

    - Removes channel messages (notes + CC + pitch) from all existing tracks.
    - Appends a new track containing the replacement content (retimed as authored).
    """

    base = MidiFile(midi_path)
    repl = MidiFile(replacement_midi_path)

    def keep(msg: mido.Message) -> bool:
        if not hasattr(msg, "channel"):
            return True
        if msg.channel != channel:
            return True
        # Strip musical control on that channel
        if msg.type in {
            "note_on",
            "note_off",
            "control_change",
            "program_change",
            "pitchwheel",
            "aftertouch",
            "polytouch",
        }:
            return False
        return True

    for i, tr in enumerate(base.tracks):
        # Keep meta messages; remove channel messages for requested channel
        filtered = MidiTrack([msg for msg in tr if keep(msg)])
        base.tracks[i] = filtered

    # Append replacement tracks (skip tempo track 0 if it only contains meta)
    for tr in repl.tracks:
        new_tr = MidiTrack()
        new_tr.append(MetaMessage("track_name", name=replacement_track_name, time=0))
        for msg in tr:
            # Preserve meta tempo if user recorded with metronome; otherwise it won't hurt.
            new_tr.append(msg)
        base.tracks.append(new_tr)
        break

    out = output_path or midi_path
    base.save(out)
    return out
