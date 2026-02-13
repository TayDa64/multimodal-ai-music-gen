"""
Virtual MIDI Bridge — sends generated MIDI to MPC Beats via loopMIDI.

Provides a ``MidiBridge`` class that opens a virtual MIDI output port
(via python-rtmidi) and streams MIDI events parsed from ``.mid`` files
(via mido) in real time, enabling live routing into MPC Beats or any
other DAW listening on the same virtual port.

Dependencies (optional — gracefully absent):
    - ``python-rtmidi``  — low-latency MIDI I/O
    - ``mido``           — MIDI file parsing (already in project)

Windows-specific:
    - ``loopMIDI`` (Tobias Erichsen) provides virtual MIDI ports.
      The bridge auto-detects loopMIDI ports when available.

Quick start::

    from multimodal_gen.intelligence.midi_bridge import create_midi_bridge
    bridge = create_midi_bridge()
    bridge.open_port()          # auto-detects loopMIDI port
    bridge.play_file("output/my_song.mid")
"""

from __future__ import annotations

import logging
import os
import platform
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional dependency probes
# ---------------------------------------------------------------------------

try:
    import rtmidi  # type: ignore[import-untyped]

    RTMIDI_AVAILABLE = True
except ImportError:
    RTMIDI_AVAILABLE = False

try:
    import mido  # type: ignore[import-untyped]

    MIDO_AVAILABLE = True
except ImportError:
    MIDO_AVAILABLE = False

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass
class MidiBridgeConfig:
    """Tuning knobs for the MIDI bridge."""

    port_name: str = "MUSE Virtual MIDI"
    """Name used when opening / matching the virtual output port."""

    auto_detect_loopmidi: bool = True
    """Automatically scan for loopMIDI ports on Windows."""

    default_tempo: float = 120.0
    """Fallback BPM when the MIDI file has no tempo meta-events."""

    ticks_per_beat: int = 480
    """Standard MIDI resolution (PPQ).  Used for time conversion."""


# ---------------------------------------------------------------------------
# MidiBridge
# ---------------------------------------------------------------------------


