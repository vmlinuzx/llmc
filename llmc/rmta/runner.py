import dataclasses
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Literal
import subprocess
import json
import time

@dataclass
class TestResult:
    name: str
    tool: str
    passed: bool
    duration_ms: int
    error: str | None = None

@dataclass
class RMTAReport:
    results: List[TestResult] = field(default_factory=list)
    mode: str = "unknown"

    @property
    def total(self) -> int:
        return len(self.results)

    @property
    def passed(self) -> int:
        return sum(1 for r in self.results if r.passed)

    @property
    def failed(self) -> int:
        return self.total - self.passed

    @property
    def pass_rate(self) -> float:
        return self.passed / self.total if self.total > 0 else 0.0

    def save(self, path: Path):
        with open(path, "w") as f:
            json.dump(dataclasses.asdict(self), f, indent=2)

    def print_summary(self):
        print(f"RMTA Test Report ({self.mode})")
        print("=" * 40)
        for result in self.results:
            status = "✅ PASSED" if result.passed else "❌ FAILED"
            print(f"[{status}] {result.name} ({result.duration_ms}ms)")
            if not result.passed and result.error:
                print(f"  └─ Error: {result.error}")
        print("-" * 40)
        print(f"Summary: {self.passed}/{self.total} passed ({self.pass_rate:.2%})")
        print("=" * 40)


@dataclass
class TestCase:
    path: Path

    @property
    def name(self) -> str:
        return self.path.stem

    @property
    def tool(self) -> str:
        # A simple way to guess the tool from the test name
        parts = self.name.split("_")
        if len(parts) > 1:
            return parts[1]
        return "unknown"

@dataclass
class RMTARunner:
    mode: Literal["quick", "standard", "ruthless"]
    tools: list[str] | None = None
    fail_fast: bool = False

    def run(self) -> RMTAReport:
        """Execute test suite based on mode."""
        test_cases = self._discover_tests()
        results = []

        for test in test_cases:
            start_time = time.monotonic()
            try:
                # Using pytest to run the tests
                result = subprocess.run(
                    ["python3", "-m", "pytest", str(test.path)],
                    capture_output=True,
                    text=True,
                    check=True
                )
                passed = True
                error = None
            except subprocess.CalledProcessError as e:
                passed = False
                error = e.stdout + e.stderr

            duration_ms = int((time.monotonic() - start_time) * 1000)

            results.append(TestResult(
                name=test.name,
                tool=test.tool,
                passed=passed,
                duration_ms=duration_ms,
                error=error
            ))

            if self.fail_fast and not passed:
                break

        return RMTAReport(results=results, mode=self.mode)

    def _discover_tests(self) -> list[TestCase]:
        """Discover tests based on mode and tool filter."""
        base_dir = Path(__file__).parent.parent.parent / "tests" / "ruthless"

        if self.mode == "quick":
            # There are no smoke tests, so I'll just grab a few tests to act as smoke tests.
            pattern = "test_mcgrep.py"
        elif self.mode == "standard":
            pattern = "test_*.py"
        else:  # ruthless
            pattern = "**/*.py"

        tests = list(base_dir.glob(pattern))

        if self.tools:
            tests = [t for t in tests if any(tool in t.name for tool in self.tools)]

        return [TestCase(path=t) for t in tests]
