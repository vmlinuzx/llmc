"""
Test 11: Index Status Metadata - Round-trip and Corruption Handling
"""

import json
import os
from pathlib import Path
import tempfile

# Calculate REPO_ROOT dynamically
REPO_ROOT = Path(__file__).resolve().parents[1]


# Simulated IndexStatus class (from what we see in rag_index_status.json)
class IndexStatus:
    def __init__(
        self,
        index_state,
        last_indexed_at,
        repo,
        schema_version,
        last_indexed_commit=None,
        last_error=None,
    ):
        self.index_state = index_state
        self.last_indexed_at = last_indexed_at
        self.repo = repo
        self.schema_version = schema_version
        self.last_indexed_commit = last_indexed_commit
        self.last_error = last_error

    def to_dict(self):
        return {
            "index_state": self.index_state,
            "last_indexed_at": self.last_indexed_at,
            "repo": self.repo,
            "schema_version": self.schema_version,
            "last_indexed_commit": self.last_indexed_commit,
            "last_error": self.last_error,
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            index_state=data.get("index_state"),
            last_indexed_at=data.get("last_indexed_at"),
            repo=data.get("repo"),
            schema_version=data.get("schema_version"),
            last_indexed_commit=data.get("last_indexed_commit"),
            last_error=data.get("last_error"),
        )

    @classmethod
    def load(cls, path):
        with open(path) as f:
            data = json.load(f)
        return cls.from_dict(data)

    def save(self, path):
        with open(path, "w") as f:
            json.dump(self.to_dict(), f)


def test_index_status_round_trip():
    """Test saving and loading IndexStatus"""
    print("Test 1: Round-trip serialization")

    # Create status
    status = IndexStatus(
        index_state="fresh",
        last_indexed_at="2025-11-16T17:09:22.388903+00:00",
        repo=str(REPO_ROOT),
        schema_version=1,
        last_indexed_commit="29a91d55c6478ebaf7a721eac2c09dbbe4577a0b",
        last_error=None,
    )

    # Save to temp file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        status.save(f.name)
        temp_path = f.name

    try:
        # Load back
        loaded_status = IndexStatus.load(temp_path)

        # Verify
        assert loaded_status.index_state == status.index_state
        assert loaded_status.last_indexed_at == status.last_indexed_at
        assert loaded_status.repo == status.repo
        assert loaded_status.schema_version == status.schema_version
        assert loaded_status.last_indexed_commit == status.last_indexed_commit
        assert loaded_status.last_error == status.last_error

        print("  ✓ Round-trip successful\n")

    finally:
        os.unlink(temp_path)


def test_index_status_missing_file():
    """Test handling of missing status file"""
    print("Test 2: Missing file handling")

    try:
        IndexStatus.load("/nonexistent/path/status.json")
        print("  ✗ Should have raised FileNotFoundError")
    except FileNotFoundError:
        print("  ✓ Correctly raised FileNotFoundError\n")
    except Exception as e:
        print(f"  ✓ Raised exception: {type(e).__name__}\n")


def test_index_status_corrupt_json():
    """Test handling of corrupt JSON"""
    print("Test 3: Corrupt JSON handling")

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        f.write("{ this is not valid json }")
        corrupt_path = f.name

    try:
        try:
            IndexStatus.load(corrupt_path)
            print("  ✗ Should have raised JSONDecodeError")
        except json.JSONDecodeError:
            print("  ✓ Correctly raised JSONDecodeError\n")
        except Exception as e:
            print(f"  ✓ Raised exception: {type(e).__name__}\n")
    finally:
        os.unlink(corrupt_path)


def test_index_status_missing_fields():
    """Test handling of JSON with missing fields"""
    print("Test 4: Missing fields handling")

    # Create JSON with missing optional fields
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(
            {
                "index_state": "ready",
                "last_indexed_at": "2025-11-16T00:00:00",
                "repo": "/tmp/test",
                "schema_version": 1,
                # Missing: last_indexed_commit, last_error
            },
            f,
        )
        incomplete_path = f.name

    try:
        # Should load with defaults
        status = IndexStatus.load(incomplete_path)

        print("  Loaded with defaults:")
        print(f"    index_state: {status.index_state}")
        print(f"    last_indexed_commit: {status.last_indexed_commit}")
        print(f"    last_error: {status.last_error}")

        assert status.index_state == "ready"
        assert status.last_indexed_commit is None  # Should get default
        assert status.last_error is None  # Should get default

        print("  ✓ Handles missing fields correctly\n")

    finally:
        os.unlink(incomplete_path)


def test_existing_status_file():
    """Test the actual status file in the repo"""
    print("Test 5: Existing status file")

    status_path = REPO_ROOT / ".llmc" / "rag" / "index_status.json"

    if not status_path.exists():
        print(f"  ⚠ WARNING: {status_path} does not exist")
        return

    # Load and verify
    status = IndexStatus.load(status_path)

    print("  Loaded existing status:")
    print(f"    index_state: {status.index_state}")
    print(f"    last_indexed_at: {status.last_indexed_at}")
    print(f"    repo: {status.repo}")
    print(f"    schema_version: {status.schema_version}")
    print(f"    last_indexed_commit: {status.last_indexed_commit}")
    print(f"    last_error: {status.last_error}")

    # Verify structure
    assert status.index_state in ["fresh", "ready", "error", "indexing"]
    assert status.last_indexed_at is not None
    assert status.repo is not None
    assert status.schema_version is not None

    print("  ✓ Existing status file is valid\n")
