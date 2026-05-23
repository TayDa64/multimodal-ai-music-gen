"""Bounded optional neural runtime seam for future audio rendering.

This module is intentionally conservative: it provides capability probing and an
opt-in execution seam, but it does not claim that a production neural renderer
ships in the repo today.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from importlib.util import find_spec
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Sequence


@dataclass(frozen=True)
class NeuralBackendStatus:
    """Truthful capability snapshot for the optional neural runtime."""

    backend_name: str
    enabled: bool
    available: bool
    missing_dependencies: Sequence[str] = field(default_factory=tuple)
    model_path: Optional[str] = None
    model_exists: bool = False
    can_render: bool = False
    skip_reason: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "backend_name": self.backend_name,
            "enabled": bool(self.enabled),
            "available": bool(self.available),
            "missing_dependencies": list(self.missing_dependencies),
            "model_path": self.model_path,
            "model_exists": bool(self.model_exists),
            "can_render": bool(self.can_render),
            "skip_reason": self.skip_reason,
            "details": dict(self.details),
        }


@dataclass
class NeuralRenderResult:
    """Result of a neural render attempt."""

    success: bool
    attempted: bool = False
    backend_name: str = "bounded_neural_runtime"
    output_path: Optional[str] = None
    skip_reason: Optional[str] = None
    error_message: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": bool(self.success),
            "attempted": bool(self.attempted),
            "backend_name": self.backend_name,
            "output_path": self.output_path,
            "skip_reason": self.skip_reason,
            "error_message": self.error_message,
            "details": dict(self.details),
        }


class OptionalNeuralRuntime:
    """Optional neural backend seam.

    The default implementation only reports capabilities honestly and can host
    an injected render callback for controlled opt-in execution.
    """

    def __init__(
        self,
        *,
        enabled: bool = False,
        model_path: Optional[str] = None,
        required_dependencies: Sequence[str] = ("torch",),
        backend_name: str = "bounded_neural_runtime",
        render_callback: Optional[Callable[..., Any]] = None,
    ) -> None:
        self.enabled = bool(enabled)
        self.model_path = model_path
        self.required_dependencies = tuple(dep for dep in required_dependencies if dep)
        self.backend_name = backend_name
        self._render_callback = render_callback

    def probe(self) -> NeuralBackendStatus:
        missing_dependencies = tuple(
            dependency for dependency in self.required_dependencies if find_spec(dependency) is None
        )
        normalized_model_path = str(Path(self.model_path).expanduser()) if self.model_path else None
        model_exists = bool(normalized_model_path and Path(normalized_model_path).exists())
        available = len(missing_dependencies) == 0

        skip_reason: Optional[str]
        if not self.enabled:
            skip_reason = "disabled"
        elif not normalized_model_path:
            skip_reason = "missing_model_path"
        elif not model_exists:
            skip_reason = "model_path_not_found"
        elif missing_dependencies:
            skip_reason = "missing_dependencies"
        elif self._render_callback is None:
            skip_reason = "no_runtime_impl"
        else:
            skip_reason = None

        return NeuralBackendStatus(
            backend_name=self.backend_name,
            enabled=self.enabled,
            available=available,
            missing_dependencies=missing_dependencies,
            model_path=normalized_model_path,
            model_exists=model_exists,
            can_render=skip_reason is None,
            skip_reason=skip_reason,
            details={"required_dependencies": list(self.required_dependencies)},
        )

    def render_midi_to_audio(
        self,
        midi_path: str,
        output_path: str,
        *,
        parsed: Any = None,
        sample_rate: int = 44100,
    ) -> NeuralRenderResult:
        status = self.probe()
        if not status.can_render:
            return NeuralRenderResult(
                success=False,
                attempted=False,
                backend_name=self.backend_name,
                output_path=output_path,
                skip_reason=status.skip_reason,
                details=status.to_dict(),
            )

        try:
            callback_result = self._render_callback(
                midi_path,
                output_path,
                parsed=parsed,
                sample_rate=sample_rate,
            )
        except Exception as exc:
            return NeuralRenderResult(
                success=False,
                attempted=True,
                backend_name=self.backend_name,
                output_path=output_path,
                skip_reason="render_exception",
                error_message=f"{type(exc).__name__}: {exc}",
                details=status.to_dict(),
            )

        if isinstance(callback_result, NeuralRenderResult):
            result = callback_result
        elif isinstance(callback_result, bool):
            result = NeuralRenderResult(
                success=callback_result,
                attempted=True,
                backend_name=self.backend_name,
                output_path=output_path,
                skip_reason=None if callback_result else "render_failed",
                details=status.to_dict(),
            )
        elif isinstance(callback_result, dict):
            result = NeuralRenderResult(
                success=bool(callback_result.get("success")),
                attempted=bool(callback_result.get("attempted", True)),
                backend_name=str(callback_result.get("backend_name", self.backend_name)),
                output_path=callback_result.get("output_path", output_path),
                skip_reason=callback_result.get("skip_reason"),
                error_message=callback_result.get("error_message"),
                details={**status.to_dict(), **dict(callback_result.get("details") or {})},
            )
        else:
            result = NeuralRenderResult(
                success=False,
                attempted=True,
                backend_name=self.backend_name,
                output_path=output_path,
                skip_reason="invalid_result_type",
                error_message=f"Unsupported callback result type: {type(callback_result).__name__}",
                details=status.to_dict(),
            )

        result.details = {**status.to_dict(), **dict(result.details or {})}
        return result