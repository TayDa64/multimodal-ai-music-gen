import json
from pathlib import Path


def _rpc_call(method: str, params: dict) -> dict:
    """Call JSON-RPC server handler directly (unit-level)."""
    from multimodal_gen.server.config import ServerConfig
    from multimodal_gen.server.jsonrpc_server import MusicGenJSONRPCServer

    srv = MusicGenJSONRPCServer(config=ServerConfig(), host="127.0.0.1", port=0, worker=None)
    handler = srv._methods[method]  # type: ignore[attr-defined]
    return handler(params)


def test_run_critics_midi_returns_metrics(tmp_path: Path):
    # Use an existing fixture MIDI if available; fall back to generating a tiny MIDI via mido.
    midi_path = tmp_path / "tiny.mid"

    try:
        import mido

        mid = mido.MidiFile()
        tr = mido.MidiTrack()
        tr.name = "keys"
        mid.tracks.append(tr)

        # Simple two-chord voicing to ensure VLC can compute.
        tr.append(mido.Message("note_on", note=60, velocity=80, time=0, channel=0))
        tr.append(mido.Message("note_on", note=64, velocity=80, time=0, channel=0))
        tr.append(mido.Message("note_on", note=67, velocity=80, time=0, channel=0))
        tr.append(mido.Message("note_off", note=60, velocity=0, time=480, channel=0))
        tr.append(mido.Message("note_off", note=64, velocity=0, time=0, channel=0))
        tr.append(mido.Message("note_off", note=67, velocity=0, time=0, channel=0))

        tr.append(mido.Message("note_on", note=60, velocity=80, time=0, channel=0))
        tr.append(mido.Message("note_on", note=63, velocity=80, time=0, channel=0))
        tr.append(mido.Message("note_on", note=67, velocity=80, time=0, channel=0))
        tr.append(mido.Message("note_off", note=60, velocity=0, time=480, channel=0))
        tr.append(mido.Message("note_off", note=63, velocity=0, time=0, channel=0))
        tr.append(mido.Message("note_off", note=67, velocity=0, time=0, channel=0))

        mid.save(str(midi_path))
    except Exception:
        # If mido isn't available, the test can't proceed meaningfully.
        assert False, "mido is required for this test"

    res = _rpc_call("run_critics_midi", {"midi_path": str(midi_path)})

    assert "overall_passed" in res
    assert "metrics" in res and isinstance(res["metrics"], list)
    assert any(m.get("name") == "VLC" for m in res["metrics"])
    assert any(m.get("name") == "BKAS" for m in res["metrics"])
    assert any(m.get("name") == "ADC" for m in res["metrics"])

