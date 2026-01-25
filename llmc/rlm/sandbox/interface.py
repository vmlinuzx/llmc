"""Sandbox interface - ABC for code execution environments."""

from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Callable


@dataclass
class ExecutionResult:
    """Result from code execution."""
    success: bool
    stdout: str
    stderr: str
    error: str | None = None
    final_answer: str | None = None
    execution_time_ms: float = 0.0


class CodeExecutionEnvironment(ABC):
    """Abstract base class for code execution sandboxes."""
    
    @abstractmethod
    def start(self) -> None:
        """Initialize the environment."""
        pass
    
    @abstractmethod
    def stop(self) -> None:
        """Clean up resources."""
        pass
    
    @abstractmethod
    def execute(self, code: str, timeout: int | None = None) -> ExecutionResult:
        """Execute Python code and return result."""
        pass
    
    @abstractmethod
    def inject_variable(self, name: str, value: Any) -> None:
        """Inject a variable into the execution namespace."""
        pass
    
    @abstractmethod
    def register_callback(self, name: str, func: Callable) -> None:
        """Register a callback function."""
        pass
    
    @abstractmethod
    def get_variable(self, name: str) -> Any:
        """Get a variable from the execution namespace."""
        pass


def create_sandbox(
    backend: str = "process",
    max_output_chars: int = 10_000,
    timeout_seconds: int = 30,
    blocked_builtins: frozenset[str] | None = None,
    allowed_modules: frozenset[str] | None = None,
    security_mode: str = "permissive",
) -> CodeExecutionEnvironment:
    """Factory for creating sandboxes."""
    if backend == "process":
        from .process_backend import ProcessSandboxBackend
        return ProcessSandboxBackend(
            max_output_chars=max_output_chars,
            timeout_seconds=timeout_seconds,
            blocked_builtins=blocked_builtins,
            allowed_modules=allowed_modules,
            security_mode=security_mode,
        )
    elif backend == "restricted":
        # TODO: Implement RestrictedPython backend (Tier -1)
        raise NotImplementedError("RestrictedPython backend not yet implemented")
    else:
        raise ValueError(f"Unknown sandbox backend: {backend}")
