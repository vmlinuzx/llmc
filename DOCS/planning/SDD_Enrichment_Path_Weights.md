# SDD: Enrichment Path Weights & Collision Resolution (Roadmap 1.2.1)

**Author:** Otto (Claude Opus 4.5)  
**Date:** 2025-12-02  
**Status:** Draft  
**Parent SDD:** SDD_Enrichment_Code_First.md  
**Effort:** 3-4 hours  
**Difficulty:** 🟡 Medium

---

## Problem

The code-first enrichment SDD (1.2) introduces a binary CODE/NON_CODE classification that's too coarse:

1. **Test code detection is unreliable** - Not everyone puts tests in `/tests/`. Tests can be:
   - `src/mymodule/test_thing.py` (colocated)
   - `__tests__/Component.test.tsx` (Jest convention)
   - `spec/models/user_spec.rb` (RSpec convention)
   - `foo_test.go` (Go convention)

2. **No granular priority control** - A docstring-heavy utility module and a critical router have the same priority just because both are `.py` files.

3. **Binary classification causes edge cases** - Is `docker-compose.yml` code or config? Is `Makefile` code? Is `setup.py` infra or code?

---

## Solution: Configurable Path Weights

Replace binary CODE/NON_CODE with a **1-10 weight scale** where lower = higher priority.

### Weight Scale

| Weight | Meaning | Example Paths |
|--------|---------|---------------|
| 1 | Critical code - enrich immediately | `src/core/**`, `lib/**`, `app/**` |
| 2-3 | Important code | `pkg/**`, `internal/**`, `cmd/**` |
| 4-5 | Supporting code | `utils/**`, `helpers/**` |
| 6-7 | Test code, examples | `**/tests/**`, `examples/**` |
| 8-9 | Docs and config | `docs/**`, `.github/**` |
| 10 | Vendor/generated - back of the line | `vendor/**`, `node_modules/**` |

### Priority Formula

```
final_priority = base_priority * (11 - path_weight) / 10
```

Where:
- `base_priority` comes from content type (CODE=100, NON_CODE=10) + modifiers (new file, recently changed, etc.)
- `path_weight` is 1-10 from config

**Examples:**

| File | Base | Weight | Final |
|------|------|--------|-------|
| `src/core/router.py` | 100 | 1 | 100 |
| `src/tests/test_router.py` | 100 | 6 | 50 |
| `docs/example.py` | 100 | 8 | 30 |
| `docs/README.md` | 10 | 8 | 3 |
| `vendor/lib/thing.py` | 100 | 10 | 10 |

