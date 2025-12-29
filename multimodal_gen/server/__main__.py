"""
Entry point for running the OSC server as a module.

Usage:
    python -m multimodal_gen.server [--verbose] [--port PORT]
"""

import argparse
import sys


def main():
    parser = argparse.ArgumentParser(
        description="AI Music Generator OSC Server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python -m multimodal_gen.server --verbose
    python -m multimodal_gen.server --port 9000 --send-port 9001
        """
    )
    
    parser.add_argument(
        "--port", "-p",
        type=int,
        default=9000,
        help="Port to receive OSC messages (default: 9000)"
    )
    
    parser.add_argument(
        "--send-port", "-s",
        type=int,
        default=9001,
        help="Port to send OSC messages (default: 9001)"
    )
    
    parser.add_argument(
        "--host", "-H",
        type=str,
        default="127.0.0.1",
        help="Host address to bind to (default: 127.0.0.1)"
    )
    
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging"
    )
    
    args = parser.parse_args()
    
    # Import here to avoid the RuntimeWarning
    from .osc_server import run_server
    
    print(f"🎵 Starting AI Music Generator OSC Server")
    print(f"   Receiving on port: {args.port}")
    print(f"   Sending to port: {args.send_port}")
    print(f"   Verbose: {args.verbose}")
    print()
    
    run_server(
        recv_port=args.port,
        send_port=args.send_port,
        host=args.host,
        verbose=args.verbose,
    )


if __name__ == "__main__":
    main()
