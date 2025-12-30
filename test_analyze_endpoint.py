import json

import pytest


pytest.importorskip("pythonosc")

from multimodal_gen.server.config import ErrorCode, OSCAddresses, ServerConfig
from multimodal_gen.server.osc_server import MusicGenOSCServer


class DummyOSCClient:
    def __init__(self):
        self.messages: list[tuple[str, tuple]] = []

    def send_message(self, address, args):
        # osc_server._send_message passes a tuple of args as the second parameter
        self.messages.append((address, args))


def _last_payload(client: DummyOSCClient) -> dict:
    assert client.messages, "No OSC messages were sent"
    _address, args = client.messages[-1]
    assert isinstance(args, tuple) and len(args) == 1
    assert isinstance(args[0], str)
    return json.loads(args[0])


def test_analyze_missing_path_returns_file_not_found():
    server = MusicGenOSCServer(ServerConfig(verbose=False))
    client = DummyOSCClient()
    server._client = client

    request = {
        "request_id": "test-analyze-1",
        "schema_version": 1,
        "path": "Z:/definitely_not_real_file_12345.wav",
    }

    server._handle_analyze(OSCAddresses.ANALYZE, json.dumps(request))

    address, _args = client.messages[-1]
    assert address == OSCAddresses.ERROR

    payload = _last_payload(client)
    assert payload["request_id"] == "test-analyze-1"
    assert payload["code"] == ErrorCode.FILE_NOT_FOUND
    assert "File not found" in payload["message"]


def test_analyze_invalid_json_returns_invalid_message():
    server = MusicGenOSCServer(ServerConfig(verbose=False))
    client = DummyOSCClient()
    server._client = client

    server._handle_analyze(OSCAddresses.ANALYZE, "{not json")

    address, _args = client.messages[-1]
    assert address == OSCAddresses.ERROR

    payload = _last_payload(client)
    assert payload["code"] == ErrorCode.INVALID_MESSAGE


def test_analyze_success_returns_expected_payload_shape(monkeypatch, tmp_path):
    """Success-path test without requiring librosa/yt-dlp.

    The OSC server lazily imports ReferenceAnalyzer inside the handler.
    We monkeypatch the class to avoid pulling optional heavy deps and to
    make the output deterministic.
    """

    from multimodal_gen.reference_analyzer import (
        GrooveAnalysis,
        GrooveFeel,
        ReferenceAnalysis,
    )

    class DummyAnalyzer:
        def __init__(self, verbose: bool = False):
            self.verbose = verbose

        def analyze_file(self, file_path: str) -> ReferenceAnalysis:
            return ReferenceAnalysis(
                source_url=f"file://{file_path}",
                title="unit_test",
                duration_seconds=12.3,
                bpm=95.0,
                bpm_confidence=0.88,
                key="C",
                mode="minor",
                key_confidence=0.77,
                time_signature=(4, 4),
                estimated_genre="g_funk",
                genre_confidence=0.66,
                style_tags=["west coast", "talkbox"],
                groove=GrooveAnalysis(
                    swing_amount=0.25,
                    groove_feel=GrooveFeel.SHUFFLE,
                    pulse_strength=0.8,
                    micro_timing_variance=0.12,
                    downbeat_emphasis=0.9,
                ),
            )

        def analyze_url(self, url: str) -> ReferenceAnalysis:
            raise AssertionError("This test should call analyze_file")

    monkeypatch.setattr(
        "multimodal_gen.reference_analyzer.ReferenceAnalyzer",
        DummyAnalyzer,
        raising=True,
    )

    audio_path = tmp_path / "ref.wav"
    audio_path.write_bytes(b"RIFF----WAVEfmt ")  # minimal placeholder; not parsed

    server = MusicGenOSCServer(ServerConfig(verbose=False))
    client = DummyOSCClient()
    server._client = client

    request = {
        "request_id": "test-analyze-success-1",
        "schema_version": 1,
        "path": str(audio_path),
        "verbose": False,
    }

    server._handle_analyze(OSCAddresses.ANALYZE, json.dumps(request))

    address, _args = client.messages[-1]
    assert address == OSCAddresses.ANALYZE_RESULT

    payload = _last_payload(client)
    assert payload["request_id"] == "test-analyze-success-1"
    assert payload["success"] is True
    assert payload["schema_version"] == 1

    analysis = payload["analysis"]
    assert analysis["bpm"] == 95.0
    assert analysis["bpm_confidence"] == 0.88
    assert analysis["key"] == "C"
    assert analysis["mode"] == "minor"
    assert analysis["key_confidence"] == 0.77
    assert analysis["estimated_genre"] == "g_funk"
    assert analysis["genre_confidence"] == 0.66
    assert analysis["style_tags"] == ["west coast", "talkbox"]

    # Enum/tuple serialization checks
    assert analysis["time_signature"] == [4, 4]
    assert analysis["groove"]["groove_feel"] == "shuffle"

    assert isinstance(payload.get("prompt_hints"), str)
    assert isinstance(payload.get("generation_params"), dict)
