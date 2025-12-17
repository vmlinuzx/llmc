"""Test enrichment with real AEGIS repository data.

This test validates that the enrichment system properly handles data from
the AEGIS repository (a real-world codebase with 84+ Python files).

It tests:
1. Repository indexing and span creation
2. Batch enrichment processing
3. Data quality and completeness validation
4. Proper database record creation
"""

from __future__ import annotations

from pathlib import Path
import shutil
from typing import Any

import pytest

from llmc.rag.database import Database
from llmc.rag.enrichment import EnrichmentBatchResult, batch_enrich
from llmc.rag.indexer import index_repo
from llmc.rag.workers import enrichment_plan

AEGIS_REPO_PATH = Path("/home/vmlinux/srcwpsg/aegis")


def _mock_llm_call(prompt: dict[str, Any]) -> dict[str, Any]:
    """Mock LLM call for enrichment testing.

    Returns a valid enrichment payload based on the prompt content.
    """
    prompt.get("span_hash", "unknown")
    path = prompt.get("path", "unknown")
    lines = prompt.get("lines", [1, 10])

    # Create a realistic summary based on the file path
    if "brand" in path.lower():
        summary = f"Brand enrichment function for {Path(path).name}. Handles brand data processing and validation."
    elif "worker" in path.lower():
        summary = f"Worker module for {Path(path).name}. Processes data according to AEGIS pipeline."
    elif "loader" in path.lower():
        summary = f"Data loader component in {Path(path).name}. Handles ingestion and transformation."
    elif "capsule" in path.lower():
        summary = f"Capsule module in {Path(path).name}. Encapsulates specific AEGIS functionality."
    elif "core" in path.lower():
        summary = f"Core module {Path(path).name}. Contains main AEGIS business logic."
    elif "discover" in path.lower():
        summary = f"Discovery module in {Path(path).name}. Handles web scraping and data discovery."
    elif "llm" in path.lower():
        summary = (
            f"LLM client module in {Path(path).name}. Manages AI service integration."
        )
    else:
        summary = f"Module {Path(path).name} from AEGIS repository. Contains implementation details."

    # Use actual line ranges from the prompt, with bounds checking
    start_line, end_line = lines
    # Provide evidence within the actual span range, or use the full range if valid
    evidence_lines = [start_line, min(start_line + 9, end_line)]

    return {
        "summary_120w": summary,
        "tags": ["aegis", "test", "python"],
        "inputs": ["input_data", "config"],
        "outputs": ["processed_data", "status"],
        "side_effects": ["data_modification", "logging"],
        "pitfalls": ["handle_none_values", "validate_input"],
        "usage_snippet": f"# Usage example for {Path(path).name}",
        "evidence": [
            {"field": "summary_120w", "lines": evidence_lines},
            {"field": "tags", "lines": evidence_lines},
        ],
        "schema_version": "enrichment.v1",
        "model": "mock-model",
    }


