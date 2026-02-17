"""
Dual-Protocol Gateway (OSC + JSON-RPC)

Starts both the OSC server (JUCE) and JSON-RPC server (Copilot-Liku CLI)
using a shared ServerConfig. Each server currently manages its own worker,
but they share ports/config for consistent behavior. Intended as a single
entrypoint so Copilot and JUCE can run side-by-side without manual setup.
"""

from __future__ import annotations

import signal
import threading
import time
from typing import Optional

from .config import ServerConfig
from .osc_server import MusicGenOSCServer
from .jsonrpc_server import MusicGenJSONRPCServer
from .worker import GenerationWorker


class GatewayServer:
    """Boots OSC and JSON-RPC servers together."""

    def __init__(
        self,
        osc_host: str = "127.0.0.1",
        osc_recv_port: int = 9000,
        osc_send_port: int = 9001,
        jsonrpc_host: str = "127.0.0.1",
        jsonrpc_port: int = 8765,
        verbose: bool = False,
        log_file: Optional[str] = None,
        config: Optional[ServerConfig] = None,
    ) -> None:
        self.config = config or ServerConfig(
            host=osc_host,
            recv_port=osc_recv_port,
            send_port=osc_send_port,
            verbose=verbose,
            log_file=log_file,
        )

        # Default log file for GUI-embedded runs (stdout isn't visible).
        if not self.config.log_file:
            try:
                from pathlib import Path

                self.config.log_file = str(Path(self.config.default_output_dir) / "gateway.log")
            except Exception:
                pass
        self.osc_host = osc_host
        self.osc_recv_port = osc_recv_port
        self.osc_send_port = osc_send_port
        self.jsonrpc_host = jsonrpc_host
        self.jsonrpc_port = jsonrpc_port

        self._osc_server: Optional[MusicGenOSCServer] = None
        self._json_server: Optional[MusicGenJSONRPCServer] = None
        self._worker: Optional[GenerationWorker] = None
        self._running = False

    # ------------------------------------------------------------------ #
    # Callback fan-out helpers so both servers get updates
    # ------------------------------------------------------------------ #

    def _dispatch_progress(self, step: str, percent: float, message: str) -> None:
        """Fan progress updates to both servers if they exist."""
        if self._json_server:
            try:
                self._json_server._on_progress(step, percent, message)  # type: ignore[attr-defined]
            except Exception:
                pass
        if self._osc_server:
            try:
                self._osc_server._on_progress(step, percent, message)  # type: ignore[attr-defined]
            except Exception:
                pass

    def _dispatch_complete(self, result) -> None:
        """Fan completion to both servers if they exist."""
        if self._json_server:
            try:
                self._json_server._on_complete(result)  # type: ignore[attr-defined]
            except Exception:
                pass
        if self._osc_server:
            try:
                self._osc_server._on_generation_complete(result)  # type: ignore[attr-defined]
            except Exception:
                pass

    def _dispatch_error(self, code: int, message: str) -> None:
        """Fan errors to both servers if they exist."""
        if self._json_server:
            try:
                self._json_server._on_error(code, message)  # type: ignore[attr-defined]
            except Exception:
                pass
        if self._osc_server:
            try:
                self._osc_server._on_error(code, message)  # type: ignore[attr-defined]
            except Exception:
                pass

    def start(self) -> None:
        """Start both servers (blocking)."""
        self._start_servers()
        self._install_signal_handlers()
        self._running = True
        try:
            while self._running:
                time.sleep(0.5)
        except KeyboardInterrupt:
            self.stop()

    def start_async(self) -> None:
        """Start both servers in background threads."""
        self._start_servers(async_mode=True)
        self._running = True

    def stop(self) -> None:
        """Stop both servers gracefully."""
        self._running = False
        try:
            if self._osc_server:
                self._osc_server.stop()
        finally:
            if self._json_server:
                self._json_server.stop()

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    def _start_servers(self, async_mode: bool = False) -> None:
        """Create and start OSC + JSON-RPC servers."""
        # Shared worker
        if self._worker is None:
            self._worker = GenerationWorker(
                max_workers=self.config.max_workers,
                progress_callback=self._dispatch_progress,
                completion_callback=self._dispatch_complete,
                error_callback=self._dispatch_error,
            )

        # OSC server for JUCE
        self._osc_server = MusicGenOSCServer(config=self.config, worker=self._worker)
        if async_mode:
            self._osc_server.start_async()
        else:
            threading.Thread(
                target=self._osc_server.start,
                kwargs={"handle_signals": False},
                name="Gateway-OSC",
                daemon=True,
            ).start()

        # JSON-RPC server for Copilot-Liku CLI
        self._json_server = MusicGenJSONRPCServer(
            config=self.config,
            host=self.jsonrpc_host,
            port=self.jsonrpc_port,
            worker=self._worker,
        )
        if async_mode:
            self._json_server.start_async()
        else:
            threading.Thread(
                target=self._json_server.start,
                name="Gateway-JSONRPC",
                daemon=True,
            ).start()

        print(
            f"[Gateway] OSC {self.osc_host}:{self.osc_recv_port}/{self.osc_send_port} "
            f"+ JSON-RPC {self.jsonrpc_host}:{self.jsonrpc_port} started"
        )

    def _install_signal_handlers(self) -> None:
        def _handler(signum, _frame):
            print(f"[Gateway] Caught signal {signum}, stopping...")
            self.stop()

        try:
            signal.signal(signal.SIGINT, _handler)
            signal.signal(signal.SIGTERM, _handler)
        except Exception:
            # Some environments (Windows) may not support all signals
            pass


def run_gateway(
    osc_host: str = "127.0.0.1",
    osc_recv_port: int = 9000,
    osc_send_port: int = 9001,
    jsonrpc_host: str = "127.0.0.1",
    jsonrpc_port: int = 8765,
    verbose: bool = False,
    log_file: Optional[str] = None,
) -> None:
    """Convenience entry to run the dual-protocol gateway (blocking)."""
    gw = GatewayServer(
        osc_host=osc_host,
        osc_recv_port=osc_recv_port,
        osc_send_port=osc_send_port,
        jsonrpc_host=jsonrpc_host,
        jsonrpc_port=jsonrpc_port,
        verbose=verbose,
        log_file=log_file,
    )
    gw.start()
