"""
Server Configuration Module

Centralized configuration for the OSC server.
All constants and defaults are defined here for easy modification.
"""

from dataclasses import dataclass, field
from typing import Optional
from pathlib import Path
import os


@dataclass
class ServerConfig:
    """
    Configuration for the Music Generation OSC Server.
    
    Attributes:
        recv_port: Port to receive OSC messages from JUCE client
        send_port: Port to send OSC messages to JUCE client
        host: Host address to bind to
        max_workers: Maximum concurrent generation tasks
        generation_timeout: Timeout for single generation (seconds)
        heartbeat_interval: Interval for heartbeat/ping (seconds)
        auto_render_audio: Whether to render audio by default
        default_output_dir: Default directory for generated files
        verbose: Enable verbose logging
    """
    # Network Configuration
    recv_port: int = 9000
    send_port: int = 9001
    host: str = "127.0.0.1"
    
    # Worker Configuration
    max_workers: int = 1  # Sequential generation for consistency
    generation_timeout: int = 300  # 5 minutes max
    
    # Heartbeat & Health
    heartbeat_interval: float = 5.0
    connection_timeout: float = 30.0
    
    # Generation Defaults
    auto_render_audio: bool = True
    auto_export_stems: bool = False
    auto_export_mpc: bool = False
    
    # Paths
    default_output_dir: Optional[str] = None
    default_soundfont: Optional[str] = None
    instrument_paths: list = field(default_factory=list)
    
    # Logging
    verbose: bool = False
    log_file: Optional[str] = None
    
    def __post_init__(self):
        """Set computed defaults after initialization."""
        if self.default_output_dir is None:
            # Use script directory / output as default
            self.default_output_dir = str(
                Path(__file__).parent.parent.parent / "output"
            )
    
    @classmethod
    def from_env(cls) -> "ServerConfig":
        """
        Create config from environment variables.
        
        Environment Variables:
            MMG_RECV_PORT: Receive port
            MMG_SEND_PORT: Send port
            MMG_HOST: Host address
            MMG_OUTPUT_DIR: Default output directory
            MMG_SOUNDFONT: Path to soundfont
            MMG_VERBOSE: Enable verbose mode (1/true/yes)
        """
        return cls(
            recv_port=int(os.getenv("MMG_RECV_PORT", 9000)),
            send_port=int(os.getenv("MMG_SEND_PORT", 9001)),
            host=os.getenv("MMG_HOST", "127.0.0.1"),
            default_output_dir=os.getenv("MMG_OUTPUT_DIR"),
            default_soundfont=os.getenv("MMG_SOUNDFONT"),
            verbose=os.getenv("MMG_VERBOSE", "").lower() in ("1", "true", "yes"),
        )


# OSC Message Addresses (Protocol Definition)
class OSCAddresses:
    """
    OSC address constants for message routing.
    
    Client → Server (JUCE → Python):
        /generate - Start music generation
        /cancel - Cancel current generation
        /analyze - Analyze existing file
        /instruments - Scan instrument directories
        /ping - Health check
        /shutdown - Graceful shutdown
        
    Server → Client (Python → JUCE):
        /progress - Generation progress update
        /complete - Generation complete with results
        /error - Error notification
        /instruments_loaded - Instrument scan results
        /pong - Health check response
        /status - Server status update
    """
    
    # Incoming (JUCE → Python)
    GENERATE = "/generate"
    CANCEL = "/cancel"
    ANALYZE = "/analyze"
    GET_INSTRUMENTS = "/instruments"
    PING = "/ping"
    SHUTDOWN = "/shutdown"
    
    # Outgoing (Python → JUCE)
    PROGRESS = "/progress"
    COMPLETE = "/complete"
    ERROR = "/error"
    INSTRUMENTS_LOADED = "/instruments_loaded"
    PONG = "/pong"
    STATUS = "/status"


# Generation Steps (for progress reporting)
class GenerationStep:
    """
    Enum-like class for generation step identifiers.
    Used for progress reporting with consistent step names.
    """
    INITIALIZING = "initializing"
    PARSING = "parsing"
    ARRANGING = "arranging"
    GENERATING_MIDI = "generating_midi"
    GENERATING_SAMPLES = "generating_samples"
    DISCOVERING_INSTRUMENTS = "discovering_instruments"
    RENDERING_AUDIO = "rendering_audio"
    EXPORTING_STEMS = "exporting_stems"
    EXPORTING_MPC = "exporting_mpc"
    COMPLETE = "complete"
    
    # Progress percentages for each step
    PROGRESS_MAP = {
        INITIALIZING: 0.0,
        PARSING: 0.05,
        ARRANGING: 0.15,
        GENERATING_MIDI: 0.35,
        GENERATING_SAMPLES: 0.45,
        DISCOVERING_INSTRUMENTS: 0.55,
        RENDERING_AUDIO: 0.75,
        EXPORTING_STEMS: 0.85,
        EXPORTING_MPC: 0.95,
        COMPLETE: 1.0,
    }


# Error Codes
class ErrorCode:
    """
    Error codes for structured error reporting.
    """
    # General errors (1xx)
    UNKNOWN = 100
    INVALID_MESSAGE = 101
    MISSING_PARAMETER = 102
    
    # Generation errors (2xx)
    GENERATION_FAILED = 200
    GENERATION_TIMEOUT = 201
    GENERATION_CANCELLED = 202
    INVALID_PROMPT = 203
    
    # Audio errors (3xx)
    AUDIO_RENDER_FAILED = 300
    SOUNDFONT_NOT_FOUND = 301
    FLUIDSYNTH_NOT_AVAILABLE = 302
    
    # Instrument errors (4xx)
    INSTRUMENTS_NOT_FOUND = 400
    INSTRUMENT_ANALYSIS_FAILED = 401
    
    # File errors (5xx)
    FILE_NOT_FOUND = 500
    FILE_WRITE_FAILED = 501
    OUTPUT_DIR_NOT_WRITABLE = 502
    
    # Server errors (9xx)
    SERVER_BUSY = 900
    WORKER_CRASHED = 901
    SHUTDOWN_IN_PROGRESS = 902


# Default configuration instance
DEFAULT_CONFIG = ServerConfig()
