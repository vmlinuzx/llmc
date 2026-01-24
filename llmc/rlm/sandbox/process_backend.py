"""Process-based sandbox for RLM code execution.

FIXES V1.1.0 ISSUE: Thread-based timeout is unenforceable.
Python threads cannot be killed. A `while True: pass` would hang forever.

Solution: Use multiprocessing.Process which CAN be terminated.
"""

from __future__ import annotations
import multiprocessing as mp
from multiprocessing import Queue
import time
from typing import Any, Callable
from dataclasses import dataclass

from llmc.rlm.sandbox.interface import CodeExecutionEnvironment, ExecutionResult


def _sandbox_worker(
    code: str,
    namespace: dict,
    result_queue: Queue,
    max_output_chars: int,
):
    """Worker function that runs in separate process."""
    import sys
    import io
    import ast
    import traceback
    from contextlib import redirect_stdout, redirect_stderr
    
    stdout_capture = io.StringIO()
    stderr_capture = io.StringIO()
    final_answer = None
    
    # Inject FINAL handler
    def final_handler(answer):
        nonlocal final_answer
        final_answer = str(answer)
    
    namespace["FINAL"] = final_handler
    namespace["FINAL_VAR"] = None
    
    try:
        with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
            tree = ast.parse(code, mode='exec')
            exec(compile(tree, '<rlm>', 'exec'), namespace)
        
        # Check FINAL_VAR
        if namespace.get("FINAL_VAR") is not None:
            final_answer = str(namespace["FINAL_VAR"])
        
        result_queue.put({
            "success": True,
            "stdout": stdout_capture.getvalue()[:max_output_chars],
            "stderr": stderr_capture.getvalue()[:max_output_chars],
            "final_answer": final_answer,
            "error": None,
            "namespace_updates": _extract_safe_updates(namespace),
        })
        
    except Exception as e:
        result_queue.put({
            "success": False,
            "stdout": stdout_capture.getvalue()[:max_output_chars],
            "stderr": traceback.format_exc()[:max_output_chars],
            "final_answer": None,
            "error": f"{type(e).__name__}: {e}",
            "namespace_updates": {},
        })


def _extract_safe_updates(namespace: dict) -> dict:
    """Extract JSON-serializable namespace updates."""
    import json
    safe = {}
    for k, v in namespace.items():
        if k.startswith("_") or callable(v):
            continue
        try:
            json.dumps(v)  # Test serializability
            safe[k] = v
        except (TypeError, ValueError):
            pass
    return safe