def test_enrich_aegis_repository_basic(tmp_path: Path) -> None:
    """Test basic enrichment of AEGIS repository."""
    if not AEGIS_REPO_PATH.exists():
        pytest.skip(f"AEGIS repository not found at {AEGIS_REPO_PATH}")

    # Setup: Copy AEGIS to test directory
    test_repo = tmp_path / "aegis_test"
    print(f"\n[*] Copying AEGIS repository to {test_repo}...")
    shutil.copytree(AEGIS_REPO_PATH, test_repo)

    # Ensure a fresh RAG workspace so index_repo performs real work.
    rag_dir = test_repo / ".rag"
    if rag_dir.exists():
        shutil.rmtree(rag_dir)

    # Note: index_repo uses find_repo_root() to detect the repo, so we need to run it from the test repo
    import os

    original_cwd = os.getcwd()
    try:
        os.chdir(test_repo)
        # The DB path is determined inside index_repo using index_path_for_write
        # which looks for .llmc/rag directory relative to the detected repo root
        print("[*] Indexing repository...")

        # Step 1: Index the repository
        stats = index_repo(include_paths=None, since=None)

        # Get the actual DB path that was created
        from llmc.rag.config import index_path_for_write
        from llmc.rag.utils import find_repo_root

        db_path = index_path_for_write(find_repo_root())

        print(f"    Files indexed: {stats.files}")
        print(f"    Spans created: {stats.spans}")

        assert stats.files > 0, "No files were indexed"
        assert stats.spans > 0, "No spans were created"

        # Step 2: Verify database structure
        print("\n[*] Verifying database structure...")
        db = Database(db_path)

        # Check tables exist
        tables = {
            row[0]
            for row in db.conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }

        required_tables = {"files", "spans"}
        assert required_tables.issubset(
            tables
        ), f"Missing required tables. Found: {tables}"

        # Check span count
        span_count = db.conn.execute("SELECT COUNT(*) FROM spans").fetchone()[0]
        print(f"    Total spans in DB: {span_count}")
        assert span_count > 0, "No spans found in database"

        # Check file count
        file_count = db.conn.execute("SELECT COUNT(*) FROM files").fetchone()[0]
        print(f"    Total files in DB: {file_count}")
        assert file_count > 0, "No files found in database"

        # Step 3: Create enrichment plan
        print("\n[*] Creating enrichment plan...")
        plan = enrichment_plan(db, test_repo, limit=50, cooldown_seconds=0)

        print(f"    Pending enrichments: {len(plan)}")
        assert len(plan) > 0, "No pending enrichments found"

        # Verify plan structure
        for item in plan[:3]:  # Check first 3 items
            assert "span_hash" in item
            assert "path" in item
            assert "lang" in item
            assert "lines" in item
            assert "code_snippet" in item

        # Step 4: Run enrichment
        print("\n[*] Running enrichment batch...")
        result = batch_enrich(
            db=db,
            repo_root=test_repo,
            llm_call=_mock_llm_call,
            batch_size=10,
            model="mock-model",
        )

        print(f"    Attempted: {result.attempted}")
        print(f"    Succeeded: {result.succeeded}")
        print(f"    Failed: {result.failed}")

        assert isinstance(result, EnrichmentBatchResult)
        assert result.attempted > 0, "No enrichments were attempted"
        assert result.succeeded > 0, "No enrichments succeeded"

        # Step 5: Verify enrichment records
        print("\n[*] Verifying enrichment records...")

        enrich_count = db.conn.execute("SELECT COUNT(*) FROM enrichments").fetchone()[0]
        print(f"    Total enrichment records: {enrich_count}")

        assert enrich_count > 0, "No enrichment records were created"

        # Verify enrichment data quality
        sample = db.conn.execute(
            """
            SELECT e.summary, e.model, e.schema_ver, e.usage_snippet, e.tags
            FROM enrichments e
            LIMIT 5
            """
        ).fetchall()

        print("\n    Sample enrichment records:")
        for row in sample:
            summary, model, schema, usage, tags = row
            print(f"      - Model: {model}, Schema: {schema}")
            print(f"        Summary: {summary[:80]}...")
            print(f"        Tags: {tags}")
            print(f"        Usage: {usage[:60]}...")

            assert summary is not None and len(summary) > 0, "Empty summary"
            assert model == "mock-model", "Incorrect model name"
            assert schema == "enrichment.v1", "Incorrect schema version"

        # Step 6: Validate enrichment completeness
        print("\n[*] Validating enrichment completeness...")

        # Check that some spans were enriched
        enrichment_rate = enrich_count / span_count if span_count > 0 else 0
        print(f"    Enrichment rate: {enrichment_rate:.2%}")

        # We expect at least 1% enrichment rate for this test
        # (many spans might be ignored or skipped due to various reasons)
        assert enrich_count > 0, "No enrichments were created"
        assert enrichment_rate >= 0.01, f"Low enrichment rate: {enrichment_rate:.2%}"

        print("\n[✓] AEGIS enrichment test completed successfully!")
        print(f"    Repository: {AEGIS_REPO_PATH.name}")
        print(f"    Files indexed: {stats.files}")
        print(f"    Spans created: {stats.spans}")
        print(f"    Enrichments: {enrich_count}/{span_count} ({enrichment_rate:.2%})")

    finally:
        os.chdir(original_cwd)


