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
    
    parser.add_argument(
        "--jsonrpc",
        action="store_true",
        help="Start JSON-RPC server instead of OSC server (default port 8765)"
    )
    parser.add_argument(
        "--gateway",
        action="store_true",
        help="Start dual-protocol gateway (OSC + JSON-RPC)"
    )
    
    args = parser.parse_args()
    
    if args.gateway:
        from .gateway import run_gateway

        jsonrpc_port = args.port if args.port != 9000 else 8765

        # Use ASCII-only output to avoid Windows console encoding crashes when embedded.
        print("Starting AI Music Generator Gateway (OSC + JSON-RPC)")
        print(f"  OSC recv: {args.host}:{args.port}")
        print(f"  OSC send: {args.host}:{args.send_port}")
        print(f"  JSON-RPC: http://{args.host}:{jsonrpc_port}")
        print(f"  Verbose: {args.verbose}")
        print()

        run_gateway(
            osc_host=args.host,
            osc_recv_port=args.port,
            osc_send_port=args.send_port,
            jsonrpc_host=args.host,
            jsonrpc_port=jsonrpc_port,
            verbose=args.verbose,
        )
        return

    if args.jsonrpc:
        from .jsonrpc_server import run_jsonrpc_server
        
        jsonrpc_port = args.port if args.port != 9000 else 8765
        print("Starting AI Music Generator JSON-RPC Server")
        print(f"  Listening on: http://{args.host}:{jsonrpc_port}")
        print(f"  Verbose: {args.verbose}")
        print()
        
        run_jsonrpc_server(
            host=args.host,
            port=jsonrpc_port,
            verbose=args.verbose,
        )
    else:
        # Import here to avoid the RuntimeWarning
        from .osc_server import run_server
        
        print("Starting AI Music Generator OSC Server")
        print(f"  Receiving on port: {args.port}")
        print(f"  Sending to port: {args.send_port}")
        print(f"  Verbose: {args.verbose}")
        print()
        
        run_server(
            recv_port=args.port,
            send_port=args.send_port,
            host=args.host,
            verbose=args.verbose,
        )


if __name__ == "__main__":
    main()
