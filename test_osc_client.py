"""
Test client for OSC server.

Usage:
    python test_osc_client.py [command]
    
Commands:
    ping        - Send ping message
    generate    - Send test generation request
    cancel      - Cancel current generation
    shutdown    - Shutdown server
"""

import json
import sys
import time
import threading
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
    elif command == "shutdown":
        send_shutdown()
    else:
        print(f"Unknown command: {command}")
        print("Use: ping, generate, cancel, shutdown")
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