This ensures:
- Code in core paths beats everything
- Code in test paths beats docs, but loses to core code
- Vendor code (even if it's code) goes to the back

---

## Configuration

### `llmc.toml` Section

```toml
[enrichment.path_weights]
# Weight 1-10: lower = higher priority
# Patterns are globs matched against repo-relative paths
# First matching pattern wins... just kidding, HIGHEST weight wins (see Collision Resolution)

# === Core code (weight 1-2) ===
"src/**"        = 1
"lib/**"        = 1
"app/**"        = 1
"core/**"       = 1
"pkg/**"        = 2
"internal/**"   = 2
"cmd/**"        = 2

# === Test code (weight 6) ===
# Path-based
"**/tests/**"     = 6
"**/test/**"      = 6
"**/__tests__/**" = 6
"**/spec/**"      = 6
# Filename-based
"*_test.py"       = 6
"test_*.py"       = 6
"*.test.ts"       = 6
"*.test.tsx"      = 6
"*.spec.js"       = 6
"*.spec.ts"       = 6
"*_test.go"       = 6

# === Docs and config (weight 7-8) ===
"docs/**"         = 8
"DOCS/**"         = 8
"*.md"            = 7
"examples/**"     = 7
"README*"         = 7

# === CI/CD and meta (weight 9) ===
".github/**"      = 9
".gitlab-ci.yml"  = 9
"Makefile"        = 5   # Actually useful for understanding build
"Dockerfile*"     = 5
"docker-compose*" = 5

# === Vendor trash (weight 10) ===
"vendor/**"       = 10
"node_modules/**" = 10
"third_party/**"  = 10
"**/generated/**" = 10
"**/*.gen.go"     = 10
"**/*.pb.go"      = 10
```

### Config Schema

```python
class PathWeightConfig(TypedDict):
    pattern: str    # Glob pattern (fnmatch style)
    weight: int     # 1-10

# Validation
def validate_path_weight(weight: int) -> int:
    if not 1 <= weight <= 10:
        raise ValueError(f"Path weight must be 1-10, got {weight}")
    return weight
```

---

## Collision Resolution

### The Problem

`src/tests/test_router.py` matches BOTH:
- `src/**` (weight 1)
- `**/tests/**` (weight 6)

Which wins?

### Decision: Highest Weight Wins (Pessimistic)

**Rationale:**
1. If ANY rule says "this is low priority", it probably is
2. Tests in `src/` are still tests - you want core code enriched first
3. Easy to reason about: "if anything deprioritizes it, it's deprioritized"
4. Explicit overrides let you escape: add `"src/critical_tests/**" = 2` if needed

### Algorithm

```python
def get_path_weight(
    file_path: str, 
    weight_config: dict[str, int]
) -> tuple[int, list[str]]:
    """
    Returns (final_weight, list_of_matched_patterns).
    
    If no patterns match, returns default weight (5).
    """
    matches = []
    
    for pattern, weight in weight_config.items():
        if fnmatch.fnmatch(file_path, pattern):
            matches.append((pattern, weight))
    
    if not matches:
        return (5, [])  # Default: middle of the road
    
    # Highest weight wins (pessimistic)
    winning_weight = max(w for _, w in matches)
    winning_patterns = [p for p, w in matches if w == winning_weight]
    
    return (winning_weight, winning_patterns)
```

### Alternative Strategies (Not Chosen)

| Strategy | Problem |
|----------|---------|
| First match wins | Config order becomes load-bearing, fragile |
| Longest match wins | "Longest" is fuzzy with globs |
| Lowest weight wins | Defeats the purpose - test code gets priority |
| Additive/average | Hard to reason about, weird edge cases |
| Most specific wins | "Specific" is undefined for globs |

---

## Test Code Detection

Beyond path patterns, detect test files by content signals (optional enhancement):

### Heuristics

```python
TEST_IMPORT_PATTERNS = [
    r'^import pytest',
    r'^from pytest import',
    r'^import unittest',
    r'^from unittest import',
    r'^import jest',
    r'^describe\(',
    r'^it\(',
    r'^test\(',
]

TEST_DECORATOR_PATTERNS = [
    r'@pytest\.',
    r'@Test',
    r'@Before',
    r'@After',
]

def is_test_file_by_content(content: str) -> bool:
    """Check if file content indicates test code."""
    # Only check first 50 lines for performance
    head = '
'.join(content.split('
')[:50])
    
    for pattern in TEST_IMPORT_PATTERNS + TEST_DECORATOR_PATTERNS:
        if re.search(pattern, head, re.MULTILINE):
            return True
    return False
```

### Neighbor Heuristics

```python
def is_test_file_by_neighbors(file_path: Path) -> bool:
    """Check if file lives near test infrastructure."""
    parent = file_path.parent
    test_markers = [
        'conftest.py',      # pytest
        'pytest.ini',       # pytest
        'jest.config.js',   # Jest
        'jest.config.ts',
        '.rspec',           # RSpec
        'setup.cfg',        # may contain [tool:pytest]
    ]
    
    for marker in test_markers:
        if (parent / marker).exists():
            return True
    return False
```

### Integration

If content/neighbor heuristics detect test code but no path pattern matched:

```python
def compute_path_weight(file_path: str, content: str, config: dict) -> int:
    weight, matched = get_path_weight(file_path, config)
    
    # If no explicit match but content says "test", apply default test weight
    if not matched:
        if is_test_file_by_content(content) or is_test_file_by_neighbors(Path(file_path)):
            return 6  # Default test weight
    
    return weight
```

---

## Debug/Introspection

### CLI: Show Weight Decisions

```bash
$ llmc enrich plan --show-weights

src/core/router.py              weight=1  (matched: src/**)
src/core/tests/test_router.py   weight=6  (matched: src/**, **/tests/** → highest: **/tests/**)
lib/utils.py                    weight=1  (matched: lib/**)
docs/api/example.py             weight=8  (matched: docs/**)
docs/README.md                  weight=8  (matched: docs/**, *.md → highest: docs/**)
vendor/requests/api.py          weight=10 (matched: vendor/**)
random_file.txt                 weight=5  (no match, default)
```

### Structured Output

```bash
$ llmc enrich plan --show-weights --json | jq '.[:3]'
[
  {
    "path": "src/core/router.py",
    "weight": 1,
    "matched_patterns": ["src/**"],
    "winning_pattern": "src/**",
    "base_priority": 100,
    "final_priority": 100
  },
  {
    "path": "src/core/tests/test_router.py",
    "weight": 6,
    "matched_patterns": ["src/**", "**/tests/**"],
    "winning_pattern": "**/tests/**",
    "base_priority": 100,
    "final_priority": 50
  }
]
```

---

## Updated NFR2

**Old (broken):**
> For a new repo with mixed content, at least 80% of the first N enriched files should be code files.

**New:**
> The enrichment runner SHALL respect path_weight ordering such that, absent concurrency effects, no file with weight W is enriched before all files with weight ≤ W-2 are complete, unless the higher-priority queue is exhausted or the starvation ratio is reached.

**Even simpler version:**
> Files with path_weight ≤ 3 SHALL be enriched before files with path_weight > 5, subject to configured starvation ratio.

---

## Implementation Plan

### Phase 1: Core Weight System (2h)

1. Add `[enrichment.path_weights]` config section
2. Implement `get_path_weight()` with collision resolution
3. Update `FileClassifier` to use weights instead of binary CODE/NON_CODE
4. Update priority formula: `final = base * (11 - weight) / 10`

### Phase 2: CLI & Debug (1h)

1. Add `--show-weights` flag to `llmc enrich plan`
2. Add JSON output option
3. Log weight decisions during enrichment

### Phase 3: Content Heuristics (Optional, 1h)

1. Implement test detection by content
2. Implement neighbor heuristics
3. Apply as fallback when no pattern matches

---

## Files to Modify

```
llmc/enrichment/
├── classifier.py      # FileClassifier gets weight support
├── scheduler.py       # Priority calculation uses weights
├── config.py          # PathWeightConfig schema
└── cli.py             # --show-weights flag

llmc.toml              # Default path_weights section
```

---

## Testing

### Unit Tests

```python
def test_path_weight_single_match():
    config = {"src/**": 1, "**/tests/**": 6}
    weight, matched = get_path_weight("src/router.py", config)
    assert weight == 1
    assert matched == ["src/**"]

def test_path_weight_collision_highest_wins():
    config = {"src/**": 1, "**/tests/**": 6}
    weight, matched = get_path_weight("src/tests/test_router.py", config)
    assert weight == 6  # Highest wins
    assert "**/tests/**" in matched

def test_path_weight_no_match_default():
    config = {"src/**": 1}
    weight, matched = get_path_weight("random/file.txt", config)
    assert weight == 5  # Default
    assert matched == []

def test_priority_formula():
    # weight 1: full priority
    assert compute_final_priority(base=100, weight=1) == 100
    # weight 6: half priority
    assert compute_final_priority(base=100, weight=6) == 50
    # weight 10: 10% priority
    assert compute_final_priority(base=100, weight=10) == 10
```

### Integration Tests

```python
def test_enrichment_order_respects_weights(tmp_repo):
    """Files with lower weights should be enriched first."""
    # Create mixed repo
    (tmp_repo / "src/core.py").write_text("# core code")
    (tmp_repo / "src/tests/test_core.py").write_text("import pytest")
    (tmp_repo / "docs/readme.md").write_text("# docs")
    
    # Run enrichment
    enriched_order = run_enrichment_capture_order(tmp_repo)
    
    # Assert ordering
    core_idx = enriched_order.index("src/core.py")
    test_idx = enriched_order.index("src/tests/test_core.py")
    docs_idx = enriched_order.index("docs/readme.md")
    
    assert core_idx < test_idx < docs_idx
```

---

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Glob performance on huge repos | Pre-compile patterns, short-circuit on first weight-10 match |
| User confusion about collision resolution | Clear docs, `--show-weights` debug mode |
| Over-configured mess | Ship sane defaults, let power users override |
| Test heuristics false positives | Content heuristics are fallback only, explicit patterns win |

---

## Summary

| Change | Impact |
|--------|--------|
| 1-10 weight scale | Granular priority control |
| Glob-based config | User-customizable, project-specific |
| Highest-weight-wins collision | Predictable, safe default |
| `--show-weights` debug | Transparency into decisions |

**Result:** Test code in `src/` gets deprioritized. Core code gets enriched first. Vendor trash goes to the back. All configurable.
