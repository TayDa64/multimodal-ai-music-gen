"""
Background Worker Module

Handles non-blocking execution of music generation tasks.
Uses ThreadPoolExecutor for concurrent task management with
proper cancellation and progress reporting.
"""

from __future__ import annotations

import threading
import traceback
import uuid
import json
from concurrent.futures import ThreadPoolExecutor, Future
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from .config import GenerationStep, ErrorCode, SCHEMA_VERSION


class TaskStatus(Enum):
    """Status of a generation task."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class GenerationRequest:
    """
    Encapsulates all parameters for a generation request.
    
    Attributes:
        request_id: Unique identifier for request/response correlation
        schema_version: Protocol version for compatibility checking
        prompt: Natural language music description
        genre: Genre ID override (e.g., "g_funk", "trap", "lofi")
        bpm: BPM override (0 = auto-detect from prompt)
        key: Key override (empty = auto-detect)
        output_dir: Directory for generated files
        instruments: List of instrument library paths
        soundfont: Path to soundfont file
        render_audio: Whether to render WAV
        export_stems: Whether to export stems
        export_mpc: Whether to export MPC project
        reference_url: Optional reference track URL
        template: Optional template file path
        verbose: Enable verbose output
        num_takes: Number of takes to generate per track (1 = no takes)
        take_variation: Variation axis for takes ("rhythm", "pitch", "timing", etc.)
    """
    prompt: str
    request_id: str = ""  # UUID for request/response correlation
    schema_version: int = 1  # Protocol version
    genre: str = ""  # Genre ID from UI (e.g., "g_funk", "trap_soul")
    bpm: int = 0
    key: str = ""
    mode: str = ""  # "major" or "minor"
    duration_bars: int = 8
    output_dir: str = ""
    instruments: List[str] = field(default_factory=list)
    soundfont: str = ""
    render_audio: bool = True
    export_stems: bool = False
    export_mpc: bool = False
    reference_url: str = ""
    template: str = ""
    verbose: bool = False
    # Take generation
    num_takes: int = 1          # Number of takes per track (1 = no variations)
    take_variation: str = ""    # Variation axis: "rhythm", "pitch", "timing", "combined"
    options: Dict[str, Any] = field(default_factory=dict)  # Additional options
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging/serialization."""
        return {
            "request_id": self.request_id,
            "schema_version": self.schema_version,
            "prompt": self.prompt,
            "genre": self.genre,
            "bpm": self.bpm,
            "key": self.key,
            "mode": self.mode,
            "duration_bars": self.duration_bars,
            "output_dir": self.output_dir,
            "instruments": self.instruments,
            "render_audio": self.render_audio,
            "export_stems": self.export_stems,
            "export_mpc": self.export_mpc,
            "num_takes": self.num_takes,
            "take_variation": self.take_variation,
        }


