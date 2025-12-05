
from pathlib import Path
from typing import Annotated

import typer
import yaml

from llmc.core import find_repo_root
from llmc.ruta.config import get_artifact_dir
from llmc.ruta.trace import TraceRecorder
from llmc.ruta.types import Scenario

app = typer.Typer(help="Ruthless User Testing Agent (RUTA)")

@app.command()
def init():
    """Initialize RUTA artifacts directory."""
    repo_root = find_repo_root()
    artifact_dir = get_artifact_dir(repo_root)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    typer.echo(f"Initialized RUTA artifacts at: {artifact_dir}")

@app.command()
def run(
    scenario: Annotated[str, typer.Argument(help="Scenario ID or path")],
    suite: Annotated[str, typer.Option(help="Test suite tag")] = None,
    manual: Annotated[bool, typer.Option(help="Run in manual mode (no agent)")] = False,
):
    """Run a user test scenario."""
    repo_root = find_repo_root()
    artifact_dir = get_artifact_dir(repo_root)
    
    run_id = f"ruta_run_{scenario}"
    recorder = TraceRecorder(run_id, artifact_dir)
    
    # Load scenario (Common for both modes)
    scenario_path = Path(scenario)
    if not scenario_path.exists():
            # try looking in tests/usertests/
            scenario_path = repo_root / "tests/usertests" / f"{scenario}.yaml"
    
    if not scenario_path.exists():
        typer.echo(f"Error: Scenario file not found: {scenario}")
        recorder.log_event("error", "orchestrator", metadata={"msg": f"Scenario not found: {scenario}"})
        recorder.close()
        raise typer.Exit(1)
        
    with open(scenario_path) as f:
        try:
            scenario_data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            typer.echo(f"Error parsing YAML: {e}")
            recorder.close()
            raise typer.Exit(1)
        
    try:
        scen = Scenario(**scenario_data)
    except Exception as e:
        typer.echo(f"Invalid scenario definition: {e}")
        recorder.close()
        raise typer.Exit(1)

    if manual:
        typer.echo("Running in MANUAL mode (legacy Phase 1 logic)...")
        # ... (Keep existing manual logic or deprecate it. For now, let's keep it simple and just use Executor for everything but maybe with a flag?)
        # Actually, let's just use the Executor for the main path.
        # The manual mode in Phase 1 was a temporary hardcoded loop. 
        # The Executor in Phase 2 covers this.
        # But to preserve the "manual" flag behavior if needed, we can just warn.
        pass

    # Phase 2: User Executor
    import json

    from llmc.ruta.executor import UserExecutor
    from llmc.ruta.judge import Judge

    executor = UserExecutor(scen, recorder, repo_root)
    executor.run()
    
    recorder.log_event("system", "orchestrator", metadata={"msg": "Run finished"})
    recorder.close()
    typer.echo(f"Trace saved to {recorder.trace_file}")

    # Phase 3: Judge
    typer.echo("Evaluating run...")
    judge = Judge(scen, recorder.trace_file)
    report = judge.evaluate()
    
    safe_run_id = run_id.replace("/", "_").replace("\\", "_")
    report_file = artifact_dir / f"report_{safe_run_id}.json"
    with open(report_file, "w") as f:
        json.dump(report, f, indent=2)
        
    typer.echo(f"Report saved to {report_file}")
    
    if report["status"] == "FAIL":
        typer.echo(typer.style("Run FAILED", fg=typer.colors.RED, bold=True))
        for inc in report["incidents"]:
            typer.echo(f" - [{inc['severity']}] {inc['summary']}")
        raise typer.Exit(1)
    else:
        typer.echo(typer.style("Run PASSED", fg=typer.colors.GREEN, bold=True))
