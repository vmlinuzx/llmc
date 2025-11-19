from __future__ import annotations

import re
from pathlib import Path

# Safety: ONLY rewrite literal 'except:' with no qualifiers.
PATTERN = re.compile(r"(?m)^([ \t]*)except:\s*$")


def rewrite_repo(repo_root: Path) -> int:
    """
    Rewrite bare `except:` clauses to `except Exception:` across the repo.

    This is intentionally conservative and only touches lines that match the
    exact pattern; it does not modify typed handlers or BaseException uses.
    """
    changed = 0
    for path in repo_root.rglob("*.py"):
        if "/.git/" in str(path):
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        new_text = PATTERN.sub(r"\1except Exception:", text)
        if new_text != text:
            path.write_text(new_text, encoding="utf-8")
            changed += 1
    return changed


if __name__ == "__main__":
    root = Path(".").resolve()
    count = rewrite_repo(root)
    print(f"Rewrote {count} files (bare 'except:' -> 'except Exception:').")