@dataclass
class GenerationResult:
    """
    Result of a completed generation task.
    
    Attributes:
        task_id: Unique identifier for the task (internal)
        request_id: Unique identifier for request/response correlation (from client)
        success: Whether generation succeeded
        midi_path: Path to generated MIDI file
        audio_path: Path to rendered audio (if applicable)
        stems_path: Path to stems directory (if applicable)
        mpc_path: Path to MPC project (if applicable)
        metadata: Generation metadata (bpm, key, genre, etc.)
        error_code: Error code if failed
        error_message: Error description if failed
        duration: Time taken for generation (seconds)
        takes: List of generated take lanes (for multi-take generation)
    """
    task_id: str
    success: bool
    request_id: str = ""  # For request/response correlation
    midi_path: str = ""
    audio_path: str = ""
    stems_path: str = ""
    mpc_path: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    error_code: int = 0
    error_message: str = ""
    duration: float = 0.0
    samples_generated: int = 0
    instruments_used: List[Dict[str, Any]] = field(default_factory=list)
    takes: List[Dict[str, Any]] = field(default_factory=list)  # Take lanes from TakeGenerator
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for OSC transmission."""
        return {
            "task_id": self.task_id,
            "request_id": self.request_id,
            "success": self.success,
            "midi_path": self.midi_path,
            "audio_path": self.audio_path,
            "stems_path": self.stems_path,
            "mpc_path": self.mpc_path,
            "metadata": self.metadata,
            "error_code": self.error_code,
            "error_message": self.error_message,
            "duration": self.duration,
            "samples_generated": self.samples_generated,
            "instruments_used": self.instruments_used,
            "takes": self.takes,
        }


# Type alias for progress callback
ProgressCallback = Callable[[str, float, str], None]


def build_run_generation_kwargs(
    request: GenerationRequest,
    output_dir: str,
    progress_callback: ProgressCallback,
) -> Dict[str, Any]:
    """Build kwargs for main.run_generation from a GenerationRequest.

    Keeps server/protocol option mapping isolated and unit-testable.
    """

    options = request.options if isinstance(request.options, dict) else {}

    def _opt(key: str, default: Any = None) -> Any:
        return options.get(key, default)

    def _as_int(v: Any) -> Optional[int]:
        try:
            if v is None:
                return None
            return int(v)
        except Exception:
            return None

    def _as_float(v: Any) -> Optional[float]:
        try:
            if v is None:
                return None
            return float(v)
        except Exception:
            return None

    def _as_str(v: Any) -> Optional[str]:
        try:
            if v is None:
                return None
            return str(v)
        except Exception:
            return None

    seed_opt = _as_int(_opt("seed"))
    preset_opt = _as_str(_opt("preset"))
    style_preset_opt = _as_str(_opt("style_preset"))
    production_preset_opt = _as_str(_opt("production_preset"))
    tension_arc_shape_opt = _as_str(_opt("tension_arc_shape"))
    tension_intensity_opt = _as_float(_opt("tension_intensity"))
    motif_mode_opt = _as_str(_opt("motif_mode"))
    num_motifs_opt = _as_int(_opt("num_motifs"))

    return {
        "prompt": request.prompt,
        "output_dir": output_dir,
        "genre_override": request.genre if request.genre else None,
        "bpm_override": request.bpm if request.bpm and request.bpm > 0 else None,
        "key_override": request.key if request.key else None,
        "reference_url": request.reference_url if request.reference_url else None,
        "export_mpc": request.export_mpc,
        "export_stems": request.export_stems,
        "soundfont_path": request.soundfont if request.soundfont else None,
        "template_path": request.template if request.template else None,
        "instruments_paths": request.instruments if request.instruments else None,
        "verbose": request.verbose,
        "progress_callback": progress_callback,
        "seed": seed_opt,
        "takes": request.num_takes if request.num_takes and request.num_takes > 1 else 0,
        "preset": preset_opt,
        "style_preset": style_preset_opt,
        "production_preset": production_preset_opt,
        "duration_bars": request.duration_bars,
        "tension_arc_shape": tension_arc_shape_opt,
        "tension_intensity": tension_intensity_opt,
        "motif_mode": motif_mode_opt,
        "num_motifs": num_motifs_opt,
    }


@dataclass
class Task:
    """
    Internal representation of a queued/running task.
    """
    id: str
    request: GenerationRequest
    request_id: str = ""  # Client-provided request_id for correlation
    status: TaskStatus = TaskStatus.PENDING
    future: Optional[Future] = None
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[GenerationResult] = None
    cancel_requested: bool = False


class GenerationWorker:
    """
    Background worker for non-blocking music generation.
    
    Manages a thread pool for executing generation tasks,
    with support for cancellation, progress reporting, and
    task queuing.
    
    Example:
        ```python
        def on_progress(step, percent, message):
            print(f"{step}: {percent*100:.0f}% - {message}")
        
        def on_complete(result):
            print(f"Done! MIDI at: {result.midi_path}")
        
        worker = GenerationWorker(
            progress_callback=on_progress,
            completion_callback=on_complete,
        )
        
        request = GenerationRequest(prompt="G-Funk beat")
        task_id = worker.submit(request)
        
        # Later: cancel if needed
        worker.cancel(task_id)
        ```
    """
    
    def __init__(
        self,
        max_workers: int = 1,
        progress_callback: Optional[ProgressCallback] = None,
        completion_callback: Optional[Callable[[GenerationResult], None]] = None,
        error_callback: Optional[Callable[[int, str], None]] = None,
    ):
        """
        Initialize the generation worker.
        
        Args:
            max_workers: Maximum concurrent generations (default 1)
            progress_callback: Called with (step, percent, message)
            completion_callback: Called with GenerationResult on completion
            error_callback: Called with (error_code, message) on error
        """
        self.max_workers = max_workers
        self.progress_callback = progress_callback
        self.completion_callback = completion_callback
        self.error_callback = error_callback
        
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="MusicGen-"
        )
        self._tasks: Dict[str, Task] = {}
        self._lock = threading.Lock()
        self._current_task_id: Optional[str] = None
        self._shutdown_requested = False
    
    def submit(self, request: GenerationRequest) -> str:
        """
        Submit a generation request for background execution.
        
        Args:
            request: GenerationRequest with all parameters
            
        Returns:
            task_id: Unique identifier for tracking the task
            
        Raises:
            RuntimeError: If worker is shutting down
        """
        if self._shutdown_requested:
            raise RuntimeError("Worker is shutting down")
        
        task_id = str(uuid.uuid4())[:8]
        
        task = Task(
            id=task_id,
            request=request,
            request_id=request.request_id,  # Copy client's request_id for correlation
        )
        
        with self._lock:
            self._tasks[task_id] = task
        
        # Submit to thread pool
        future = self._executor.submit(self._execute_task, task)
        task.future = future
        
        return task_id
    
    def cancel(self, task_id: Optional[str] = None) -> bool:
        """
        Request cancellation of a task.
        
        Args:
            task_id: Task to cancel, or None for current task
            
        Returns:
            True if cancellation was requested, False if task not found
        """
        target_id = task_id or self._current_task_id
        
        if not target_id:
            return False
        
        with self._lock:
            task = self._tasks.get(target_id)
            if not task:
                return False
            
            task.cancel_requested = True
            
            # Try to cancel if not started
            if task.future and task.status == TaskStatus.PENDING:
                cancelled = task.future.cancel()
                if cancelled:
                    task.status = TaskStatus.CANCELLED
                    return True
        
        return True
    
    def get_status(self, task_id: str) -> Optional[TaskStatus]:
        """Get the status of a task."""
        with self._lock:
            task = self._tasks.get(task_id)
            return task.status if task else None
    
    def is_busy(self) -> bool:
        """Check if worker is currently processing a task."""
        return self._current_task_id is not None
    
    def get_current_task_id(self) -> Optional[str]:
        """Get the ID of the currently running task."""
        return self._current_task_id
    
    def shutdown(self, wait: bool = True, timeout: float = 30.0):
        """
        Shutdown the worker gracefully.
        
        Args:
            wait: Wait for pending tasks to complete
            timeout: Maximum time to wait (seconds)
        """
        self._shutdown_requested = True
        
        # Cancel all pending tasks
        with self._lock:
            for task in self._tasks.values():
                if task.status in (TaskStatus.PENDING, TaskStatus.RUNNING):
                    task.cancel_requested = True
        
        self._executor.shutdown(wait=wait, cancel_futures=not wait)
    
    def _execute_task(self, task: Task) -> GenerationResult:
        """
        Execute a generation task (runs in thread pool).
        
        This is the main execution method that:
        1. Sets up progress reporting
        2. Calls the main generation function
        3. Handles errors and cancellation
        4. Reports results
        """
        import time
        start_time = time.time()
        
        task.status = TaskStatus.RUNNING
        task.started_at = datetime.now()
        self._current_task_id = task.id
        
        try:
            # Report initialization
            self._report_progress(
                GenerationStep.INITIALIZING,
                GenerationStep.PROGRESS_MAP[GenerationStep.INITIALIZING],
                "Starting generation..."
            )
            
            # Check for early cancellation
            if task.cancel_requested:
                return self._create_cancelled_result(task.id, task.request_id, time.time() - start_time)
            
            # Import here to avoid circular imports
            from main import run_generation
            
            # Create progress callback that checks for cancellation
            def progress_with_cancel_check(step: str, percent: float, message: str):
                if task.cancel_requested:
                    raise InterruptedError("Generation cancelled by user")
                self._report_progress(step, percent, message)
            
            # Prepare arguments
            output_dir = task.request.output_dir or str(
                Path(__file__).parent.parent.parent / "output"
            )

            kwargs = build_run_generation_kwargs(
                request=task.request,
                output_dir=output_dir,
                progress_callback=progress_with_cancel_check,
            )

            # Execute generation
            results = run_generation(**kwargs)
            
            # Build result
            duration = time.time() - start_time
            
            # Build takes list from the results dictionary for TakeLanePanel
            # Format: {track_name: [{take_id, midi_track_name, variation_type, seed, ...}, ...]}
            takes_data = []
            takes_dict = results.get("takes", {})
            if isinstance(takes_dict, dict):
                for track_name, take_list in takes_dict.items():
                    for take_info in take_list:
                        if isinstance(take_info, dict):
                            # Rich format with full take info
                            takes_data.append({
                                "track": track_name,
                                **take_info  # Include all take metadata
                            })
                        else:
                            # Legacy format (just track name string)
                            takes_data.append({
                                "take_id": "1",
                                "track": track_name,
                                "midi_track_name": str(take_info),
                                "variation_type": "timing",
                                "seed": 0,
                            })
            
            result = GenerationResult(
                task_id=task.id,
                request_id=task.request_id,  # Include client's request_id for correlation
                success=True,
                midi_path=results.get("midi", ""),
                audio_path=results.get("audio", ""),
                stems_path=results.get("stems", ""),
                mpc_path=results.get("mpc", ""),
                metadata={
                    "bpm": results.get("bpm"),
                    "key": results.get("key"),
                    "genre": results.get("genre"),
                    "sections": results.get("sections", []),
                },
                samples_generated=len(results.get("samples", [])),
                instruments_used=results.get("instruments_used", []),
                duration=duration,
                takes=takes_data,
            )
            
            task.status = TaskStatus.COMPLETED
            task.result = result
            
            # Report completion
            self._report_progress(
                GenerationStep.COMPLETE,
                1.0,
                f"Generation complete in {duration:.1f}s"
            )
            
            if self.completion_callback:
                self.completion_callback(result)
            
            return result
            
        except InterruptedError:
            # Cancelled
            duration = time.time() - start_time
            result = self._create_cancelled_result(task.id, task.request_id, duration)
            task.status = TaskStatus.CANCELLED
            task.result = result
            
            if self.error_callback:
                self.error_callback(
                    ErrorCode.GENERATION_CANCELLED,
                    "Generation cancelled by user"
                )
            
            return result
            
        except Exception as e:
            # Error
            duration = time.time() - start_time
            error_msg = str(e)
            
            result = GenerationResult(
                task_id=task.id,
                request_id=task.request_id,  # Include client's request_id for correlation
                success=False,
                error_code=ErrorCode.GENERATION_FAILED,
                error_message=error_msg,
                duration=duration,
            )
            
            task.status = TaskStatus.FAILED
            task.result = result
            
            if self.error_callback:
                self.error_callback(ErrorCode.GENERATION_FAILED, error_msg)
            
            # Log full traceback
            traceback.print_exc()
            
            return result
            
        finally:
            task.completed_at = datetime.now()
            self._current_task_id = None
    
    def _report_progress(self, step: str, percent: float, message: str):
        """Report progress through callback if available."""
        if self.progress_callback:
            try:
                self.progress_callback(step, percent, message)
            except Exception:
                pass  # Don't let callback errors affect generation
    
    def _create_cancelled_result(self, task_id: str, request_id: str, duration: float) -> GenerationResult:
        """Create a result for a cancelled task."""
        return GenerationResult(
            task_id=task_id,
            request_id=request_id,  # Include client's request_id for correlation
            success=False,
            error_code=ErrorCode.GENERATION_CANCELLED,
            error_message="Generation cancelled by user",
            duration=duration,
        )


class InstrumentScanWorker:
    """
    Lightweight worker for scanning instrument directories.
    
    Separated from GenerationWorker to allow instrument scanning
    while a generation is in progress.
    """
    
    def __init__(
        self,
        completion_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
        error_callback: Optional[Callable[[int, str], None]] = None,
        progress_callback: Optional[Callable[[str, float, str], None]] = None,
    ):
        self.completion_callback = completion_callback
        self.error_callback = error_callback
        self.progress_callback = progress_callback
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="InstrumentScan-")
    
    def scan(self, paths: List[str], cache_dir: Optional[str] = None) -> str:
        """
        Start scanning instrument directories.
        
        Args:
            paths: List of directories to scan
            cache_dir: Directory for cache files
            
        Returns:
            scan_id: Unique identifier for the scan operation
        """
        scan_id = str(uuid.uuid4())[:8]
        self._executor.submit(self._execute_scan, scan_id, paths, cache_dir)
        return scan_id
    
    def _execute_scan(self, scan_id: str, paths: List[str], cache_dir: Optional[str]):
        """Execute instrument scan in background thread."""
        try:
            from multimodal_gen import load_multiple_libraries

            def _progress(p: float, msg: str):
                if self.progress_callback:
                    try:
                        self.progress_callback("discovering_instruments", float(p), msg)
                    except Exception:
                        pass

            if self.progress_callback:
                _progress(0.0, "Starting instrument scan")
            
            library = load_multiple_libraries(
                paths,
                cache_dir=cache_dir,
                auto_load_audio=False,
                verbose=True,
                progress_callback=_progress,
            )

            if self.progress_callback:
                _progress(1.0, f"Scan complete: {len(library.instruments)} instruments")
            
            # Serialize instruments by category
            instruments_by_category = {}
            for category, instruments in library.by_category.items():
                if not instruments:
                    continue
                    
                cat_name = category.value if hasattr(category, 'value') else str(category)
                instruments_list = []
                
                for inst in instruments:
                    inst_data = {
                        "id": str(uuid.uuid4()),
                        "name": inst.name,
                        "filename": Path(inst.path).name,
                        "path": inst.path,
                        "absolute_path": inst.path,
                        "category": cat_name,
                        "subcategory": "", 
                        "tags": [],
                        "key": "",
                        "bpm": 0,
                        "duration_ms": 0,
                        "file_size_bytes": 0,
                        "favorite": False,
                        "play_count": 0
                    }
                    
                    if inst.profile:
                        inst_data.update({
                            "duration_ms": inst.profile.duration_sec * 1000.0,
                            "bpm": 0, 
                            "key": "", 
                        })
                        
                        if inst.profile.midi_note > 0:
                             # Convert midi note to note name if needed
                             pass
                             
                    instruments_list.append(inst_data)
                
                instruments_by_category[cat_name] = instruments_list

            full_result: Dict[str, Any] = {
                "schema_version": SCHEMA_VERSION,
                "scan_id": scan_id,
                "success": True,
                "count": len(library.instruments),
                "categories": library.list_categories(),
                "sources": library.get_source_summary(),
                "instruments": instruments_by_category,
            }

            # OSC messages have practical size limits; send a small summary payload and
            # write the full manifest to disk for the client to load.
            manifest_path = ""
            try:
                if cache_dir:
                    cache_dir_path = Path(cache_dir)
                    cache_dir_path.mkdir(parents=True, exist_ok=True)
                    manifest_file = cache_dir_path / f"instrument_scan_{scan_id}.json"
                    manifest_file.write_text(
                        json.dumps(full_result, ensure_ascii=False),
                        encoding="utf-8",
                    )
                    manifest_path = str(manifest_file)
            except Exception:
                manifest_path = ""

            summary: Dict[str, Any] = {
                "schema_version": SCHEMA_VERSION,
                "scan_id": scan_id,
                "success": True,
                "count": len(library.instruments),
                "categories": library.list_categories(),
                "sources": library.get_source_summary(),
            }
            if manifest_path:
                summary["manifest_path"] = manifest_path

            if self.completion_callback:
                self.completion_callback(summary)
                
        except Exception as e:
            if self.error_callback:
                self.error_callback(
                    ErrorCode.INSTRUMENT_ANALYSIS_FAILED,
                    str(e)
                )
    
    def shutdown(self):
        """Shutdown the scan worker."""
        self._executor.shutdown(wait=False)
