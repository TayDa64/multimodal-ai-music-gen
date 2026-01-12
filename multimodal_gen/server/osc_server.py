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
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional
import dataclasses
from enum import Enum

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
    SCHEMA_VERSION,
)
from .worker import (
    GenerationWorker,
    GenerationRequest,
    GenerationResult,
    InstrumentScanWorker,
)

# Try to import expansion manager
try:
    from ..expansion_manager import ExpansionManager, create_expansion_manager
    EXPANSION_AVAILABLE = True
except ImportError:
    ExpansionManager = None
    create_expansion_manager = None
    EXPANSION_AVAILABLE = False


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
        
        # Expansion Manager
        # ExpansionManager is an optional dependency in some environments; keep annotation permissive
        self._expansion_manager: Optional[Any] = None
        if EXPANSION_AVAILABLE:
            # Use factory function to auto-discover expansions in standard locations
            # This finds ../expansions automatically
            self._expansion_manager = create_expansion_manager(auto_scan=True)
        
        # State
        self._running = False
        self._server_thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._current_request_id: Optional[str] = None  # Track current request for correlation
        self._current_fx_chain: Dict[str, Any] = {}     # FX chain configuration for render parity
        # Phase 5.2: persisted control overrides (merged into /generate + /regenerate)
        self._control_overrides: Dict[str, Any] = {}
        
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
        self._dispatcher.map(OSCAddresses.REGENERATE, self._handle_regenerate)
        self._dispatcher.map(OSCAddresses.FX_CHAIN, self._handle_fx_chain)
        self._dispatcher.map(OSCAddresses.CONTROLS_SET, self._handle_controls_set)
        self._dispatcher.map(OSCAddresses.CONTROLS_CLEAR, self._handle_controls_clear)
        self._dispatcher.map(OSCAddresses.GET_INSTRUMENTS, self._handle_get_instruments)
        self._dispatcher.map(OSCAddresses.PING, self._handle_ping)
        self._dispatcher.map(OSCAddresses.SHUTDOWN, self._handle_shutdown)
        
        # Take management handlers
        self._dispatcher.map(OSCAddresses.SELECT_TAKE, self._handle_select_take)
        self._dispatcher.map(OSCAddresses.COMP_TAKES, self._handle_comp_takes)
        self._dispatcher.map(OSCAddresses.RENDER_TAKE, self._handle_render_take)
        
        # Expansion handlers
        self._dispatcher.map(OSCAddresses.EXPANSION_LIST, self._handle_expansion_list)
        self._dispatcher.map(OSCAddresses.EXPANSION_INSTRUMENTS, self._handle_expansion_instruments)
        self._dispatcher.map(OSCAddresses.EXPANSION_RESOLVE, self._handle_expansion_resolve)
        self._dispatcher.map(OSCAddresses.EXPANSION_IMPORT, self._handle_expansion_import)
        self._dispatcher.map(OSCAddresses.EXPANSION_SCAN, self._handle_expansion_scan)
        self._dispatcher.map(OSCAddresses.EXPANSION_ENABLE, self._handle_expansion_enable)
        
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
                "request_id": "uuid",  // For request/response correlation
                "schema_version": 1,   // Protocol version
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
        
        # Parse request_id early for error correlation
        request_id = ""
        try:
            if args:
                data = json.loads(args[0]) if isinstance(args[0], str) else {}
                request_id = data.get("request_id", "")
                self._current_request_id = request_id
        except:
            pass
        
        # Check if already busy
        if self._gen_worker and self._gen_worker.is_busy():
            self._send_error(
                ErrorCode.SERVER_BUSY,
                "Server is busy with another generation",
                request_id=request_id
            )
            return
        
        try:
            # Parse JSON argument
            if not args:
                self._send_error(ErrorCode.MISSING_PARAMETER, "No parameters provided", request_id=request_id)
                return
            
            data = json.loads(args[0]) if isinstance(args[0], str) else {}
            
            # Extract and validate request_id
            request_id = data.get("request_id", "")
            if not request_id:
                # Protocol hardening: Require request_id
                self._log("   ⚠️  Missing request_id in generate request. Generating temporary ID.")
                request_id = str(uuid.uuid4())
            
            schema_version = data.get("schema_version", 1)
            
            # Schema version handling: reject major mismatches, warn on minor
            if schema_version != SCHEMA_VERSION:
                self._log(f"   ⚠️ Schema version mismatch: client={schema_version}, server={SCHEMA_VERSION}")
                # For major version differences (e.g., client=2, server=1), reject
                if schema_version > SCHEMA_VERSION:
                    self._send_error(
                        ErrorCode.SCHEMA_VERSION_MISMATCH,
                        f"Client schema version {schema_version} is newer than server version {SCHEMA_VERSION}. Please update the server.",
                        request_id=request_id
                    )
                    return
                # For older clients, we can try best-effort but send a warning status
                self._send_status("schema_version_warning", {
                    "request_id": request_id,
                    "client_version": schema_version,
                    "server_version": SCHEMA_VERSION,
                    "message": f"Client uses schema v{schema_version}, server uses v{SCHEMA_VERSION}. Proceeding with best-effort compatibility."
                })
            
            # Validate prompt
            prompt = data.get("prompt", "").strip()
            if not prompt:
                self._send_error(ErrorCode.INVALID_PROMPT, "Prompt is required", request_id=request_id)
                return

            # Phase 5.2: accept optional controls in "options" and/or top-level
            raw_options = data.get("options", {})
            options: Dict[str, Any] = raw_options if isinstance(raw_options, dict) else {}

            # Top-level convenience fields (mirrors CLI args/pipeline fields)
            for k in (
                "tension_arc_shape",
                "tension_intensity",
                "motif_mode",
                "num_motifs",
                "preset",
                "style_preset",
                "production_preset",
                "seed",
            ):
                if k in data and k not in options:
                    options[k] = data.get(k)

            # Merge persisted overrides with per-request options (per-request wins)
            if self._control_overrides:
                options = {**self._control_overrides, **options}

            # duration_bars can be either top-level or inside options.
            # Backward-compat: JUCE currently sends "bars".
            duration_bars = data.get(
                "duration_bars",
                data.get("bars", options.get("duration_bars", options.get("bars", 8))),
            )
            try:
                duration_bars = int(duration_bars)
            except Exception:
                duration_bars = 8

            # Take generation (optional)
            num_takes = data.get("num_takes", options.get("num_takes", 1))
            take_variation = data.get("take_variation", options.get("take_variation", ""))
            try:
                num_takes = int(num_takes)
            except Exception:
                num_takes = 1
            try:
                take_variation = str(take_variation) if take_variation is not None else ""
            except Exception:
                take_variation = ""
            
            # Build request with request_id
            request = GenerationRequest(
                prompt=prompt,
                request_id=request_id,
                schema_version=schema_version,
                genre=data.get("genre", ""),  # Genre ID from JUCE GenreSelector
                bpm=int(data.get("bpm", 0)),
                key=data.get("key", ""),
                duration_bars=duration_bars,
                output_dir=data.get("output_dir", self.config.default_output_dir),
                instruments=data.get("instruments", self.config.instrument_paths),
                soundfont=data.get("soundfont", self.config.default_soundfont or ""),
                render_audio=data.get("render_audio", self.config.auto_render_audio),
                export_stems=data.get("export_stems", self.config.auto_export_stems),
                export_mpc=data.get("export_mpc", self.config.auto_export_mpc),
                reference_url=data.get("reference_url", ""),
                verbose=data.get("verbose", self.config.verbose),
                num_takes=num_takes,
                take_variation=take_variation,
                options=options,
            )
            
            self._log(f"   Request ID: {request_id}" if request_id else "   Request ID: (none)")
            self._log(f"   Genre: {request.genre}" if request.genre else "   Genre: (auto-detect)")
            self._log(f"   Prompt: \"{request.prompt[:50]}...\"" if len(request.prompt) > 50 else f"   Prompt: \"{request.prompt}\"")
            
            # Optional callback
            if self.on_generation_start:
                self.on_generation_start(request)
            
            # Submit to worker
            task_id = self._gen_worker.submit(request)
            self._log(f"   Task ID: {task_id}")
            
            # Send acknowledgment with request_id
            self._send_status("generation_started", {"task_id": task_id, "request_id": request_id})
            
        except json.JSONDecodeError as e:
            self._send_error(ErrorCode.INVALID_MESSAGE, f"Invalid JSON: {e}")
        except Exception as e:
            self._send_error(ErrorCode.UNKNOWN, str(e))
    
    def _handle_cancel(self, address: str, *args):
        """Handle /cancel message with request_id correlation."""
        self._log(f"📥 Received: {address}")
        
        task_id = args[0] if args else None
        
        # Capture request_id before cancellation clears it
        request_id = self._current_request_id or ""
        
        if self._gen_worker:
            cancelled = self._gen_worker.cancel(task_id)
            if cancelled:
                self._log("   Generation cancelled")
                # Include request_id in cancel status for correlation
                self._send_status("cancelled", {
                    "task_id": task_id,
                    "request_id": request_id,
                })
                # Clear current request after sending status
                self._current_request_id = None
            else:
                self._send_error(
                    ErrorCode.UNKNOWN,
                    "No active generation to cancel",
                    request_id=request_id
                )
    
    def _handle_analyze(self, address: str, *args):
        """Handle /analyze message for analyzing existing files."""
        self._log(f"📥 Received: {address}")

        # Parse request_id early for error correlation
        request_id = ""
        try:
            if args:
                data = json.loads(args[0]) if isinstance(args[0], str) else {}
                request_id = data.get("request_id", "")
        except Exception:
            data = {}

        try:
            if not args:
                self._send_error(ErrorCode.MISSING_PARAMETER, "No parameters provided", request_id=request_id)
                return

            data = json.loads(args[0]) if isinstance(args[0], str) else {}

            request_id = data.get("request_id", "")
            schema_version = int(data.get("schema_version", 1))

            if schema_version != SCHEMA_VERSION:
                self._log(f"   ⚠️ Schema version mismatch: client={schema_version}, server={SCHEMA_VERSION}")

            source_url = (data.get("url") or "").strip()
            source_path = (data.get("path") or "").strip()
            verbose = bool(data.get("verbose", self.config.verbose))

            if not source_url and not source_path:
                self._send_error(
                    ErrorCode.MISSING_PARAMETER,
                    "Analyze requires either 'url' or 'path'",
                    request_id=request_id,
                )
                return

            # Import lazily so missing optional deps only affect /analyze
            from ..reference_analyzer import ReferenceAnalyzer

            analyzer = ReferenceAnalyzer(verbose=verbose)

            if source_path:
                path = Path(source_path)
                if not path.exists():
                    self._send_error(
                        ErrorCode.FILE_NOT_FOUND,
                        f"File not found: {source_path}",
                        request_id=request_id,
                    )
                    return
                analysis = analyzer.analyze_file(str(path))
                source_kind = "file"
            else:
                analysis = analyzer.analyze_url(source_url)
                source_kind = "url"

            def _to_jsonable(obj: Any) -> Any:
                if dataclasses.is_dataclass(obj):
                    return {k: _to_jsonable(v) for k, v in dataclasses.asdict(obj).items()}
                if isinstance(obj, Enum):
                    return obj.value
                if isinstance(obj, (list, tuple)):
                    return [_to_jsonable(v) for v in obj]
                if isinstance(obj, dict):
                    return {str(k): _to_jsonable(v) for k, v in obj.items()}
                return obj

            analysis_dict = _to_jsonable(analysis)

            response: Dict[str, Any] = {
                "request_id": request_id,
                "schema_version": schema_version,
                "success": True,
                "source_kind": source_kind,
                "analysis": analysis_dict,
                "prompt_hints": analysis.to_prompt_hints(include_genre=False),
                "generation_params": analysis.to_generation_params(),
            }

            self._send_message(OSCAddresses.ANALYZE_RESULT, json.dumps(response))

        except json.JSONDecodeError as e:
            self._send_error(ErrorCode.INVALID_MESSAGE, f"Invalid JSON: {e}", request_id=request_id)
        except ImportError as e:
            # librosa / yt-dlp are optional; surface a clear message
            self._send_error(ErrorCode.UNKNOWN, str(e), request_id=request_id)
        except Exception as e:
            self._send_error(ErrorCode.UNKNOWN, str(e), request_id=request_id)
    
    def _handle_regenerate(self, address: str, *args):
        """
        Handle /regenerate message for sectional regeneration.
        
        Regenerates a specific bar range of the current project.
        
        Expected args (JSON string):
            {
                "schema_version": 1,
                "request_id": "uuid",
                "start_bar": 4,      // 0-indexed bar to start regeneration
                "end_bar": 8,        // 0-indexed bar to end (exclusive)
                "tracks": ["drums", "bass"],  // Optional: which tracks to regenerate
                "seed_strategy": "new",  // "new" for fresh seed, "derived" to vary existing
                "prompt": "optional override prompt for this section",
                "options": {}
            }
        """
        self._log(f"📥 Received: {address}")
        
        request_id = ""
        try:
            if not args:
                self._send_error(ErrorCode.MISSING_PARAMETER, "No parameters provided")
                return
            
            data = json.loads(args[0]) if isinstance(args[0], str) else {}
            
            request_id = data.get("request_id", str(uuid.uuid4()))
            schema_version = int(data.get("schema_version", 1))
            
            # Validate schema version
            if schema_version > SCHEMA_VERSION:
                self._send_error(
                    ErrorCode.SCHEMA_VERSION_MISMATCH,
                    f"Client schema {schema_version} is newer than server {SCHEMA_VERSION}",
                    request_id=request_id
                )
                return
            
            start_bar = int(data.get("start_bar", 0))
            end_bar = int(data.get("end_bar", start_bar + 4))
            tracks = data.get("tracks", [])  # Empty = all tracks
            seed_strategy = data.get("seed_strategy", "new")
            prompt_override = data.get("prompt", "")
            raw_options = data.get("options", {})
            options: Dict[str, Any] = raw_options if isinstance(raw_options, dict) else {}

            # Merge persisted overrides (Phase 5.2) with per-request options (per-request wins)
            if self._control_overrides:
                options = {**self._control_overrides, **options}
            
            # Validate bar range
            if start_bar < 0 or end_bar <= start_bar:
                self._send_error(
                    ErrorCode.INVALID_MESSAGE,
                    f"Invalid bar range: {start_bar}-{end_bar}",
                    request_id=request_id
                )
                return
            
            self._log(f"   Regenerating bars {start_bar}-{end_bar}, tracks={tracks or 'all'}")
            
            # Check if worker is busy
            if self._gen_worker and self._gen_worker.is_busy():
                self._send_error(
                    ErrorCode.GENERATION_FAILED,
                    "Generation worker is busy. Cancel current generation first.",
                    request_id=request_id
                )
                return
            
            # Build regeneration request - this is a specialized generate request
            from ..prompt_parser import PromptParser
            
            # Get base parameters from current state or use defaults
            base_bpm = options.get("bpm", 92)
            base_key = options.get("key", "C")
            base_mode = options.get("mode", "minor")
            
            # Parse prompt for additional parameters
            parser = PromptParser()
            parsed = parser.parse(prompt_override) if prompt_override else parser.parse("")
            
            # Build request with regeneration metadata
            from .worker import GenerationRequest
            
            regen_request = GenerationRequest(
                request_id=request_id,
                prompt=prompt_override or parsed.raw_prompt,
                bpm=parsed.bpm or base_bpm,
                key=parsed.key or base_key,
                mode=parsed.mode or base_mode,
                duration_bars=end_bar - start_bar,
                genre=parsed.genre or options.get("genre", ""),
                options={
                    **options,
                    "regeneration": True,
                    "start_bar": start_bar,
                    "end_bar": end_bar,
                    "target_tracks": tracks,
                    "seed_strategy": seed_strategy,
                }
            )
            
            # Send status update
            self._send_status("regeneration_started", {
                "request_id": request_id,
                "start_bar": start_bar,
                "end_bar": end_bar,
                "tracks": tracks
            }, request_id=request_id)
            
            # Submit to worker
            self._gen_worker.submit(regen_request)
            
        except json.JSONDecodeError as e:
            self._send_error(ErrorCode.INVALID_MESSAGE, f"Invalid JSON: {e}", request_id=request_id)
        except Exception as e:
            self._log(f"⚠️  Regenerate error: {e}")
            self._send_error(ErrorCode.UNKNOWN, str(e), request_id=request_id)
    
    def _handle_fx_chain(self, address: str, *args):
        """
        Handle /fx_chain message for FX chain configuration.
        
        Stores the FX chain configuration to be applied during generation/rendering.
        
        Expected args (JSON string):
            {
                "schema_version": 1,
                "fx_chain": {
                    "master": [{"type": "eq", "enabled": true, "params": {...}}, ...],
                    "drums": [...],
                    "bass": [...],
                    "melodic": [...]
                }
            }
        """
        self._log(f"📥 Received: {address}")
        
        try:
            if not args:
                self._log("   ⚠️  No FX chain data provided")
                return
            
            data = json.loads(args[0]) if isinstance(args[0], str) else {}
            schema_version = int(data.get("schema_version", 1))
            fx_chain = data.get("fx_chain", {})
            
            if schema_version > SCHEMA_VERSION:
                self._log(f"   ⚠️ Schema version mismatch: client={schema_version}, server={SCHEMA_VERSION}")
            
            # Store FX chain configuration for use during generation
            self._current_fx_chain = fx_chain
            
            # Log summary
            chain_summary = []
            for track, effects in fx_chain.items():
                if effects:
                    chain_summary.append(f"{track}({len(effects)} fx)")
            
            self._log(f"   🎛️  FX chain stored: {', '.join(chain_summary) or 'empty'}")
            
            # Send acknowledgment
            self._send_status("fx_chain_received", {
                "tracks": list(fx_chain.keys()),
                "total_effects": sum(len(v) for v in fx_chain.values())
            })
            
        except json.JSONDecodeError as e:
            self._log(f"   ⚠️  Invalid FX chain JSON: {e}")
        except Exception as e:
            self._log(f"   ⚠️  FX chain error: {e}")

    def _handle_controls_set(self, address: str, *args):
        """Handle /controls/set to persistently store generation overrides.

        Expected args (JSON string):
            {
              "schema_version": 1,
              "request_id": "uuid",
              "overrides": {
                 "tension_arc_shape": "linear_build",
                 "tension_intensity": 0.8,
                 "motif_mode": "on",          // auto|on|off
                 "num_motifs": 2,
                 "preset": "legendary",
                 "style_preset": "g_funk_90s",
                 "production_preset": "wide_modern",
                 "duration_bars": 8,
                 "seed": 123,
                 "num_takes": 1,
                 "take_variation": "timing"
              }
            }
        """
        self._log(f"📥 Received: {address}")

        request_id = ""
        try:
            if not args:
                self._send_error(ErrorCode.MISSING_PARAMETER, "No parameters provided")
                return

            data = json.loads(args[0]) if isinstance(args[0], str) else {}

            request_id = data.get("request_id", str(uuid.uuid4()))
            schema_version = int(data.get("schema_version", 1))
            if schema_version > SCHEMA_VERSION:
                self._send_error(
                    ErrorCode.SCHEMA_VERSION_MISMATCH,
                    f"Client schema {schema_version} is newer than server {SCHEMA_VERSION}",
                    request_id=request_id,
                )
                return

            raw_overrides = data.get("overrides", {})
            overrides = raw_overrides if isinstance(raw_overrides, dict) else {}

            allowed_keys = {
                "tension_arc_shape",
                "tension_intensity",
                "motif_mode",
                "num_motifs",
                "preset",
                "style_preset",
                "production_preset",
                "duration_bars",
                "seed",
                "num_takes",
                "take_variation",
            }

            updated: Dict[str, Any] = {}
            for k, v in overrides.items():
                if k in allowed_keys:
                    self._control_overrides[k] = v
                    updated[k] = v

            self._send_status(
                "controls_updated",
                {"request_id": request_id, "updated": updated, "overrides": self._control_overrides},
                request_id=request_id,
            )

        except json.JSONDecodeError as e:
            self._send_error(ErrorCode.INVALID_MESSAGE, f"Invalid JSON: {e}", request_id=request_id)
        except Exception as e:
            self._send_error(ErrorCode.UNKNOWN, str(e), request_id=request_id)

    def _handle_controls_clear(self, address: str, *args):
        """Handle /controls/clear to remove persisted overrides.

        Expected args (JSON string):
            {
              "schema_version": 1,
              "request_id": "uuid",
              "keys": ["tension_intensity", "motif_mode"]  // optional
            }
        If keys are omitted/empty, clears all overrides.
        """
        self._log(f"📥 Received: {address}")

        request_id = ""
        try:
            if not args:
                self._send_error(ErrorCode.MISSING_PARAMETER, "No parameters provided")
                return

            data = json.loads(args[0]) if isinstance(args[0], str) else {}

            request_id = data.get("request_id", str(uuid.uuid4()))
            schema_version = int(data.get("schema_version", 1))
            if schema_version > SCHEMA_VERSION:
                self._send_error(
                    ErrorCode.SCHEMA_VERSION_MISMATCH,
                    f"Client schema {schema_version} is newer than server {SCHEMA_VERSION}",
                    request_id=request_id,
                )
                return

            keys = data.get("keys")
            cleared: List[str] = []
            if keys and isinstance(keys, list):
                for k in keys:
                    ks = str(k)
                    if ks in self._control_overrides:
                        self._control_overrides.pop(ks, None)
                        cleared.append(ks)
            else:
                cleared = list(self._control_overrides.keys())
                self._control_overrides.clear()

            self._send_status(
                "controls_cleared",
                {"request_id": request_id, "cleared": cleared, "overrides": self._control_overrides},
                request_id=request_id,
            )

        except json.JSONDecodeError as e:
            self._send_error(ErrorCode.INVALID_MESSAGE, f"Invalid JSON: {e}", request_id=request_id)
        except Exception as e:
            self._send_error(ErrorCode.UNKNOWN, str(e), request_id=request_id)
    
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
            
            # If no paths provided, use default configured paths
            if not paths:
                paths = self.config.instrument_paths
                
            if not paths:
                self._send_error(
                    ErrorCode.MISSING_PARAMETER,
                    "No instrument paths provided and no defaults configured"
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
            "schema_version": SCHEMA_VERSION,
        }))
    
    def _handle_shutdown(self, address: str, *args):
        """
        Handle /shutdown message for graceful shutdown.
        
        Expected args (JSON string):
            {
                "request_id": "uuid"  // For acknowledgment correlation
            }
        """
        self._log(f"📥 Received: {address}")
        
        # Parse request_id from shutdown request
        request_id = ""
        try:
            if args:
                data = json.loads(args[0]) if isinstance(args[0], str) else {}
                request_id = data.get("request_id", "")
        except:
            pass
        
        # Send acknowledgment with request_id
        self._send_status("shutdown_acknowledged", {
            "request_id": request_id,
            "timestamp": time.time(),
        })
        
        # Schedule shutdown on main thread (allow time for ack to be sent)
        def delayed_shutdown():
            time.sleep(0.5)  # Give 500ms for acknowledgment to be sent
            self.stop()
        
        threading.Thread(target=delayed_shutdown, daemon=True).start()
    
    def _handle_unknown(self, address: str, *args):
        """Handle unknown OSC messages."""
        self._log(f"⚠️  Unknown message: {address} {args}")
    
    # =========================================================================
    # Expansion Handlers
    # =========================================================================
    
    def _handle_expansion_list(self, address: str, *args):
        """Handle /expansion/list - return list of loaded expansions."""
        self._log(f"📥 Received: {address}")
        
        if not self._expansion_manager:
            self._send_error(ErrorCode.UNKNOWN, "Expansion manager not available")
            return
        
        try:
            expansions = self._expansion_manager.list_expansions()
            categories = self._expansion_manager.get_categories()
            
            response = {
                "expansions": expansions,
                "categories": categories,
            }
            
            self._send_message(OSCAddresses.EXPANSION_LIST_RESPONSE, json.dumps(response))
            self._log(f"   Sent {len(expansions)} expansions")
            
        except Exception as e:
            self._send_error(ErrorCode.UNKNOWN, f"Failed to list expansions: {e}")
    
    def _handle_expansion_instruments(self, address: str, *args):
        """
        Handle /expansion/instruments - list instruments in an expansion.
        
        Expected args (JSON string):
            {
                "expansion_id": "funk_o_rama"
            }
        """
        self._log(f"📥 Received: {address}")
        
        if not self._expansion_manager:
            self._send_error(ErrorCode.UNKNOWN, "Expansion manager not available")
            return
        
        try:
            data = json.loads(args[0]) if args else {}
            expansion_id = data.get("expansion_id", "")
            
            instruments = self._expansion_manager.list_instruments(expansion_id=expansion_id)
            
            self._send_message(OSCAddresses.EXPANSION_INSTRUMENTS_RESPONSE, json.dumps(instruments))
            self._log(f"   Sent {len(instruments)} instruments for {expansion_id}")
            
        except json.JSONDecodeError as e:
            self._send_error(ErrorCode.INVALID_MESSAGE, f"Invalid JSON: {e}")
        except Exception as e:
            self._send_error(ErrorCode.UNKNOWN, f"Failed to list instruments: {e}")
    
    def _handle_expansion_resolve(self, address: str, *args):
        """
        Handle /expansion/resolve - resolve instrument with intelligent matching.
        
        Expected args (JSON string):
            {
                "instrument": "krar",
                "genre": "eskista"
            }
        """
        self._log(f"📥 Received: {address}")
        
        if not self._expansion_manager:
            self._send_error(ErrorCode.UNKNOWN, "Expansion manager not available")
            return
        
        try:
            data = json.loads(args[0]) if args else {}
            instrument = data.get("instrument", "")
            genre = data.get("genre", "")
            
            if not instrument:
                self._send_error(ErrorCode.MISSING_PARAMETER, "Instrument name required")
                return
            
            result = self._expansion_manager.resolve_instrument(instrument, genre)
            
            self._send_message(OSCAddresses.EXPANSION_RESOLVE_RESPONSE, json.dumps(result.to_dict()))
            self._log(f"   Resolved '{instrument}' -> '{result.name}' ({result.match_type.value})")
            
        except json.JSONDecodeError as e:
            self._send_error(ErrorCode.INVALID_MESSAGE, f"Invalid JSON: {e}")
        except Exception as e:
            self._send_error(ErrorCode.UNKNOWN, f"Failed to resolve instrument: {e}")
    
    def _handle_expansion_import(self, address: str, *args):
        """
        Handle /expansion/import - import a new expansion pack.
        
        Expected args (JSON string):
            {
                "path": "/path/to/expansion"
            }
        """
        self._log(f"📥 Received: {address}")
        
        if not self._expansion_manager:
            self._send_error(ErrorCode.UNKNOWN, "Expansion manager not available")
            return
        
        try:
            data = json.loads(args[0]) if args else {}
            path = data.get("path", "")
            
            if not path:
                self._send_error(ErrorCode.MISSING_PARAMETER, "Expansion path required")
                return
            
            success = self._expansion_manager.add_expansion(path)
            
            if success:
                self._send_status("expansion_imported", {"path": path})
                self._log(f"   Imported expansion from: {path}")
            else:
                self._send_error(ErrorCode.UNKNOWN, f"Failed to import expansion from: {path}")
            
        except json.JSONDecodeError as e:
            self._send_error(ErrorCode.INVALID_MESSAGE, f"Invalid JSON: {e}")
        except Exception as e:
            self._send_error(ErrorCode.UNKNOWN, f"Failed to import expansion: {e}")
    
    def _handle_expansion_scan(self, address: str, *args):
        """
        Handle /expansion/scan - scan directory for expansions.
        
        Expected args (JSON string):
            {
                "directory": "/path/to/expansions"
            }
        """
        self._log(f"📥 Received: {address}")
        
        if not self._expansion_manager:
            self._send_error(ErrorCode.UNKNOWN, "Expansion manager not available")
            return
        
        try:
            data = json.loads(args[0]) if args else {}
            directory = data.get("directory", "")
            
            if not directory:
                self._send_error(ErrorCode.MISSING_PARAMETER, "Directory path required")
                return
            
            count = self._expansion_manager.scan_expansions(directory)
            
            self._send_status("expansion_scan_complete", {
                "directory": directory,
                "count": count,
            })
            self._log(f"   Scanned {directory}: found {count} expansions")
            
        except json.JSONDecodeError as e:
            self._send_error(ErrorCode.INVALID_MESSAGE, f"Invalid JSON: {e}")
        except Exception as e:
            self._send_error(ErrorCode.UNKNOWN, f"Failed to scan expansions: {e}")
    
    def _handle_expansion_enable(self, address: str, *args):
        """
        Handle /expansion/enable - enable or disable an expansion.
        
        Expected args (JSON string):
            {
                "expansion_id": "funk_o_rama",
                "enabled": true
            }
        """
        self._log(f"📥 Received: {address}")
        
        if not self._expansion_manager:
            self._send_error(ErrorCode.UNKNOWN, "Expansion manager not available")
            return
        
        try:
            data = json.loads(args[0]) if args else {}
            expansion_id = data.get("expansion_id", "")
            enabled = data.get("enabled", True)
            
            if not expansion_id:
                self._send_error(ErrorCode.MISSING_PARAMETER, "Expansion ID required")
                return
            
            self._expansion_manager.enable_expansion(expansion_id, enabled)
            
            self._send_status("expansion_enable_changed", {
                "expansion_id": expansion_id,
                "enabled": enabled,
            })
            self._log(f"   Expansion '{expansion_id}' enabled={enabled}")
            
        except json.JSONDecodeError as e:
            self._send_error(ErrorCode.INVALID_MESSAGE, f"Invalid JSON: {e}")
        except Exception as e:
            self._send_error(ErrorCode.UNKNOWN, f"Failed to change expansion state: {e}")
    
    # =========================================================================
    # Take Management Handlers
    # =========================================================================
    
    def _handle_select_take(self, address: str, *args):
        """
        Handle /take/select - select a specific take for a track.
        
        Expected args (JSON string):
            {
                "request_id": "uuid",
                "track": "drums",
                "take_id": "take_001"
            }
        """
        self._log(f"📥 Received: {address}")
        
        try:
            data = json.loads(args[0]) if args else {}
            request_id = data.get("request_id", "")
            track = data.get("track", "")
            take_id = data.get("take_id", "")
            
            if not track or not take_id:
                self._send_error(ErrorCode.MISSING_PARAMETER, 
                                 "track and take_id required", 
                                 request_id=request_id)
                return
            
            # Store selected take (will be used during render)
            if not hasattr(self, '_selected_takes'):
                self._selected_takes = {}
            self._selected_takes[track] = take_id
            
            self._send_message(OSCAddresses.TAKE_SELECTED, json.dumps({
                "request_id": request_id,
                "track": track,
                "take_id": take_id,
                "success": True
            }))
            
            self._log(f"   🎬 Selected take '{take_id}' for track '{track}'")
            
        except json.JSONDecodeError as e:
            self._send_error(ErrorCode.INVALID_MESSAGE, f"Invalid JSON: {e}")
        except Exception as e:
            self._send_error(ErrorCode.UNKNOWN, str(e))
    
    def _handle_comp_takes(self, address: str, *args):
        """
        Handle /take/comp - composite takes across bar regions.
        
        Expected args (JSON string):
            {
                "request_id": "uuid",
                "track": "drums",
                "regions": [
                    {"start_bar": 0, "end_bar": 4, "take_id": "take_001"},
                    {"start_bar": 4, "end_bar": 8, "take_id": "take_002"}
                ]
            }
        """
        self._log(f"📥 Received: {address}")
        
        try:
            data = json.loads(args[0]) if args else {}
            request_id = data.get("request_id", "")
            track = data.get("track", "")
            regions = data.get("regions", [])
            
            if not track:
                self._send_error(ErrorCode.MISSING_PARAMETER, 
                                 "track required", 
                                 request_id=request_id)
                return
            
            if not regions:
                self._send_error(ErrorCode.MISSING_PARAMETER, 
                                 "regions array required", 
                                 request_id=request_id)
                return
            
            # Validate regions
            for region in regions:
                if "start_bar" not in region or "end_bar" not in region or "take_id" not in region:
                    self._send_error(ErrorCode.INVALID_MESSAGE, 
                                     "Each region requires start_bar, end_bar, take_id",
                                     request_id=request_id)
                    return
            
            # Store comp regions for the track
            if not hasattr(self, '_comp_regions'):
                self._comp_regions = {}
            self._comp_regions[track] = regions
            
            self._send_status("comp_regions_set", {
                "request_id": request_id,
                "track": track,
                "region_count": len(regions),
            })
            
            self._log(f"   🎬 Set {len(regions)} comp regions for track '{track}'")
            
        except json.JSONDecodeError as e:
            self._send_error(ErrorCode.INVALID_MESSAGE, f"Invalid JSON: {e}")
        except Exception as e:
            self._send_error(ErrorCode.UNKNOWN, str(e))
    
    def _handle_render_take(self, address: str, *args):
        """
        Handle /take/render - render a specific take or comp to audio.
        
        Expected args (JSON string):
            {
                "request_id": "uuid",
                "track": "drums",
                "take_id": "take_001",  # Optional if using comp
                "use_comp": false,       # If true, use comp regions
                "output_path": "path/to/output.wav"
            }
        """
        self._log(f"📥 Received: {address}")
        
        try:
            data = json.loads(args[0]) if args else {}
            request_id = data.get("request_id", "")
            track = data.get("track", "")
            take_id = data.get("take_id", "")
            use_comp = data.get("use_comp", False)
            output_path = data.get("output_path", "")
            
            if not track:
                self._send_error(ErrorCode.MISSING_PARAMETER, 
                                 "track required", 
                                 request_id=request_id)
                return
            
            if not use_comp and not take_id:
                self._send_error(ErrorCode.MISSING_PARAMETER, 
                                 "take_id required when not using comp",
                                 request_id=request_id)
                return
            
            # TODO: Actually render the take (integrate with audio_renderer)
            # For now, acknowledge receipt
            self._send_message(OSCAddresses.TAKE_RENDERED, json.dumps({
                "request_id": request_id,
                "track": track,
                "take_id": take_id if not use_comp else "comp",
                "output_path": output_path,
                "success": True
            }))
            
            self._log(f"   🎬 Rendered take for track '{track}'")
            
        except json.JSONDecodeError as e:
            self._send_error(ErrorCode.INVALID_MESSAGE, f"Invalid JSON: {e}")
        except Exception as e:
            self._send_error(ErrorCode.UNKNOWN, str(e))
    
    # =========================================================================
    # Worker Callbacks
    # =========================================================================
    
    def _on_progress(self, step: str, percent: float, message: str):
        """Called by worker to report progress."""
        self._send_message(OSCAddresses.PROGRESS, json.dumps({
            "request_id": self._current_request_id or "",
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
        
        # Clear current request_id after completion
        self._current_request_id = None
        
        self._log(f"✅ Generation complete: {result.task_id}")
        if result.request_id:
            self._log(f"   Request ID: {result.request_id}")
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
    
    def _send_error(self, code: int, message: str, request_id: str = ""):
        """Send an error message to the client with request_id correlation."""
        self._log(f"❌ Error [{code}]: {message}")
        
        # Use provided request_id or fall back to current request
        req_id = request_id or self._current_request_id or ""
        
        self._send_message(OSCAddresses.ERROR, json.dumps({
            "request_id": req_id,
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