class MidiBridge:
    """Virtual MIDI output bridge — routes MIDI to DAWs via loopMIDI.

    The bridge wraps *python-rtmidi* for low-latency output and *mido*
    for MIDI file parsing.  Both are optional: if missing, instantiation
    raises ``ImportError`` with install instructions.

    Thread-safe: a ``threading.Lock`` guards port access; a
    ``threading.Event`` signals playback stop requests.
    """

    def __init__(self, config: Optional[MidiBridgeConfig] = None) -> None:
        if not RTMIDI_AVAILABLE:
            raise ImportError(
                "python-rtmidi is required for the MIDI bridge.\n"
                "Install it with:  pip install python-rtmidi\n"
                "On Windows you may also need the Visual C++ build tools."
            )
        if not MIDO_AVAILABLE:
            raise ImportError(
                "mido is required for MIDI file parsing.\n"
                "Install it with:  pip install mido"
            )

        self._config = config or MidiBridgeConfig()

        # rtmidi output wrapper
        self._midi_out: rtmidi.MidiOut = rtmidi.MidiOut()  # type: ignore[attr-defined]

        # Concurrency primitives
        self._port_lock = threading.Lock()
        self._stop_event = threading.Event()
        self._playback_thread: Optional[threading.Thread] = None

        # State
        self._port_name: Optional[str] = None
        self._playing = False
        self._playback_position: float = 0.0  # seconds elapsed

        logger.info("MidiBridge created (config=%s)", self._config)

    # ------------------------------------------------------------------
    # Port management
    # ------------------------------------------------------------------

    def list_output_ports(self) -> List[str]:
        """Return names of all available MIDI output ports."""
        with self._port_lock:
            return list(self._midi_out.get_ports())

    def open_port(self, port_name: Optional[str] = None) -> bool:
        """Open a MIDI output port.

        Resolution order:
        1. *port_name* argument (exact or substring match).
        2. Auto-detected loopMIDI port (if ``auto_detect_loopmidi``).
        3. First available port.
        4. Open a *virtual* port (Linux / macOS only — Windows
           requires loopMIDI).

        Returns ``True`` on success.
        """
        with self._port_lock:
            # Already open?
            if self._port_name is not None:
                logger.warning(
                    "Port '%s' already open — close it first.",
                    self._port_name,
                )
                return True

            ports = self._midi_out.get_ports()

            # --- 1. Explicit name ---
            target = port_name or self._config.port_name
            idx = self._find_port_index(ports, target)

            # --- 2. Auto-detect loopMIDI ---
            if idx is None and self._config.auto_detect_loopmidi:
                for i, p in enumerate(ports):
                    if "loopmidi" in p.lower():
                        idx = i
                        break

            # --- 3. First available port ---
            if idx is None and ports:
                idx = 0

            # --- 4. Virtual port fallback ---
            if idx is None:
                if platform.system() == "Windows":
                    logger.error(
                        "No MIDI output ports found.  Install loopMIDI to "
                        "create a virtual MIDI port on Windows."
                    )
                    return False
                # On Linux / macOS we can create a virtual port
                self._midi_out.open_virtual_port(target)
                self._port_name = target
                logger.info("Opened virtual port '%s'", target)
                return True

            # Open the matched hardware / loopMIDI port
            self._midi_out.open_port(idx)
            self._port_name = ports[idx]
            logger.info("Opened MIDI output port '%s' (index %d)", self._port_name, idx)
            return True

    def close_port(self) -> None:
        """Close the current output port."""
        self.stop_playback()
        with self._port_lock:
            if self._port_name is not None:
                self._midi_out.close_port()
                logger.info("Closed MIDI port '%s'", self._port_name)
                self._port_name = None

    def is_connected(self) -> bool:
        """``True`` if a MIDI output port is currently open."""
        with self._port_lock:
            return self._port_name is not None

    # ------------------------------------------------------------------
    # loopMIDI detection
    # ------------------------------------------------------------------

    def detect_loopmidi_ports(self) -> List[str]:
        """Return port names that look like loopMIDI virtual ports."""
        return [p for p in self.list_output_ports() if "loopmidi" in p.lower()]

    def is_loopmidi_available(self) -> bool:
        """``True`` if at least one loopMIDI port is detected."""
        return len(self.detect_loopmidi_ports()) > 0

    # ------------------------------------------------------------------
    # Playback — from MIDI file
    # ------------------------------------------------------------------

    def play_file(
        self,
        midi_path: str,
        tempo_override: Optional[float] = None,
    ) -> None:
        """Start non-blocking MIDI playback of *midi_path*.

        A daemon thread sends messages in real time via the open port.
        Call :meth:`stop_playback` to interrupt.
        """
        if not self.is_connected():
            raise RuntimeError("No MIDI port is open — call open_port() first.")
        if self._playing:
            self.stop_playback()

        path = Path(midi_path)
        if not path.is_file():
            raise FileNotFoundError(f"MIDI file not found: {midi_path}")

        self._stop_event.clear()
        self._playback_thread = threading.Thread(
            target=self._playback_worker,
            args=(str(path), tempo_override),
            name="MidiBridge-Playback",
            daemon=True,
        )
        self._playback_thread.start()

    def play_file_sync(
        self,
        midi_path: str,
        tempo_override: Optional[float] = None,
    ) -> None:
        """Blocking playback — returns when the file finishes or is stopped."""
        self.play_file(midi_path, tempo_override)
        if self._playback_thread is not None:
            self._playback_thread.join()

    def stop_playback(self) -> None:
        """Signal the playback thread to stop and wait for it."""
        if not self._playing:
            return
        self._stop_event.set()
        if self._playback_thread is not None:
            self._playback_thread.join(timeout=5.0)
            self._playback_thread = None
        # Send all-notes-off on every channel to avoid stuck notes
        self._send_all_notes_off()

    def is_playing(self) -> bool:
        """``True`` if a MIDI file is currently being streamed."""
        return self._playing

    # ------------------------------------------------------------------
    # Real-time note sending
    # ------------------------------------------------------------------

    def send_note_on(self, channel: int, note: int, velocity: int) -> None:
        """Send a MIDI Note-On message."""
        self._send_raw([0x90 | (channel & 0x0F), note & 0x7F, velocity & 0x7F])

    def send_note_off(self, channel: int, note: int) -> None:
        """Send a MIDI Note-Off message (velocity 0)."""
        self._send_raw([0x80 | (channel & 0x0F), note & 0x7F, 0])

    def send_cc(self, channel: int, cc: int, value: int) -> None:
        """Send a MIDI Control-Change message."""
        self._send_raw([0xB0 | (channel & 0x0F), cc & 0x7F, value & 0x7F])

    def send_program_change(self, channel: int, program: int) -> None:
        """Send a MIDI Program-Change message."""
        self._send_raw([0xC0 | (channel & 0x0F), program & 0x7F])

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def get_status(self) -> Dict[str, Any]:
        """Return a JSON-friendly status snapshot."""
        return {
            "connected": self.is_connected(),
            "port_name": self._port_name,
            "playing": self._playing,
            "position": round(self._playback_position, 3),
            "rtmidi_available": RTMIDI_AVAILABLE,
            "mido_available": MIDO_AVAILABLE,
            "loopmidi_detected": self.is_loopmidi_available(),
            "available_ports": self.list_output_ports(),
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _find_port_index(ports: List[str], name: str) -> Optional[int]:
        """Find port index by exact match or case-insensitive substring."""
        lower = name.lower()
        for i, p in enumerate(ports):
            if p == name:
                return i
        for i, p in enumerate(ports):
            if lower in p.lower():
                return i
        return None

    def _send_raw(self, message: List[int]) -> None:
        """Send a raw MIDI message through the open port."""
        with self._port_lock:
            if self._port_name is None:
                raise RuntimeError("No MIDI port is open.")
            self._midi_out.send_message(message)

    def _send_all_notes_off(self) -> None:
        """Send CC 123 (All Notes Off) on all 16 channels."""
        with self._port_lock:
            if self._port_name is None:
                return
            for ch in range(16):
                try:
                    self._midi_out.send_message([0xB0 | ch, 123, 0])
                except Exception:
                    pass

    def _playback_worker(
        self,
        midi_path: str,
        tempo_override: Optional[float],
    ) -> None:
        """Background thread: stream MIDI messages from a file."""
        self._playing = True
        self._playback_position = 0.0

        try:
            mid = mido.MidiFile(midi_path)
            ticks_per_beat = mid.ticks_per_beat or self._config.ticks_per_beat

            # Starting tempo
            if tempo_override is not None:
                tempo = mido.bpm2tempo(tempo_override)
            else:
                tempo = mido.bpm2tempo(self._config.default_tempo)

            merged = mido.merge_tracks(mid.tracks)

            for msg in merged:
                if self._stop_event.is_set():
                    break

                # Respect delta time (in ticks → seconds)
                if msg.time > 0:
                    delay = mido.tick2second(msg.time, ticks_per_beat, tempo)
                    self._playback_position += delay

                    # Sleep in small increments so we can respond to stop
                    deadline = time.perf_counter() + delay
                    while time.perf_counter() < deadline:
                        if self._stop_event.is_set():
                            break
                        remaining = deadline - time.perf_counter()
                        time.sleep(min(remaining, 0.01))

                    if self._stop_event.is_set():
                        break

                # Update tempo from meta-events (unless overridden)
                if msg.is_meta:
                    if msg.type == "set_tempo" and tempo_override is None:
                        tempo = msg.tempo
                    continue  # meta-events are not sent over MIDI

                # Send the MIDI message
                try:
                    self._send_raw(msg.bytes())
                except Exception as exc:
                    logger.warning("Failed to send MIDI message: %s", exc)

        except Exception:
            logger.exception("Playback error for '%s'", midi_path)
        finally:
            self._playing = False

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    def __enter__(self) -> "MidiBridge":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close_port()

    def __del__(self) -> None:
        try:
            self.close_port()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Module-level utilities
# ---------------------------------------------------------------------------


def create_midi_bridge(
    config: Optional[MidiBridgeConfig] = None,
) -> MidiBridge:
    """Factory function with dependency checking.

    Raises ``ImportError`` with actionable install instructions if
    required packages are missing.
    """
    missing: List[str] = []
    if not RTMIDI_AVAILABLE:
        missing.append("python-rtmidi  (pip install python-rtmidi)")
    if not MIDO_AVAILABLE:
        missing.append("mido           (pip install mido)")

    if missing:
        raise ImportError(
            "The MIDI bridge requires optional packages that are not "
            "installed:\n  " + "\n  ".join(missing) + "\n\n"
            "Install them and try again."
        )

    return MidiBridge(config)


def get_midi_setup_instructions() -> str:
    """Return human-readable setup instructions for loopMIDI + MPC Beats."""
    return (
        "=== MUSE MIDI Bridge — Setup Guide ===\n"
        "\n"
        "1. Install loopMIDI (Windows only)\n"
        "   Download: https://www.tobias-erichsen.de/software/loopmidi.html\n"
        "   Create a virtual port named 'MUSE Virtual MIDI' (or any name).\n"
        "\n"
        "2. Install Python dependencies\n"
        "       pip install python-rtmidi mido\n"
        "\n"
        "3. Configure MPC Beats\n"
        "   - Open MPC Beats → Edit → Preferences → MIDI\n"
        "   - Under MIDI Inputs, enable the loopMIDI port\n"
        "     (e.g. 'MUSE Virtual MIDI')\n"
        "   - Set the track's MIDI input to that port\n"
        "\n"
        "4. Use the bridge\n"
        "       from multimodal_gen.intelligence.midi_bridge import (\n"
        "           create_midi_bridge,\n"
        "       )\n"
        "       bridge = create_midi_bridge()\n"
        "       bridge.open_port()                # auto-detects loopMIDI\n"
        "       bridge.play_file('output/song.mid')  # streams to MPC Beats\n"
        "\n"
        "   Or via JSON-RPC:\n"
        '       {"jsonrpc":"2.0","method":"midi_bridge_play",\n'
        '        "params":{"midi_path":"output/song.mid"},"id":1}\n'
        "\n"
        "Notes:\n"
        "  - On macOS / Linux, python-rtmidi can create virtual ports\n"
        "    directly (loopMIDI is not needed).\n"
        "  - The bridge auto-detects loopMIDI ports on Windows.\n"
        "  - Call bridge.get_status() for diagnostics.\n"
    )