class ProcessSandboxBackend(CodeExecutionEnvironment):
    """Process-based sandbox that can actually be killed on timeout.
    
    Unlike threading.Thread (V1.1.0), multiprocessing.Process can be
    terminated with process.terminate() or process.kill().
    
    Trade-offs:
    - Pro: Actually stops runaway code
    - Pro: Memory isolation (process has own heap)
    - Con: Higher overhead (~50ms per exec vs ~1ms for threads)
    - Con: Callbacks require IPC (we use mp.Queue)
    
    For Phase 1, the safety benefit outweighs the overhead cost.
    """
    
    BLOCKED_BUILTINS = {
        'open', 'exec', 'eval', 'compile', '__import__',
        'input', 'breakpoint', 'exit', 'quit',
    }
    
    ALLOWED_MODULES = {
        'json', 're', 'math', 'collections', 'itertools',
        'functools', 'operator', 'string', 'textwrap',
        'datetime', 'copy', 'typing', 'dataclasses',
    }
    
    def __init__(
        self,
        max_output_chars: int = 10_000,
        timeout_seconds: int = 30,
    ):
        self.max_output_chars = max_output_chars
        self.timeout_seconds = timeout_seconds
        self._namespace: dict[str, Any] = {}
        self._callbacks: dict[str, Callable] = {}
        self._callback_queue: Queue | None = None
        self._result_queue: Queue | None = None
    
    def start(self) -> None:
        """Initialize queues and base namespace."""
        self._callback_queue = mp.Queue()
        self._result_queue = mp.Queue()
        self._namespace = self._build_safe_namespace()
    
    def stop(self) -> None:
        """Clean up."""
        self._namespace.clear()
        self._callbacks.clear()
    
    def _build_safe_namespace(self) -> dict:
        """Build namespace with restricted builtins."""
        import builtins
        
        safe_builtins = {
            k: v for k, v in vars(builtins).items()
            if k not in self.BLOCKED_BUILTINS
        }
        safe_builtins['__import__'] = self._make_controlled_import()
        
        return {
            "__builtins__": safe_builtins,
            # Callbacks will be injected as stubs that use IPC
        }
    
    def _make_controlled_import(self):
        """Create import function with whitelist."""
        allowed = self.ALLOWED_MODULES
        
        def controlled_import(name, *args, **kwargs):
            root = name.split('.')[0]
            if root not in allowed:
                raise ImportError(f"Import '{name}' blocked. Allowed: {sorted(allowed)}")
            import importlib
            return importlib.import_module(name)
        
        return controlled_import
    
    def execute(self, code: str, timeout: int | None = None) -> ExecutionResult:
        """Execute code in subprocess with hard timeout."""
        timeout = timeout or self.timeout_seconds
        start = time.perf_counter()
        
        # Prepare namespace with callback stubs
        namespace = {**self._namespace}
        for name, _ in self._callbacks.items():
            # Callbacks can't cross process boundary directly
            # For Phase 1, we inject simplified versions or block them
            namespace[name] = self._make_callback_stub(name)
        
        # Start worker process
        result_queue = mp.Queue()
        process = mp.Process(
            target=_sandbox_worker,
            args=(code, namespace, result_queue, self.max_output_chars),
        )
        process.start()
        process.join(timeout=timeout)
        
        # Check if timed out
        if process.is_alive():
            process.terminate()  # SIGTERM
            process.join(timeout=1)
            if process.is_alive():
                process.kill()  # SIGKILL
                process.join()
            
            return ExecutionResult(
                success=False,
                stdout="",
                stderr="",
                error=f"Execution killed after {timeout}s timeout",
                execution_time_ms=(time.perf_counter() - start) * 1000,
            )
        
        # Get result
        try:
            result_data = result_queue.get_nowait()
        except:
            return ExecutionResult(
                success=False,
                stdout="",
                stderr="",
                error="Worker crashed without returning result",
                execution_time_ms=(time.perf_counter() - start) * 1000,
            )
        
        # Update namespace with safe values from worker
        self._namespace.update(result_data.get("namespace_updates", {}))
        
        return ExecutionResult(
            success=result_data["success"],
            stdout=result_data["stdout"],
            stderr=result_data["stderr"],
            error=result_data["error"],
            final_answer=result_data["final_answer"],
            execution_time_ms=(time.perf_counter() - start) * 1000,
        )
    
    def _make_callback_stub(self, name: str):
        """Create stub for callback (IPC not implemented in Phase 1).
        
        For Phase 1, callbacks like llm_query() are handled OUTSIDE
        the sandbox by intercepting code patterns. Full IPC callbacks
        are a Phase 1.2 feature.
        """
        def stub(*args, **kwargs):
            raise RuntimeError(
                f"Callback '{name}' cannot be called directly in process sandbox. "
                f"Use the pattern: result = {name}(...) and the orchestrator will handle it."
            )
        return stub
    
    def inject_variable(self, name: str, value: Any) -> None:
        """Inject variable (must be picklable for process boundary)."""
        import pickle
        try:
            pickle.dumps(value)  # Test picklability
            self._namespace[name] = value
        except Exception as e:
            raise ValueError(f"Cannot inject '{name}': not picklable ({e})")
    
    def register_callback(self, name: str, func: Callable) -> None:
        """Register callback (handled via orchestrator interception in Phase 1)."""
        self._callbacks[name] = func
    
    def get_variable(self, name: str) -> Any:
        return self._namespace.get(name)
