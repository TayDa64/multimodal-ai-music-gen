"""Focused regressions for classic-rock Hammond session graph tracks."""

from multimodal_gen.prompt_parser import PromptParser
from multimodal_gen.session_graph import Role, SessionGraphBuilder


CLASSIC_ROCK_HAMMOND_PROMPT = (
    "classic rock anthem with crunchy electric guitar, Hammond organ, "
    "melodic bass guitar, live drums, verse chorus bridge, 108 BPM in A minor"
)


def _track_shapes(graph):
    return [(track.name, track.role, track.channel) for track in graph.tracks]


def test_classic_rock_hammond_session_graph_matches_midi_contract():
    parsed = PromptParser().parse(CLASSIC_ROCK_HAMMOND_PROMPT)
    graph = SessionGraphBuilder().build_from_prompt(parsed)

    assert parsed.genre == "classic_rock"
    assert {"guitar", "organ", "bass"}.issubset(set(parsed.instruments))

    tracks = _track_shapes(graph)
    assert ("Guitar", Role.CHORDS.value, 2) in tracks
    assert ("Organ", Role.PAD.value, 4) in tracks

    bass_tracks = [track for track in graph.tracks if track.name == "Bass"]
    assert len(bass_tracks) == 1
    assert bass_tracks[0].role == Role.BASS.value
    assert bass_tracks[0].channel == 1
    assert not any(track.name == "Bass" and track.role == Role.LEAD.value for track in graph.tracks)

    manifest = graph.to_dict()
    manifest_tracks = [(track["name"], track["role"], track["channel"]) for track in manifest["tracks"]]
    assert ("Guitar", Role.CHORDS.value, 2) in manifest_tracks
    assert ("Organ", Role.PAD.value, 4) in manifest_tracks
    assert len([track for track in manifest["tracks"] if track["name"] == "Bass"]) == 1
    assert not any(
        track["name"] == "Bass" and track["role"] == Role.LEAD.value
        for track in manifest["tracks"]
    )


def test_organic_classic_rock_does_not_trigger_explicit_organ_track():
    parsed = PromptParser().parse(
        "organic classic rock anthem with crunchy electric guitar, melodic bass guitar, "
        "live drums, verse chorus bridge, 108 BPM in A minor"
    )
    # Guard SessionGraphBuilder's raw-prompt cue check even if upstream instrument
    # normalization ever supplies organ without an explicit organ/Hammond word.
    parsed.instruments = ["organ", "guitar", "bass"]

    graph = SessionGraphBuilder().build_from_prompt(parsed)

    assert ("Organ", Role.PAD.value, 4) not in _track_shapes(graph)
