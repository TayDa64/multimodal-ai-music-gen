"""
Test client for OSC server.

Usage:
    python test_osc_client.py [command]
    
Commands:
    ping        - Send ping message
    generate    - Send test generation request
    cancel      - Cancel current generation
    select-take - Select a take for a track
    render-take - Render an explicit track/take selection
    render-selected - Render the current selected-takes arrangement (live JUCE shape)
    shutdown    - Shutdown server
"""

import json
import sys
import time
import threading
import uuid
from pythonosc import udp_client, dispatcher, osc_server


# Server ports (matching default config)
SERVER_PORT = 9000  # Server receives here
CLIENT_PORT = 9001  # Server sends here (we receive)


def create_receiver():
    """Create OSC receiver for server responses."""
    disp = dispatcher.Dispatcher()
    
    def handle_any(address, *args):
        print(f"📨 Received: {address}")
        for arg in args:
            try:
                data = json.loads(arg) if isinstance(arg, str) else arg
                print(f"   {json.dumps(data, indent=2)}")
            except:
                print(f"   {arg}")
    
    disp.set_default_handler(handle_any)
    
    server = osc_server.ThreadingOSCUDPServer(
        ("127.0.0.1", CLIENT_PORT),
        disp
    )
    
    return server


def send_ping():
    """Send ping to check if server is alive."""
    client = udp_client.SimpleUDPClient("127.0.0.1", SERVER_PORT)
    print("📤 Sending: /ping")
    client.send_message("/ping", [])


def send_generate(prompt: str = "G-Funk beat with smooth synths"):
    """Send generation request."""
    client = udp_client.SimpleUDPClient("127.0.0.1", SERVER_PORT)
    
    request = {
        "prompt": prompt,
        "bpm": 0,  # Auto-detect
        "key": "",  # Auto-detect
        "render_audio": True,
        "verbose": True,
    }
    
    print(f"📤 Sending: /generate")
    print(f"   Prompt: {prompt}")
    client.send_message("/generate", json.dumps(request))


def send_cancel():
    """Send cancel request."""
    client = udp_client.SimpleUDPClient("127.0.0.1", SERVER_PORT)
    print("📤 Sending: /cancel")
    client.send_message("/cancel", [])


def send_shutdown():
    """Send shutdown request."""
    client = udp_client.SimpleUDPClient("127.0.0.1", SERVER_PORT)
    print("📤 Sending: /shutdown")
    client.send_message("/shutdown", [])


def send_select_take(track: str, take_id: str, request_id: str | None = None):
    """Send a /take/select request."""
    client = udp_client.SimpleUDPClient("127.0.0.1", SERVER_PORT)
    request = {
        "request_id": request_id or str(uuid.uuid4()),
        "track": track,
        "take_id": take_id,
    }

    print("📤 Sending: /take/select")
    print(f"   Track: {track}")
    print(f"   Take: {take_id}")
    client.send_message("/take/select", json.dumps(request))


def send_render_take(
    track: str,
    take_id: str,
    output_path: str,
    *,
    request_id: str | None = None,
    use_comp: bool = False,
):
    """Send a /take/render request for an explicit track/take override."""
    client = udp_client.SimpleUDPClient("127.0.0.1", SERVER_PORT)
    request = {
        "request_id": request_id or str(uuid.uuid4()),
        "track": track,
        "take_id": take_id,
        "use_comp": use_comp,
        "output_path": output_path,
    }

    print("📤 Sending: /take/render")
    print(f"   Track: {track}")
    print(f"   Take: {take_id}")
    print(f"   Output: {output_path}")
    client.send_message("/take/render", json.dumps(request))


def send_render_selected(output_path: str, request_id: str | None = None):
    """Send the current live JUCE-style selected-takes render request."""
    client = udp_client.SimpleUDPClient("127.0.0.1", SERVER_PORT)
    request = {
        "request_id": request_id or str(uuid.uuid4()),
        "track": "",
        "take_id": "",
        "use_comp": True,
        "output_path": output_path,
    }

    print("📤 Sending: /take/render")
    print("   Mode: selected arrangement (trackless use_comp=true)")
    print(f"   Output: {output_path}")
    client.send_message("/take/render", json.dumps(request))


def main():
    command = sys.argv[1] if len(sys.argv) > 1 else "ping"
    prompt = " ".join(sys.argv[2:]) if len(sys.argv) > 2 else None
    
    # Start receiver in background
    receiver = create_receiver()
    receiver_thread = threading.Thread(target=receiver.serve_forever, daemon=True)
    receiver_thread.start()
    print(f"🎧 Listening for responses on port {CLIENT_PORT}")
    print()
    
    # Send command
    if command == "ping":
        send_ping()
    elif command == "generate":
        send_generate(prompt or "G-Funk beat with smooth synths and funky bassline")
    elif command == "cancel":
        send_cancel()
    elif command == "select-take":
        if len(sys.argv) < 4:
            print("Usage: python test_osc_client.py select-take <track> <take_id>")
            sys.exit(1)
        send_select_take(sys.argv[2], sys.argv[3])
    elif command == "render-take":
        if len(sys.argv) < 5:
            print("Usage: python test_osc_client.py render-take <track> <take_id> <output_path>")
            sys.exit(1)
        send_render_take(sys.argv[2], sys.argv[3], sys.argv[4])
    elif command == "render-selected":
        if len(sys.argv) < 3:
            print("Usage: python test_osc_client.py render-selected <output_directory_or_wav_path>")
            sys.exit(1)
        send_render_selected(sys.argv[2])
    elif command == "shutdown":
        send_shutdown()
    else:
        print(f"Unknown command: {command}")
        print("Use: ping, generate, cancel, select-take, render-take, render-selected, shutdown")
        sys.exit(1)
    
    # Wait for responses
    print()
    print("Waiting for responses (Ctrl+C to exit)...")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nExiting.")


if __name__ == "__main__":
    main()
