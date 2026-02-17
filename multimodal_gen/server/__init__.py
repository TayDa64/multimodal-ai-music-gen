"""
Server Module for Multimodal AI Music Generator

Provides OSC server functionality for JUCE integration.
The server enables bidirectional communication between the
Python backend and JUCE-based GUI.

Quick Start:
    ```python
    from multimodal_gen.server import run_server
    run_server(verbose=True)
    ```

Or via CLI:
    ```bash
    python main.py --server --port 9000
    ```

Components:
    - MusicGenOSCServer: Main OSC server class
    - GenerationWorker: Background task execution
    - ServerConfig: Configuration management
    - run_server: Convenience function

Protocol:
    See config.py for OSCAddresses defining the message protocol.
"""

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
    TaskStatus,
    ProgressCallback,
)

from .osc_server import (
    MusicGenOSCServer,
    run_server,
)

from .jsonrpc_server import (
    MusicGenJSONRPCServer,
    run_jsonrpc_server,
)
from .gateway import (
    GatewayServer,
    run_gateway,
)

__all__ = [
    # Configuration
    "ServerConfig",
    "OSCAddresses",
    "GenerationStep",
    "ErrorCode",
    "DEFAULT_CONFIG",
    
    # Workers
    "GenerationWorker",
    "GenerationRequest",
    "GenerationResult",
    "InstrumentScanWorker",
    "TaskStatus",
    "ProgressCallback",
    
    # Server (OSC)
    "MusicGenOSCServer",
    "run_server",
    
    # Server (JSON-RPC)
    "MusicGenJSONRPCServer",
    "run_jsonrpc_server",

    # Dual-protocol Gateway
    "GatewayServer",
    "run_gateway",
]
