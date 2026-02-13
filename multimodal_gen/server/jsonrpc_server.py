"""
JSON-RPC 2.0 Server Module

HTTP-based JSON-RPC server for Electron CLI ↔ Python communication.
Bridges the copilot-Liku-cli frontend to the music generation engine
using the standard JSON-RPC 2.0 protocol over HTTP POST.

Transport:
    HTTP POST on localhost (default port 8765).
    Uses only stdlib modules (http.server, json) — no external deps.

Quick Start:
    ```python
    from multimodal_gen.server import run_jsonrpc_server
    run_jsonrpc_server(port=8765, verbose=True)
    ```

Or standalone:
    ```bash
    python -m multimodal_gen.server --jsonrpc --port 8765
    ```
"""

from __future__ import annotations

import json
import logging
import signal
import sys
import threading
import time
import uuid
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Any, Callable, Dict, List, Optional, Tuple

from .config import (
    ServerConfig,
    ErrorCode,
    SCHEMA_VERSION,
)
from .worker import (
    GenerationWorker,
    GenerationRequest,
    GenerationResult,
    TaskStatus,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# JSON-RPC 2.0 error codes (spec-defined)
# ---------------------------------------------------------------------------

JSONRPC_PARSE_ERROR = -32700
JSONRPC_INVALID_REQUEST = -32600
JSONRPC_METHOD_NOT_FOUND = -32601
JSONRPC_INVALID_PARAMS = -32602
JSONRPC_INTERNAL_ERROR = -32603


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _jsonrpc_response(result: Any, req_id: Any) -> Dict[str, Any]:
    """Build a successful JSON-RPC 2.0 response envelope."""
    return {"jsonrpc": "2.0", "result": result, "id": req_id}


def _jsonrpc_error(
    code: int,
    message: str,
    req_id: Any = None,
    data: Any = None,
) -> Dict[str, Any]:
    """Build a JSON-RPC 2.0 error response envelope."""
    err: Dict[str, Any] = {"code": code, "message": message}
    if data is not None:
        err["data"] = data
    return {"jsonrpc": "2.0", "error": err, "id": req_id}


# ---------------------------------------------------------------------------
# HTTP Request Handler
# ---------------------------------------------------------------------------

class _JSONRPCRequestHandler(BaseHTTPRequestHandler):
    """Thin HTTP handler that delegates POST bodies to the RPC dispatcher."""

    # Silence default stderr logging from BaseHTTPRequestHandler
    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        if getattr(self.server, "verbose", False):
            logger.debug(format, *args)

    # -- CORS preflight (Electron may send OPTIONS) -------------------------
    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(200)
        self._set_cors_headers()
        self.end_headers()

    # -- Main entry: POST ---------------------------------------------------
    def do_POST(self) -> None:  # noqa: N802
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length == 0:
            self._write_json(_jsonrpc_error(
                JSONRPC_PARSE_ERROR,
                "Empty request body",
            ))
            return

        raw = self.rfile.read(content_length)

        try:
            body = json.loads(raw)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            self._write_json(_jsonrpc_error(
                JSONRPC_PARSE_ERROR,
                f"Parse error: {exc}",
            ))
            return

        # Batch requests (array) are not supported — keep it simple.
        if not isinstance(body, dict):
            self._write_json(_jsonrpc_error(
                JSONRPC_INVALID_REQUEST,
                "Batch requests are not supported; send a single object.",
            ))
            return

        # Validate minimal JSON-RPC envelope
        if body.get("jsonrpc") != "2.0" or "method" not in body:
            self._write_json(_jsonrpc_error(
                JSONRPC_INVALID_REQUEST,
                "Missing 'jsonrpc': '2.0' or 'method' field.",
                req_id=body.get("id"),
            ))
            return

        method = body["method"]
        params = body.get("params", {})
        req_id = body.get("id")  # None → notification (no response expected)

        # Dispatch
        rpc_server: MusicGenJSONRPCServer = self.server.rpc_server  # type: ignore[attr-defined]
        response = rpc_server.dispatch(method, params, req_id)

        # JSON-RPC notifications (id is absent) get no response
        if req_id is None:
            self.send_response(204)
            self.end_headers()
            return

        self._write_json(response)

    # -- Health-check GET for browsers / monitoring -------------------------
    def do_GET(self) -> None:  # noqa: N802
        self._write_json({
            "jsonrpc": "2.0",
            "info": "MUSE JSON-RPC 2.0 server",
            "version": SCHEMA_VERSION,
            "hint": "Send a POST with a JSON-RPC 2.0 payload.",
        })

    # -- Helpers ------------------------------------------------------------
    def _write_json(self, obj: Dict[str, Any]) -> None:
        payload = json.dumps(obj, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(200)
        self._set_cors_headers()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _set_cors_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")


# ---------------------------------------------------------------------------
# Main JSON-RPC Server
# ---------------------------------------------------------------------------

class MusicGenJSONRPCServer:
    """
    JSON-RPC 2.0 server for the Multimodal AI Music Generator.

    Handles HTTP POST requests containing JSON-RPC calls from the
    Electron-based copilot-Liku-cli frontend.  Reuses the same
    ``GenerationWorker`` as the OSC server for actual music generation.

    Example:
        ```python
        server = MusicGenJSONRPCServer(port=8765)
        server.start()  # Blocking — runs until shutdown
        ```

    Or non-blocking:
        ```python
        server = MusicGenJSONRPCServer()
        server.start_async()
        # ... do other work ...
        server.stop()
        ```
    """

    def __init__(
        self,
        config: Optional[ServerConfig] = None,
        host: str = "127.0.0.1",
        port: int = 8765,
    ) -> None:
        self.config = config or ServerConfig()
        self.host = host
        self.port = port
        self.verbose = self.config.verbose

        # HTTP server (created in start / start_async)
        self._httpd: Optional[HTTPServer] = None
        self._server_thread: Optional[threading.Thread] = None

        # Worker
        self._worker = GenerationWorker(
            max_workers=self.config.max_workers,
            progress_callback=self._on_progress,
            completion_callback=self._on_complete,
            error_callback=self._on_error,
        )

        # Last session graph (returned by session_state)
        self._session_graph: Any = None
        self._session_lock = threading.Lock()

        # Task result cache (task_id → GenerationResult dict)
        self._results: Dict[str, Dict[str, Any]] = {}
        self._results_lock = threading.Lock()

        # Uptime tracking
        self._start_time: Optional[float] = None

        # Shutdown flag
        self._running = threading.Event()

        # Lazy-initialised MIDI bridge (None until first use)
        self._midi_bridge: Any = None
        self._midi_bridge_lock = threading.Lock()

        # Lazy-initialised embedding service + index (Sprint 4)
        self._embedding_service: Any = None
        self._embedding_index: Any = None
        self._embedding_lock = threading.Lock()

        # Lazy-initialised preference tracker (Sprint 4 — C14)
        self._preference_tracker: Any = None
        self._preference_lock = threading.Lock()

        # Method dispatch table
        self._methods: Dict[str, Callable[..., Any]] = {
            "generate": self._handle_generate,
            "generate_sync": self._handle_generate_sync,
            "get_status": self._handle_get_status,
            "cancel": self._handle_cancel,
            "run_critics": self._handle_run_critics,
            "genre_dna_lookup": self._handle_genre_dna_lookup,
            "genre_blend": self._handle_genre_blend,
            "session_state": self._handle_session_state,
            "midi_bridge_status": self._handle_midi_bridge_status,
            "midi_bridge_play": self._handle_midi_bridge_play,
            "ping": self._handle_ping,
            "shutdown": self._handle_shutdown,
            "search_assets": self._handle_search_assets,
            "build_index": self._handle_build_index,
            "get_preferences": self._handle_get_preferences,
            "record_preference": self._handle_record_preference,
        }

        logger.info(
            "MusicGenJSONRPCServer initialised (host=%s, port=%d)",
            self.host,
            self.port,
        )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the server **blocking** the calling thread.

        Runs until ``stop()`` is called or a SIGINT/SIGTERM is received.
        """
        self._create_httpd()
        self._start_time = time.time()
        self._running.set()

        # Graceful signal handling
        original_sigint = signal.getsignal(signal.SIGINT)
        original_sigterm = signal.getsignal(signal.SIGTERM)

        def _signal_handler(sig: int, frame: Any) -> None:
            logger.info("Signal %d received — shutting down", sig)
            self.stop()

        signal.signal(signal.SIGINT, _signal_handler)
        signal.signal(signal.SIGTERM, _signal_handler)

        logger.info(
            "JSON-RPC server listening on http://%s:%d",
            self.host,
            self.port,
        )
        print(
            f"🎵 MUSE JSON-RPC server listening on "
            f"http://{self.host}:{self.port}"
        )

        try:
            self._httpd.serve_forever()  # type: ignore[union-attr]
        finally:
            signal.signal(signal.SIGINT, original_sigint)
            signal.signal(signal.SIGTERM, original_sigterm)

    def start_async(self) -> None:
        """Start the server in a background daemon thread."""
        self._create_httpd()
        self._start_time = time.time()
        self._running.set()

        self._server_thread = threading.Thread(
            target=self._httpd.serve_forever,  # type: ignore[union-attr]
            name="JSONRPC-Server",
            daemon=True,
        )
        self._server_thread.start()

        logger.info(
            "JSON-RPC server started (async) on http://%s:%d",
            self.host,
            self.port,
        )

    def stop(self) -> None:
        """Gracefully stop the server and the worker."""
        if not self._running.is_set():
            return
        self._running.clear()

        logger.info("Shutting down JSON-RPC server …")

        # Shut down worker first
        try:
            self._worker.shutdown(wait=False, timeout=5.0)
        except Exception:
            pass

        # Shut down HTTP server
        if self._httpd is not None:
            self._httpd.shutdown()
            self._httpd.server_close()
            self._httpd = None

        if self._server_thread is not None:
            self._server_thread.join(timeout=5.0)
            self._server_thread = None

        logger.info("JSON-RPC server stopped.")

    # ------------------------------------------------------------------
    # Dispatch
    # ------------------------------------------------------------------

    def dispatch(
        self,
        method: str,
        params: Any,
        req_id: Any,
    ) -> Dict[str, Any]:
        """Route a JSON-RPC method call to the appropriate handler.

        Args:
            method: RPC method name.
            params: Parameters (dict or list).
            req_id: Client-provided request id.

        Returns:
            JSON-RPC response dict (result or error envelope).
        """
        handler = self._methods.get(method)
        if handler is None:
            return _jsonrpc_error(
                JSONRPC_METHOD_NOT_FOUND,
                f"Method '{method}' not found.",
                req_id=req_id,
            )

        try:
            # Normalise params to a dict for keyword dispatch
            if params is None:
                params = {}
            if isinstance(params, list):
                # Positional → not supported; require named params
                return _jsonrpc_error(
                    JSONRPC_INVALID_PARAMS,
                    "Positional parameters are not supported; use named params.",
                    req_id=req_id,
                )

            result = handler(params)
            return _jsonrpc_response(result, req_id)

        except TypeError as exc:
            return _jsonrpc_error(
                JSONRPC_INVALID_PARAMS,
                f"Invalid params: {exc}",
                req_id=req_id,
            )
        except Exception as exc:
            logger.exception("Internal error in method '%s'", method)
            return _jsonrpc_error(
                JSONRPC_INTERNAL_ERROR,
                f"Internal error: {exc}",
                req_id=req_id,
            )

    # ------------------------------------------------------------------
    # RPC method handlers
    # ------------------------------------------------------------------

    def _handle_generate(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Start asynchronous music generation.

        Returns immediately with ``task_id`` and ``request_id``.
        """
        request = self._build_generation_request(params)
        task_id = self._worker.submit(request)
        return {"task_id": task_id, "request_id": request.request_id}

    def _handle_generate_sync(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Synchronous generation — blocks until the task completes.

        Returns the full ``GenerationResult.to_dict()`` payload.
        """
        request = self._build_generation_request(params)
        task_id = self._worker.submit(request)

        # Poll until the task finishes (with a generous timeout)
        timeout = self.config.generation_timeout
        deadline = time.time() + timeout
        while time.time() < deadline:
            status = self._worker.get_status(task_id)
            if status in (
                TaskStatus.COMPLETED,
                TaskStatus.FAILED,
                TaskStatus.CANCELLED,
            ):
                break
            time.sleep(0.25)
        else:
            return {
                "task_id": task_id,
                "request_id": request.request_id,
                "success": False,
                "error_code": ErrorCode.GENERATION_TIMEOUT,
                "error_message": f"Generation timed out after {timeout}s",
            }

        with self._results_lock:
            result_dict = self._results.get(task_id)

        if result_dict is not None:
            return result_dict

        # Fallback — shouldn't normally reach here
        return {
            "task_id": task_id,
            "request_id": request.request_id,
            "success": False,
            "error_code": ErrorCode.UNKNOWN,
            "error_message": "Result not available",
        }

    def _handle_get_status(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Return current status (and result if complete) for a task."""
        task_id = params.get("task_id")
        if not task_id:
            raise TypeError("Missing required param: task_id")

        status = self._worker.get_status(task_id)
        if status is None:
            return {"task_id": task_id, "found": False}

        resp: Dict[str, Any] = {
            "task_id": task_id,
            "found": True,
            "status": status.value,
        }

        if status in (
            TaskStatus.COMPLETED,
            TaskStatus.FAILED,
            TaskStatus.CANCELLED,
        ):
            with self._results_lock:
                result_dict = self._results.get(task_id)
            if result_dict is not None:
                resp["result"] = result_dict

        return resp

    def _handle_cancel(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Cancel a running or pending generation task."""
        task_id = params.get("task_id")
        if not task_id:
            raise TypeError("Missing required param: task_id")

        cancelled = self._worker.cancel(task_id)
        return {"task_id": task_id, "cancelled": cancelled}

    def _handle_run_critics(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Run quality-gate critics on a MIDI file.

        Params:
            midi_path: Path to the MIDI file to evaluate.
            genre: Genre identifier for context-aware evaluation.

        Returns:
            CriticReport as a dict with metrics and overall verdict.
        """
        # Lazy import to keep startup fast
        from ..intelligence.critics import run_all_critics, CriticReport  # noqa: F811

        midi_path = params.get("midi_path")
        if not midi_path:
            raise TypeError("Missing required param: midi_path")

        # run_all_critics accepts analysis data, not raw file paths.
        # The caller should supply pre-extracted data when available.
        voicings = params.get("voicings")
        bass_notes = params.get("bass_notes")
        kick_ticks = params.get("kick_ticks")
        tolerance_ticks = params.get("tolerance_ticks", 60)
        tension_curve = params.get("tension_curve")
        note_density_per_beat = params.get("note_density_per_beat")

        report: CriticReport = run_all_critics(
            voicings=voicings,
            bass_notes=bass_notes,
            kick_ticks=kick_ticks,
            tolerance_ticks=tolerance_ticks,
            tension_curve=tension_curve,
            note_density_per_beat=note_density_per_beat,
        )

        return {
            "overall_passed": report.overall_passed,
            "summary": report.summary,
            "metrics": [
                {
                    "name": m.name,
                    "value": m.value,
                    "threshold": m.threshold,
                    "passed": m.passed,
                    "details": m.details,
                }
                for m in report.metrics
            ],
        }

    def _handle_genre_dna_lookup(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Look up the 10-dimensional DNA vector for a genre.

        Params:
            genre: Genre identifier (e.g. ``"trap_soul"``).

        Returns:
            Dict with ``genre``, ``vector`` (10 floats), and dimension names.
        """
        from ..intelligence.genre_dna import get_genre_dna

        genre = params.get("genre")
        if not genre:
            raise TypeError("Missing required param: genre")

        vec = get_genre_dna(genre)
        if vec is None:
            return {"genre": genre, "found": False, "vector": None}

        return {
            "genre": genre,
            "found": True,
            "vector": vec.to_list(),
            "dimensions": [
                "rhythmic_density",
                "swing",
                "harmonic_complexity",
                "syncopation",
                "bass_drum_coupling",
                "repetition_variation",
                "register_spread",
                "timbral_brightness",
                "dynamic_range",
                "tension_resolution",
            ],
        }

    def _handle_genre_blend(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Blend multiple genre DNA vectors with weights.

        Params:
            genres: List of ``{"genre": str, "weight": float}`` objects.

        Returns:
            Blended vector, sources, description, and suggested tempo.
        """
        from ..intelligence.genre_dna import blend_genres

        genres_list = params.get("genres")
        if not genres_list or not isinstance(genres_list, list):
            raise TypeError("Missing or invalid param: genres (expected list)")

        sources: list[tuple[str, float]] = [
            (item["genre"], float(item.get("weight", 1.0)))
            for item in genres_list
            if isinstance(item, dict) and "genre" in item
        ]

        if not sources:
            raise TypeError("No valid genre entries in 'genres' list")

        fusion = blend_genres(sources)

        return {
            "vector": fusion.vector.to_list(),
            "sources": fusion.sources,
            "description": fusion.description,
            "suggested_tempo": fusion.suggested_tempo,
            "dimensions": [
                "rhythmic_density",
                "swing",
                "harmonic_complexity",
                "syncopation",
                "bass_drum_coupling",
                "repetition_variation",
                "register_spread",
                "timbral_brightness",
                "dynamic_range",
                "tension_resolution",
            ],
        }

    def _handle_session_state(self, _params: Dict[str, Any]) -> Any:
        """Return the last generated SessionGraph as a dict, or null."""
        with self._session_lock:
            if self._session_graph is None:
                return None
            try:
                return self._session_graph.to_dict()
            except Exception:
                return None

    def _handle_ping(self, _params: Dict[str, Any]) -> Dict[str, Any]:
        """Health check / keep-alive."""
        uptime = time.time() - self._start_time if self._start_time else 0.0
        return {
            "status": "ok",
            "version": SCHEMA_VERSION,
            "uptime": round(uptime, 2),
            "worker_busy": self._worker.is_busy(),
        }

    def _handle_midi_bridge_status(self, _params: Dict[str, Any]) -> Dict[str, Any]:
        """Return the current state of the MIDI bridge.

        Lazy-initialises the bridge on first call.
        """
        bridge = self._get_midi_bridge()
        if bridge is None:
            return {
                "connected": False,
                "error": "MIDI bridge unavailable (missing python-rtmidi or mido)",
            }
        return bridge.get_status()

    def _handle_midi_bridge_play(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Start non-blocking MIDI playback through the bridge.

        Params:
            midi_path: Path to the ``.mid`` file to play.
            tempo_override: Optional BPM override (float).
        """
        bridge = self._get_midi_bridge()
        if bridge is None:
            return {
                "playing": False,
                "error": "MIDI bridge unavailable (missing python-rtmidi or mido)",
            }

        midi_path = params.get("midi_path")
        if not midi_path:
            raise TypeError("Missing required param: midi_path")

        tempo_override = params.get("tempo_override")
        if tempo_override is not None:
            tempo_override = float(tempo_override)

        # Ensure the port is open (auto-detect)
        if not bridge.is_connected():
            opened = bridge.open_port()
            if not opened:
                return {
                    "playing": False,
                    "error": (
                        "Could not open a MIDI port.  "
                        "Install loopMIDI and create a virtual port."
                    ),
                }

        bridge.play_file(midi_path, tempo_override=tempo_override)
        return {"playing": True, "midi_path": midi_path}

    def _get_midi_bridge(self) -> Any:
        """Lazy-init and return the MidiBridge singleton (or None)."""
        with self._midi_bridge_lock:
            if self._midi_bridge is not None:
                return self._midi_bridge
            try:
                from ..intelligence.midi_bridge import create_midi_bridge

                self._midi_bridge = create_midi_bridge()
                return self._midi_bridge
            except ImportError as exc:
                logger.warning("MIDI bridge not available: %s", exc)
                return None

    # -- Embedding / search handlers (Sprint 4) ---------------------------

    def _handle_search_assets(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Semantic search over the asset embedding index.

        Params:
            query (str): Natural-language search string **(required)**.
            top_k (int): Maximum results (default 10).
            type_filter (list[str]): Restrict to asset types.
            genre (str): Boost results matching this genre.

        Returns:
            ``{results: [{id, name, asset_type, similarity, description, metadata}], count}``
        """
        query = params.get("query")
        if not query:
            raise TypeError("Missing required param: query")

        from ..intelligence.embeddings import (
            EmbeddingService,
            VectorIndex,
            search_assets,
            build_embedding_index,
            _BUILTIN_DESCRIPTIONS,
        )

        svc, idx = self._get_embedding_singletons()

        top_k = int(params.get("top_k", 10))
        type_filter = params.get("type_filter")
        genre = params.get("genre")

        results = search_assets(
            query=query,
            index=idx,
            embedding_service=svc,
            top_k=top_k,
            type_filter=type_filter,
            genre=genre,
        )

        return {
            "results": [
                {
                    "id": r.id,
                    "name": r.name,
                    "asset_type": r.asset_type,
                    "similarity": r.similarity,
                    "description": r.description,
                    "metadata": r.metadata,
                }
                for r in results
            ],
            "count": len(results),
        }

    def _handle_build_index(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Build or rebuild the asset embedding index.

        Params:
            descriptions (list[dict]): Optional list of asset descriptions.
                Each dict must have ``id``, ``type``, ``name``, ``description``
                and optionally ``metadata``.  If omitted the built-in catalog
                (~30 entries) is used.

        Returns:
            ``{count: int, builtin: bool}``
        """
        from ..intelligence.embeddings import (
            build_embedding_index,
            _BUILTIN_DESCRIPTIONS,
        )

        descriptions = params.get("descriptions")
        use_builtin = descriptions is None
        if use_builtin:
            descriptions = _BUILTIN_DESCRIPTIONS

        svc, _ = self._get_embedding_singletons()
        new_index = build_embedding_index(descriptions, svc)

        # Replace the cached index
        with self._embedding_lock:
            self._embedding_index = new_index

        return {"count": new_index.size, "builtin": use_builtin}

    def _get_embedding_singletons(
        self,
    ) -> tuple:
        """Lazy-init EmbeddingService + VectorIndex singletons."""
        with self._embedding_lock:
            if self._embedding_service is None:
                from ..intelligence.embeddings import (
                    EmbeddingService,
                    VectorIndex,
                    build_embedding_index,
                    _BUILTIN_DESCRIPTIONS,
                )

                self._embedding_service = EmbeddingService()
                self._embedding_index = build_embedding_index(
                    _BUILTIN_DESCRIPTIONS, self._embedding_service
                )
            return self._embedding_service, self._embedding_index

    # -- Preference handlers (Sprint 4 — C14) ---------------------------

    def _handle_get_preferences(self, _params: Dict[str, Any]) -> Dict[str, Any]:
        """Return current user preferences.

        Returns:
            Full ``UserPreferences`` dict.
        """
        tracker = self._get_preference_tracker()
        return tracker.preferences.to_dict()

    def _handle_record_preference(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Record a preference signal.

        Params:
            signal_type (str): "accept", "reject", "modify", etc.
            domain (str): "harmony", "rhythm", "sound", etc.
            dimension (str): Key from PreferenceDimensions.
            direction (str): "increase", "decrease", "neutral".
            confidence (float): 0.0–1.0.

        Returns:
            ``{ok: true, signal_count, confidence}``
        """
        from ..intelligence.preferences import PreferenceSignal
        from datetime import datetime, timezone

        signal = PreferenceSignal(
            timestamp=datetime.now(timezone.utc).isoformat(),
            signal_type=str(params.get("signal_type", "accept")),
            domain=str(params.get("domain", "harmony")),
            dimension=str(params.get("dimension", "harmonic_complexity")),
            direction=str(params.get("direction", "neutral")),
            confidence=float(params.get("confidence", 0.5)),
            context=params.get("context", {}),
        )
        tracker = self._get_preference_tracker()
        tracker.record_signal(signal)
        tracker.save()
        return {
            "ok": True,
            "signal_count": tracker.preferences.signal_count,
            "confidence": round(tracker.preferences.confidence, 4),
        }

    def _get_preference_tracker(self):
        """Lazy-init PreferenceTracker singleton."""
        with self._preference_lock:
            if self._preference_tracker is None:
                from ..intelligence.preferences import PreferenceTracker

                self._preference_tracker = PreferenceTracker()
            return self._preference_tracker

    def _handle_shutdown(self, _params: Dict[str, Any]) -> Dict[str, Any]:
        """Initiate graceful shutdown (returns before fully stopped)."""
        # Close MIDI bridge if it was initialised
        with self._midi_bridge_lock:
            if self._midi_bridge is not None:
                try:
                    self._midi_bridge.close_port()
                except Exception:
                    pass
                self._midi_bridge = None

        threading.Thread(
            target=self.stop,
            name="JSONRPC-Shutdown",
            daemon=True,
        ).start()
        return {"status": "shutting_down"}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_generation_request(
        self,
        params: Dict[str, Any],
    ) -> GenerationRequest:
        """Construct a ``GenerationRequest`` from JSON-RPC params."""
        prompt = params.get("prompt")
        if not prompt:
            raise TypeError("Missing required param: prompt")

        return GenerationRequest(
            prompt=prompt,
            request_id=params.get("request_id", str(uuid.uuid4())[:8]),
            schema_version=SCHEMA_VERSION,
            genre=params.get("genre", ""),
            bpm=int(params.get("bpm", 0)),
            key=params.get("key", ""),
            mode=params.get("mode", ""),
            duration_bars=int(params.get("duration_bars", 8)),
            output_dir=params.get("output_dir", self.config.default_output_dir or ""),
            instruments=params.get("instruments", []),
            soundfont=params.get("soundfont", ""),
            render_audio=params.get("render_audio", self.config.auto_render_audio),
            export_stems=params.get("export_stems", self.config.auto_export_stems),
            export_mpc=params.get("export_mpc", self.config.auto_export_mpc),
            num_takes=int(params.get("num_takes", 1)),
            take_variation=params.get("take_variation", ""),
            options=params.get("options", {}),
        )

    def _create_httpd(self) -> None:
        """Create and configure the underlying HTTPServer."""
        self._httpd = HTTPServer(
            (self.host, self.port),
            _JSONRPCRequestHandler,
        )
        # Attach a back-reference so the handler can reach the dispatcher
        self._httpd.rpc_server = self  # type: ignore[attr-defined]
        self._httpd.verbose = self.verbose  # type: ignore[attr-defined]

    # -- Worker callbacks --------------------------------------------------

    def _on_progress(self, step: str, percent: float, message: str) -> None:
        """Called by GenerationWorker on progress updates."""
        if self.verbose:
            logger.debug("Progress: %s %.0f%% — %s", step, percent * 100, message)

    def _on_complete(self, result: GenerationResult) -> None:
        """Called by GenerationWorker when a task finishes."""
        result_dict = result.to_dict()
        with self._results_lock:
            self._results[result.task_id] = result_dict

        # Try to capture the session graph from the last generation
        self._try_capture_session_graph(result)

        logger.info(
            "Task %s completed (success=%s, duration=%.1fs)",
            result.task_id,
            result.success,
            result.duration,
        )

    def _on_error(self, error_code: int, message: str) -> None:
        """Called by GenerationWorker on non-result errors."""
        logger.error("Worker error %d: %s", error_code, message)

    def _try_capture_session_graph(self, result: GenerationResult) -> None:
        """Attempt to load the SessionGraph from the generation output.

        The session manifest is written alongside the MIDI file by
        ``main.run_generation()``.
        """
        if not result.success or not result.midi_path:
            return

        try:
            from pathlib import Path as _Path

            midi_p = _Path(result.midi_path)
            manifest = midi_p.parent / "session_manifest.json"
            if manifest.exists():
                # Lazy import
                from ..session_graph import SessionGraph

                data = json.loads(manifest.read_text(encoding="utf-8"))
                with self._session_lock:
                    self._session_graph = SessionGraph.from_dict(data)
                logger.debug("Captured SessionGraph from %s", manifest)
        except Exception as exc:
            logger.debug("Could not capture SessionGraph: %s", exc)


# ---------------------------------------------------------------------------
# Convenience entry point
# ---------------------------------------------------------------------------

def run_jsonrpc_server(
    host: str = "127.0.0.1",
    port: int = 8765,
    verbose: bool = False,
) -> None:
    """Start the JSON-RPC server (blocking).

    Args:
        host: Bind address (default ``127.0.0.1``).
        port: TCP port (default ``8765``).
        verbose: Enable debug logging.
    """
    if verbose:
        logging.basicConfig(
            level=logging.DEBUG,
            format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        )
    else:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        )

    config = ServerConfig(verbose=verbose)
    server = MusicGenJSONRPCServer(config=config, host=host, port=port)
    server.start()


# ---------------------------------------------------------------------------
# Standalone entry
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="MUSE AI Music Generator — JSON-RPC 2.0 Server",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Bind address (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port", "-p",
        type=int,
        default=8765,
        help="TCP port (default: 8765)",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable debug logging",
    )
    args = parser.parse_args()

    run_jsonrpc_server(host=args.host, port=args.port, verbose=args.verbose)
