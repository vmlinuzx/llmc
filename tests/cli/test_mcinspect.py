import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

# The app object must be imported from the app's file.
from llmc.mcinspect import app
from llmc.rag.inspector import DefinedSymbol, InspectionResult, RelatedEntity

# The runner object is used to invoke the CLI application.
runner = CliRunner()


def create_mock_result() -> InspectionResult:
    """Create a mock InspectionResult for consistent testing."""
    return InspectionResult(
        path="llmc/rag/enrichment_pipeline.py",
        source_mode="symbol",
        snippet="class EnrichmentPipeline:\n    pass",
        full_source="class EnrichmentPipeline:\n    pass",
        primary_span=(45, 312),
        file_summary="Orchestrates batch LLM enrichment with backend cascade and retry logic",
        graph_status="connected",
        defined_symbols=[
            DefinedSymbol(
                name="EnrichmentPipeline",
                line=45,
                type="class",
                summary="Main class for enrichment",
            )
        ],
        incoming_calls=[
            RelatedEntity(symbol="service.run", path="llmc/service.py"),
            RelatedEntity(
                symbol="workers.execute_enrichment", path="llmc/workers.py"
            ),
            RelatedEntity(symbol="daemon.idle_loop", path="llmc/daemon.py"),
        ],
        outgoing_calls=[
            RelatedEntity(
                symbol="Database.write_enrichment", path="llmc/rag/database.py"
            ),
            RelatedEntity(symbol="OllamaBackend.generate", path="llmc/rag/ollama.py"),
            RelatedEntity(symbol="RouterChain.select", path="llmc/rag/router.py"),
        ],
    )


@patch("llmc.mcinspect.find_repo_root", return_value=Path("/fake/repo"))
@patch("llmc.mcinspect.inspect_entity")
@patch("llmc.mcinspect._format_size", return_value=(267, 8200))
def test_mcinspect_default_summary_mode(
    mock_format_size, mock_inspect_entity, mock_find_repo_root
):
    """Test the default summary output."""
    mock_inspect_entity.return_value = create_mock_result()

    result = runner.invoke(app, ["EnrichmentPipeline"])

    assert result.exit_code == 0
    output = result.stdout
    assert "EnrichmentPipeline (class, llmc/rag/enrichment_pipeline.py:45-312)" in output
    assert "Orchestrates batch LLM enrichment" in output
    assert "Called by: service.run, workers.execute_enrichment, daemon.idle_loop" in output
    assert "Calls: Database.write_enrichment, OllamaBackend.generate, RouterChain.select" in output
    assert "Size: 267 lines" in output
    assert "8.0KB" in output
    assert "class EnrichmentPipeline" not in output  # No code dump


@patch("llmc.mcinspect.find_repo_root", return_value=Path("/fake/repo"))
@patch("llmc.mcinspect.inspect_entity")
def test_mcinspect_capsule_mode(mock_inspect_entity, mock_find_repo_root):
    """Test the --capsule flag for compact output."""
    mock_inspect_entity.return_value = create_mock_result()

    result = runner.invoke(app, ["EnrichmentPipeline", "--capsule"])

    assert result.exit_code == 0
    output = result.stdout
    assert "EnrichmentPipeline (llmc/rag/enrichment_pipeline.py)" in output
    assert "Purpose: Orchestrates batch LLM enrichment" in output
    assert "Key Exports: EnrichmentPipeline" in output
    assert "Dependencies: service.run, workers.execute_enrichment, daemon.idle_loop" in output
    assert "class EnrichmentPipeline" not in output


@patch("llmc.mcinspect.find_repo_root", return_value=Path("/fake/repo"))
@patch("llmc.mcinspect.inspect_entity")
def test_mcinspect_full_mode(mock_inspect_entity, mock_find_repo_root):
    """Test the --full flag for detailed code output."""
    mock_inspect_entity.return_value = create_mock_result()

    result = runner.invoke(app, ["EnrichmentPipeline", "--full"])

    assert result.exit_code == 0
    output = result.stdout
    assert "━━━ EnrichmentPipeline ━━━" in output
    assert "File: llmc/rag/enrichment_pipeline.py" in output
    assert "Definition:" in output
    assert "class EnrichmentPipeline" in output  # Code dump expected


@patch("llmc.mcinspect.find_repo_root", return_value=Path("/fake/repo"))
@patch("llmc.mcinspect.inspect_entity")
def test_mcinspect_json_mode(mock_inspect_entity, mock_find_repo_root):
    """Test the --json flag for programmatic output."""
    mock_result = create_mock_result()
    mock_inspect_entity.return_value = mock_result

    result = runner.invoke(app, ["EnrichmentPipeline", "--json"])

    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["path"] == "llmc/rag/enrichment_pipeline.py"
    assert data["file_summary"] == mock_result.file_summary
    assert len(data["incoming_calls"]) == 3
    assert data["incoming_calls"][0]["symbol"] == "service.run"


@patch("llmc.mcinspect.find_repo_root", return_value=Path("/fake/repo"))
@patch("llmc.mcinspect.inspect_entity", return_value=None)
def test_mcinspect_symbol_not_found(mock_inspect_entity, mock_find_repo_root):
    """Test the case where the symbol is not found."""
    result = runner.invoke(app, ["NonExistentSymbol"])
    assert result.exit_code == 1
    assert "Symbol not found: NonExistentSymbol" in result.stdout
