## 2025-12-17 - Path Canonicalization Bypass
**Vulnerability:** `llmc.security.normalize_path` verified path containment but returned the original non-canonical input path (e.g., `subdir/../subdir/file.txt`).
**Learning:** Security checks relying on path strings (like prefix matching) can be bypassed if the path is not canonicalized, even if it technically points to a safe file. "Safe file" != "Safe path string".
**Prevention:** Security normalization functions must return the *normalized* form they validated, not the raw input.
