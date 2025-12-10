#!/usr/bin/env python
"""
Test client for OSC server.

Usage:
    python test_client.py ping
    python test_client.py generate "G-Funk beat with smooth synths"
"""

import json
import sys
import time
from pythonosc import udp_client, osc_server, dispatcher
import threading

# Server addresses
SERVER_HOST = "127.0.0.1"
SERVER_PORT = 9000
CLIENT_PORT = 9001


def create_listener():
    """Create a listener for server responses."""
    d = dispatcher.Dispatcher()
    
    def handle_message(address, *args):
        print(f"\n📨 Response: {address}")
        for arg in args:
            try:
                data = json.loads(arg)
                print(json.dumps(data, indent=2))
            except:
                print(f"   {arg}")
    
    d.set_default_handler(handle_message)
    
    server = osc_server.ThreadingOSCUDPServer((SERVER_HOST, CLIENT_PORT), d)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def send_ping():
    """Send ping to server."""
    client = udp_client.SimpleUDPClient(SERVER_HOST, SERVER_PORT)
    print(f"📤 Sending /ping to {SERVER_HOST}:{SERVER_PORT}")
    client.send_message("/ping", [])


def send_generate(prompt: str):
    """Send generation request."""
    client = udp_client.SimpleUDPClient(SERVER_HOST, SERVER_PORT)
    
    request = json.dumps({
        "prompt": prompt,
        "render_audio": True,
        "verbose": True,
    })
    
    print(f"📤 Sending /generate to {SERVER_HOST}:{SERVER_PORT}")
    print(f"   Prompt: {prompt}")
    client.send_message("/generate", request)


def main():
    if len(sys.argv) < 2:
        print("Usage: python test_client.py <command> [args]")
        print("Commands: ping, generate")
        sys.exit(1)
    
    command = sys.argv[1].lower()
    
    # Start listener for responses
    listener = create_listener()
    print(f"👂 Listening for responses on port {CLIENT_PORT}")
    
    if command == "ping":
        send_ping()
        time.sleep(1)  # Wait for response
        
    elif command == "generate":
        prompt = sys.argv[2] if len(sys.argv) > 2 else "Lo-fi hip hop beat"
        send_generate(prompt)
        print("\n⏳ Waiting for generation (press Ctrl+C to stop listening)...")
        try:
            while True:
                time.sleep(0.5)
        except KeyboardInterrupt:
            print("\n👋 Stopped listening")
    
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
