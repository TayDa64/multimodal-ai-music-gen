"""
Test script: Send a masterclass generation request via OSC to the running server.
This tests the full pipeline: OSC → Python backend → MIDI generation → audio render → JUCE app.
"""
import json
import uuid
from pythonosc import udp_client

def main():
    client = udp_client.SimpleUDPClient("127.0.0.1", 9000)

    req_id = str(uuid.uuid4())
    request = {
        "request_id": req_id,
        "schema_version": 1,
        "prompt": (
            "Epic cinematic orchestral masterpiece with sweeping strings, "
            "powerful brass fanfare, thundering timpani, delicate harp arpeggios, "
            "soaring melody building to a triumphant climax with full orchestra"
        ),
        "genre": "cinematic",
        "bpm": 110,
        "key": "D minor",
        "duration_bars": 16,
        "render_audio": True,
        "export_stems": False,
        "num_takes": 1,
        "options": {
            "tension_arc_shape": "rising",
            "tension_intensity": 0.85,
            "production_preset": "cinematic",
        },
    }

    payload = json.dumps(request)
    client.send_message("/generate", payload)

    print(f"=== Masterclass Generation Request Sent ===")
    print(f"Request ID : {req_id[:8]}...")
    print(f"Prompt     : {request['prompt'][:80]}...")
    print(f"Genre      : {request['genre']}")
    print(f"BPM        : {request['bpm']}")
    print(f"Key        : {request['key']}")
    print(f"Bars       : {request['duration_bars']}")
    print(f"Tension    : {request['options']['tension_arc_shape']} @ {request['options']['tension_intensity']}")
    print(f"Production : {request['options']['production_preset']}")
    print()
    print("Watch the JUCE app for progress and mixer meter activity!")

if __name__ == "__main__":
    main()
