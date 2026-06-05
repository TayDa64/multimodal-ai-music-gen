"""Focused regressions for cinematic/classical session graph tracks."""

from multimodal_gen.prompt_parser import PromptParser
from multimodal_gen.session_graph import Role, SessionGraphBuilder


TASK_063_PROMPT = (
    "cinematic orchestral film score with strings, brass, choir, timpani, "
    "evolving sections, 96 BPM in D minor"
)

LYRICAL_CINEMATIC_PIANO_PROMPT = (
    "cinematic orchestral score with lyrical piano, warm strings, flute, oboe, "
    "harp, and soft choir, emotional rising theme, 78 BPM in G major"
)


def _track_shapes(graph):
    return [(track.name, track.role, track.channel) for track in graph.tracks]


def test_cinematic_classical_session_graph_preserves_orchestral_sections():
    parsed = PromptParser().parse(TASK_063_PROMPT)
    graph = SessionGraphBuilder().build_from_prompt(parsed)

    assert parsed.genre == "cinematic"
    assert {"strings", "brass", "choir", "timpani"}.issubset(set(parsed.instruments))

    tracks = _track_shapes(graph)
    assert ("Drums", Role.DRUMS.value, 9) in tracks
    assert ("Strings", Role.PAD.value, 2) in tracks
    assert ("Brass", Role.LEAD.value, 5) in tracks
    assert ("Choir", Role.PAD.value, 6) in tracks
    assert ("Timpani", Role.PERCUSSION.value, 8) in tracks
    assert not any(track.name == "Bass" for track in graph.tracks)


def test_cinematic_classical_manifest_preserves_orchestral_sections():
    parsed = PromptParser().parse(TASK_063_PROMPT)
    manifest = SessionGraphBuilder().build_from_prompt(parsed).to_dict()
    tracks = [(track["name"], track["role"], track["channel"]) for track in manifest["tracks"]]

    assert ("Drums", Role.DRUMS.value, 9) in tracks
    assert ("Strings", Role.PAD.value, 2) in tracks
    assert ("Brass", Role.LEAD.value, 5) in tracks
    assert ("Choir", Role.PAD.value, 6) in tracks
    assert ("Timpani", Role.PERCUSSION.value, 8) in tracks
    assert not any(track["name"] == "Bass" for track in manifest["tracks"])


def test_lyrical_cinematic_session_graph_preserves_first_class_piano_track():
    parsed = PromptParser().parse(LYRICAL_CINEMATIC_PIANO_PROMPT)
    graph = SessionGraphBuilder().build_from_prompt(parsed)

    assert parsed.genre == "cinematic"
    assert {"piano", "strings", "flute", "oboe", "harp", "choir"}.issubset(set(parsed.instruments))

    tracks = _track_shapes(graph)
    assert ("Piano", Role.CHORDS.value, 2) in tracks
    assert ("Strings", Role.PAD.value, 10) in tracks
    assert ("Woodwinds", Role.COUNTER_MELODY.value, 4) in tracks
    assert ("Choir", Role.PAD.value, 6) in tracks
    assert ("Harp", Role.CHORDS.value, 7) in tracks
    assert ("Strings", Role.PAD.value, 2) not in tracks


def test_lyrical_cinematic_manifest_preserves_first_class_piano_track():
    parsed = PromptParser().parse(LYRICAL_CINEMATIC_PIANO_PROMPT)
    manifest = SessionGraphBuilder().build_from_prompt(parsed).to_dict()
    tracks = [(track["name"], track["role"], track["channel"]) for track in manifest["tracks"]]

    assert ("Piano", Role.CHORDS.value, 2) in tracks
    assert ("Strings", Role.PAD.value, 10) in tracks
    assert ("Woodwinds", Role.COUNTER_MELODY.value, 4) in tracks
    assert ("Choir", Role.PAD.value, 6) in tracks
    assert ("Harp", Role.CHORDS.value, 7) in tracks
    assert ("Strings", Role.PAD.value, 2) not in tracks
