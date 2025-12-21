from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from llmc.main import app

runner = CliRunner()


def test_rag_doctor_embedding_model_not_found(tmp_path: Path):
    """
    Test `rag doctor` when embedding model is not found.
    """
    from llmc.rag.embeddings.check import EmbeddingCheckResult

    mock_check_results = [
        EmbeddingCheckResult(
            model_name="nomic-embed-text",
            passed=False,
            message="Warning: Embedding model 'nomic-embed-text' not found in Ollama.",
        )
    ]

    with patch(
        "llmc.rag.doctor.check_embedding_models", return_value=mock_check_results
    ), patch("llmc.rag.doctor._open_db") as mock_open_db:
        mock_db = MagicMock()
        mock_db.stats.return_value = {
            "files": 10,
            "spans": 100,
            "enrichments": 100,
            "embeddings": 100,
        }
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = [0]
        mock_conn.execute.return_value = mock_cursor
        mock_db.conn = mock_conn
        dummy_db_path = tmp_path / "test-repo/.rag/index_v2.db"
        mock_open_db.return_value = (mock_db, dummy_db_path)

        # Create a test repo
        repo_path = tmp_path / "test-repo"
        repo_path.mkdir()
        (repo_path / ".llmc").mkdir()
        (repo_path / "llmc.toml").write_text(
            """
[embeddings.profiles.docs]
provider = "ollama"
model = "nomic-embed-text"
"""
        )

        result = runner.invoke(app, ["debug", "doctor", "--repo-path", str(repo_path)], catch_exceptions=False)

        assert result.exit_code == 0
        assert (
            "Embedding check failed: Warning: Embedding model 'nomic-embed-text' not found in Ollama."
            in result.stdout
        )
