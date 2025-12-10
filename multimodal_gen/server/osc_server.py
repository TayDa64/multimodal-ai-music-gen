"""
OSC Server Module

Main OSC server implementation for JUCE ↔ Python communication.
Handles incoming OSC messages and dispatches responses.
"""

from __future__ import annotations

import json
import signal
import sys
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from pythonosc import dispatcher, osc_server, udp_client
    from pythonosc.osc_message_builder import OscMessageBuilder
    OSC_AVAILABLE = True
except ImportError:
    OSC_AVAILABLE = False

from .config import (
    ServerConfig,
    OSCAddresses,
    GenerationStep,
    ErrorCode,
    DEFAULT_CONFIG,
)
from .worker import (
    GenerationWorker,
    GenerationRequest,
    GenerationResult,
    InstrumentScanWorker,
)


class MusicGenOSCServer:
    """
    OSC Server for the Multimodal AI Music Generator.
    
    Handles bidirectional communication with JUCE client:
    - Receives generation requests
    - Sends progress updates
    - Sends completion/error notifications
    
    Example:
        ```python
        server = MusicGenOSCServer(config=ServerConfig(verbose=True))
        server.start()  # Blocking - runs until shutdown
        ```
    
    Or with custom callbacks:
        ```python
        server = MusicGenOSCServer()
        server.on_generation_start = lambda req: print(f"Starting: {req.prompt}")
        server.start_async()  # Non-blocking
        
        # Later
        server.stop()
        ```
    """
    
    def __init__(self, config: Optional[ServerConfig] = None):
        """
        Initialize the OSC server.
        
        Args:
            config: Server configuration (uses DEFAULT_CONFIG if None)
        """
        if not OSC_AVAILABLE:
            raise ImportError(
                "python-osc is required for server mode. "
                "Install with: pip install python-osc"
            )
        
        self.config = config or DEFAULT_CONFIG
        
        # OSC components
        self._dispatcher = dispatcher.Dispatcher()
        self._server: Optional[osc_server.ThreadingOSCUDPServer] = None
        self._client: Optional[udp_client.SimpleUDPClient] = None
        
        # Workers
        self._gen_worker: Optional[GenerationWorker] = None
        self._instrument_worker: Optional[InstrumentScanWorker] = None
        
        # State
        self._running = False
        self._server_thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        
        # Callbacks for external integration (optional)
        self.on_generation_start: Optional[callable] = None
        self.on_generation_complete: Optional[callable] = None
        self.on_error: Optional[callable] = None
        
        # Setup message handlers
        self._setup_handlers()
    
    def _setup_handlers(self):
        """Register OSC message handlers with dispatcher."""
        self._dispatcher.map(OSCAddresses.GENERATE, self._handle_generate)
        self._dispatcher.map(OSCAddresses.CANCEL, self._handle_cancel)
        self._dispatcher.map(OSCAddresses.ANALYZE, self._handle_analyze)
        self._dispatcher.map(OSCAddresses.GET_INSTRUMENTS, self._handle_get_instruments)
        self._dispatcher.map(OSCAddresses.PING, self._handle_ping)
        self._dispatcher.map(OSCAddresses.SHUTDOWN, self._handle_shutdown)
        
        # Default handler for unknown messages
        self._dispatcher.set_default_handler(self._handle_unknown)
    
    def start(self, handle_signals: bool = True):
        """
        Start the server (blocking).
        
        This will block the current thread until shutdown is requested.
        Use start_async() for non-blocking operation.
        
        Args:
            handle_signals: Whether to setup signal handlers (disable for embedded use)
        """
        self._initialize()
        
        self._log(f"🎵 Music Generation OSC Server")
        self._log(f"   Listening on {self.config.host}:{self.config.recv_port}")
        self._log(f"   Sending to {self.config.host}:{self.config.send_port}")
        self._log(f"   Press Ctrl+C to stop")
        self._log("")
        
        # Setup signal handlers for graceful shutdown (only if requested)
        # Note: In VS Code terminals, signal handling can be problematic
        if handle_signals:
            try:
                signal.signal(signal.SIGINT, self._signal_handler)
                signal.signal(signal.SIGTERM, self._signal_handler)
            except (ValueError, OSError):
                # Signal handling not available in this context
                pass
        
        self._running = True
        
        try:
            self._server.serve_forever()
        except KeyboardInterrupt:
            self._log("\nReceived keyboard interrupt")
        except Exception as e:
            self._log(f"Server error: {e}")
        
        # Only stop if we're still marked as running (wasn't already stopped)
        if self._running:
            self.stop()
    
    def start_async(self) -> threading.Thread:
        """
        Start the server in a background thread.
        
        Returns:
            Thread object running the server
        """
        self._initialize()
        
        self._running = True
        self._server_thread = threading.Thread(
            target=self._server.serve_forever,
            name="OSCServer",
            daemon=True
        )
        self._server_thread.start()
        
        self._log(f"🎵 OSC Server started on {self.config.host}:{self.config.recv_port}")
        
        return self._server_thread
    
    def stop(self):
        """Stop the server gracefully."""
        if not self._running:
            return
        
        self._log("Shutting down server...")
        self._running = False
        
        # Shutdown workers
        if self._gen_worker:
            self._gen_worker.shutdown(wait=True, timeout=10.0)
        
        if self._instrument_worker:
            self._instrument_worker.shutdown()
        
        # Shutdown OSC server
        if self._server:
            self._server.shutdown()
        
        self._log("Server stopped.")
    
    def is_running(self) -> bool:
        """Check if server is running."""
        return self._running
    
    def _initialize(self):
        """Initialize server components."""
        # Create OSC server
        self._server = osc_server.ThreadingOSCUDPServer(
            (self.config.host, self.config.recv_port),
            self._dispatcher
        )
        
        # Create OSC client for sending messages
        self._client = udp_client.SimpleUDPClient(
            self.config.host,
            self.config.send_port
        )
        
        # Create workers
        self._gen_worker = GenerationWorker(
            max_workers=self.config.max_workers,
            progress_callback=self._on_progress,
            completion_callback=self._on_generation_complete,
            error_callback=self._on_error,
        )
        
        self._instrument_worker = InstrumentScanWorker(
            completion_callback=self._on_instruments_loaded,
            error_callback=self._on_error,
        )
    
    # =========================================================================
    # OSC Message Handlers
    # =========================================================================
    
    def _handle_generate(self, address: str, *args):
        """
        Handle /generate message.
        
        Expected args (JSON string):
            {
                "prompt": "G-Funk beat with smooth synths",
                "bpm": 0,           // 0 = auto
                "key": "",          // Empty = auto
                "output_dir": "",   // Empty = default
                "instruments": [],  // List of paths
                "render_audio": true,
                "export_stems": false,
                "export_mpc": false
            }
        """
        self._log(f"📥 Received: {address}")
        
        # Check if already busy
        if self._gen_worker and self._gen_worker.is_busy():
            self._send_error(
                ErrorCode.SERVER_BUSY,
                "Server is busy with another generation"
            )
            return
        
        try:
            # Parse JSON argument
            if not args:
                self._send_error(ErrorCode.MISSING_PARAMETER, "No parameters provided")
                return
            
            data = json.loads(args[0]) if isinstance(args[0], str) else {}
            
            # Validate prompt
            prompt = data.get("prompt", "").strip()
            if not prompt:
                self._send_error(ErrorCode.INVALID_PROMPT, "Prompt is required")
                return
            
            # Build request
            request = GenerationRequest(
                prompt=prompt,
                bpm=int(data.get("bpm", 0)),
                key=data.get("key", ""),
                output_dir=data.get("output_dir", self.config.default_output_dir),
                instruments=data.get("instruments", self.config.instrument_paths),
                soundfont=data.get("soundfont", self.config.default_soundfont or ""),
                render_audio=data.get("render_audio", self.config.auto_render_audio),
                export_stems=data.get("export_stems", self.config.auto_export_stems),
                export_mpc=data.get("export_mpc", self.config.auto_export_mpc),
                reference_url=data.get("reference_url", ""),
                verbose=data.get("verbose", self.config.verbose),
            )
            
            self._log(f"   Prompt: \"{request.prompt[:50]}...\"" if len(request.prompt) > 50 else f"   Prompt: \"{request.prompt}\"")
            
            # Optional callback
            if self.on_generation_start:
                self.on_generation_start(request)
            
            # Submit to worker
            task_id = self._gen_worker.submit(request)
            self._log(f"   Task ID: {task_id}")
            
            # Send acknowledgment
            self._send_status("generation_started", {"task_id": task_id})
            
        except json.JSONDecodeError as e:
            self._send_error(ErrorCode.INVALID_MESSAGE, f"Invalid JSON: {e}")
        except Exception as e:
            self._send_error(ErrorCode.UNKNOWN, str(e))
    
    def _handle_cancel(self, address: str, *args):
        """Handle /cancel message."""
        self._log(f"📥 Received: {address}")
        
        task_id = args[0] if args else None
        
        if self._gen_worker:
            cancelled = self._gen_worker.cancel(task_id)
            if cancelled:
                self._log("   Generation cancelled")
                self._send_status("cancelled", {"task_id": task_id})
            else:
                self._send_error(
                    ErrorCode.UNKNOWN,
                    "No active generation to cancel"
                )
    
    def _handle_analyze(self, address: str, *args):
        """Handle /analyze message for analyzing existing files."""
        self._log(f"📥 Received: {address}")
        
        # TODO: Implement file analysis
        self._send_error(
            ErrorCode.UNKNOWN,
            "Analyze feature not yet implemented"
        )
    
    def _handle_get_instruments(self, address: str, *args):
        """
        Handle /instruments message.
        
        Expected args (JSON string):
            {
                "paths": ["path/to/kit1", "path/to/kit2"],
                "cache_dir": "optional/cache/dir"
            }
        """
        self._log(f"📥 Received: {address}")
        
        try:
            data = json.loads(args[0]) if args else {}
            paths = data.get("paths", [])
            cache_dir = data.get("cache_dir", str(Path(self.config.default_output_dir)))
            
            if not paths:
                self._send_error(
                    ErrorCode.MISSING_PARAMETER,
                    "No instrument paths provided"
                )
                return
            
            self._log(f"   Scanning {len(paths)} directories...")
            
            scan_id = self._instrument_worker.scan(paths, cache_dir)
            self._send_status("scan_started", {"scan_id": scan_id})
            
        except json.JSONDecodeError as e:
            self._send_error(ErrorCode.INVALID_MESSAGE, f"Invalid JSON: {e}")
        except Exception as e:
            self._send_error(ErrorCode.UNKNOWN, str(e))
    
    def _handle_ping(self, address: str, *args):
        """Handle /ping message for health check."""
        self._send_message(OSCAddresses.PONG, json.dumps({
            "status": "ok",
            "busy": self._gen_worker.is_busy() if self._gen_worker else False,
            "timestamp": time.time(),
        }))
    
    def _handle_shutdown(self, address: str, *args):
        """Handle /shutdown message for graceful shutdown."""
        self._log(f"📥 Received: {address}")
        self._send_status("shutdown_started", {})
        
        # Schedule shutdown on main thread
        threading.Thread(target=self.stop, daemon=True).start()
    
    def _handle_unknown(self, address: str, *args):
        """Handle unknown OSC messages."""
        self._log(f"⚠️  Unknown message: {address} {args}")
    
    # =========================================================================
    # Worker Callbacks
    # =========================================================================
    
    def _on_progress(self, step: str, percent: float, message: str):
        """Called by worker to report progress."""
        self._send_message(OSCAddresses.PROGRESS, json.dumps({
            "step": step,
            "percent": percent,
            "message": message,
        }))
        
        if self.config.verbose:
            bar_width = 20
            filled = int(bar_width * percent)
            bar = "█" * filled + "░" * (bar_width - filled)
            self._log(f"   [{bar}] {percent*100:5.1f}% - {message}", end="\r")
            if percent >= 1.0:
                print()  # New line after completion
    
    def _on_generation_complete(self, result: GenerationResult):
        """Called by worker when generation completes."""
        self._send_message(OSCAddresses.COMPLETE, json.dumps(result.to_dict()))
        
        self._log(f"✅ Generation complete: {result.task_id}")
        if result.midi_path:
            self._log(f"   MIDI: {Path(result.midi_path).name}")
        if result.audio_path:
            self._log(f"   Audio: {Path(result.audio_path).name}")
        
        if self.on_generation_complete:
            self.on_generation_complete(result)
    
    def _on_instruments_loaded(self, result: Dict[str, Any]):
        """Called when instrument scanning completes."""
        self._send_message(OSCAddresses.INSTRUMENTS_LOADED, json.dumps(result))
        
        self._log(f"🎸 Instruments loaded: {result.get('count', 0)} total")
        if self.config.verbose:
            for source, count in result.get("sources", {}).items():
                self._log(f"   {Path(source).name}: {count}")
    
    def _on_error(self, error_code: int, message: str):
        """Called by worker on error."""
        self._send_error(error_code, message)
        
        if self.on_error:
            self.on_error(error_code, message)
    
    # =========================================================================
    # OSC Message Sending
    # =========================================================================
    
    def _send_message(self, address: str, *args):
        """Send an OSC message to the client."""
        if self._client:
            try:
                self._client.send_message(address, args)
            except Exception as e:
                self._log(f"⚠️  Failed to send message: {e}")
    
    def _send_error(self, code: int, message: str):
        """Send an error message to the client."""
        self._log(f"❌ Error [{code}]: {message}")
        
        self._send_message(OSCAddresses.ERROR, json.dumps({
            "code": code,
            "message": message,
            "recoverable": code not in (
                ErrorCode.SHUTDOWN_IN_PROGRESS,
                ErrorCode.WORKER_CRASHED,
            ),
        }))
    
    def _send_status(self, status: str, data: Dict[str, Any]):
        """Send a status update to the client."""
        self._send_message(OSCAddresses.STATUS, json.dumps({
            "status": status,
            **data,
        }))
    
    # =========================================================================
    # Utilities
    # =========================================================================
    
    def _log(self, message: str, end: str = "\n"):
        """Log a message if verbose mode is enabled or it's important."""
        # Always log important messages (errors, status changes)
        important = any(c in message for c in ("✅", "❌", "⚠️", "🎵", "📥"))
        
        if self.config.verbose or important:
            print(message, end=end, flush=True)
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        # Only handle if we're actually running
        if not self._running:
            return
        
        signal_name = signal.Signals(signum).name if hasattr(signal, 'Signals') else str(signum)
        self._log(f"\n📛 Received signal: {signal_name}")
        self.stop()
        sys.exit(0)


def run_server(
    recv_port: int = 9000,
    send_port: int = 9001,
    host: str = "127.0.0.1",
    verbose: bool = False,
    **kwargs
):
    """
    Convenience function to start the OSC server.
    
    Args:
        recv_port: Port to receive messages (default 9000)
        send_port: Port to send messages (default 9001)
        host: Host address (default localhost)
        verbose: Enable verbose logging
        **kwargs: Additional config options
    
    Example:
        ```python
        from multimodal_gen.server import run_server
        run_server(verbose=True)  # Blocking
        ```
    """
    config = ServerConfig(
        recv_port=recv_port,
        send_port=send_port,
        host=host,
        verbose=verbose,
        **kwargs
    )
    
    server = MusicGenOSCServer(config)
    server.start()