def test_enrich_aegis_specific_modules(tmp_path: Path) -> None:
    """Test enrichment of specific AEGIS modules with detailed validation."""
    if not AEGIS_REPO_PATH.exists():
        pytest.skip(f"AEGIS repository not found at {AEGIS_REPO_PATH}")

    test_repo = tmp_path / "aegis_test_modules"
    print(f"\n[*] Setting up test repository at {test_repo}...")
    shutil.copytree(AEGIS_REPO_PATH, test_repo)

    # Ensure a fresh RAG workspace to avoid reusing stale indexes.
    rag_dir = test_repo / ".rag"
    if rag_dir.exists():
        shutil.rmtree(rag_dir)

    # Note: index_repo uses find_repo_root() to detect the repo, so we need to run it from the test repo
    import os

    original_cwd = os.getcwd()
    try:
        os.chdir(test_repo)
        db_path = test_repo / ".llmc" / "rag" / "index_v2.db"

        # Index repository
        stats = index_repo(include_paths=None, since=None)
        assert stats.spans > 0, "No spans created"

        db = Database(db_path)

        # Focus on specific high-value modules
        target_modules = [
            "core.py",
            "worker_enrich_atts.py",
            "tools/enrich_brand.py",
            "loader/bc2bq.py",
        ]

        print("\n[*] Validating specific module enrichments...")

        for module_name in target_modules:
            module_path = test_repo / module_name
            if not module_path.exists():
                print(f"    [SKIP] {module_name} (not found)")
                continue

            # Check if module has spans
            span_hashes = db.conn.execute(
                """
                SELECT s.span_hash
                FROM spans s
                JOIN files f ON s.file_id = f.id
                WHERE f.path = ?
                """,
                (str(module_name),),
            ).fetchall()

            if not span_hashes:
                print(f"    [SKIP] {module_name} (no spans)")
                continue

            print(f"\n    Module: {module_name}")
            print(f"        Spans: {len(span_hashes)}")

            # Check enrichment records
            enriched = db.conn.execute(
                """
                SELECT COUNT(*)
                FROM enrichments e
                WHERE e.span_hash IN (
                    SELECT s.span_hash
                    FROM spans s
                    JOIN files f ON s.file_id = f.id
                    WHERE f.path = ?
                )
                """,
                (str(module_name),),
            ).fetchone()[0]

            print(f"        Enriched: {enriched}")

            # Verify enrichment quality
            enrichment = db.conn.execute(
                """
                SELECT e.summary, e.tags
                FROM enrichments e
                WHERE e.span_hash IN (
                    SELECT s.span_hash
                    FROM spans s
                    JOIN files f ON s.file_id = f.id
                    WHERE f.path = ?
                )
                LIMIT 1
                """,
                (str(module_name),),
            ).fetchone()

            if enrichment:
                summary, tags = enrichment
                assert summary is not None and len(summary) > 10
                assert tags is not None
                print(f"        ✓ Summary: {summary[:60]}...")
                print(f"        ✓ Tags: {tags}")

        print("\n[✓] Module-specific validation completed!")

    finally:
        os.chdir(original_cwd)


def test_enrich_aegis_data_integrity(tmp_path: Path) -> None:
    """Test data integrity of enriched AEGIS repository."""
    if not AEGIS_REPO_PATH.exists():
        pytest.skip(f"AEGIS repository not found at {AEGIS_REPO_PATH}")

    test_repo = tmp_path / "aegis_integrity"
    shutil.copytree(AEGIS_REPO_PATH, test_repo)

    # Ensure a clean workspace for integrity checks.
    rag_dir = test_repo / ".rag"
    if rag_dir.exists():
        shutil.rmtree(rag_dir)

    # Note: index_repo uses find_repo_root() to detect the repo, so we need to run it from the test repo
    import os

    original_cwd = os.getcwd()
    try:
        os.chdir(test_repo)
        from llmc.rag.config import index_path_for_write
        from llmc.rag.utils import find_repo_root

        db_path = index_path_for_write(find_repo_root())
        index_repo(include_paths=None, since=None)
        db = Database(db_path)

        print("\n[*] Testing data integrity...")

        # Run enrichment
        result = batch_enrich(
            db=db,
            repo_root=test_repo,
            llm_call=_mock_llm_call,
            batch_size=20,
            model="mock-model",
        )

        assert result.succeeded > 0, "No enrichments succeeded"

        # Verify foreign key relationships
        orphan_enrichments = db.conn.execute(
            """
            SELECT COUNT(*)
            FROM enrichments e
            LEFT JOIN spans s ON e.span_hash = s.span_hash
            WHERE s.span_hash IS NULL
            """
        ).fetchone()[0]

        print(f"    Orphan enrichments: {orphan_enrichments}")
        assert orphan_enrichments == 0, "Found orphan enrichment records"

        # Verify all required fields are populated
        null_summaries = db.conn.execute(
            """
            SELECT COUNT(*)
            FROM enrichments
            WHERE summary IS NULL OR summary = ''
            """
        ).fetchone()[0]

        print(f"    Null/empty summaries: {null_summaries}")
        assert null_summaries == 0, "Found null or empty summaries"

        # Verify evidence references
        records_with_evidence = db.conn.execute(
            """
            SELECT COUNT(*)
            FROM enrichments
            WHERE evidence IS NOT NULL AND evidence != ''
            """
        ).fetchone()[0]

        total_enrichments = db.conn.execute(
            "SELECT COUNT(*) FROM enrichments"
        ).fetchone()[0]

        print(f"    Records with evidence: {records_with_evidence}/{total_enrichments}")
        assert records_with_evidence > 0, "No records have evidence"

        print("\n[✓] Data integrity validation passed!")

    finally:
        os.chdir(original_cwd)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
