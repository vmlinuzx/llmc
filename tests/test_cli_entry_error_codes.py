from __future__ import annotations

from pathlib import Path
import subprocess
import sys

from llmc.rag_repo import cli_entry


def test_cli_error_code_for_bad_workspace(tmp_path, capsys) -> None:
    repo = tmp_path / "repo"
    (repo / ".llmc" / "workspace").mkdir(parents=True)
    code = cli_entry.main(
        ["doctor-paths", "--repo", str(repo), "--workspace", "../escape", "--json"]
    )
    assert code == 2
    err = capsys.readouterr().err
    assert "ERROR:" in err


def test_cli_import_error_message(monkeypatch, tmp_path):
    """
    Test that the CLI prints a helpful error and exits if core modules are missing.
    """
    import os

    # from pathlib import Path # Path is now imported at top level

    # Simulate llmc.rag_nav not being available
    monkeypatch.setitem(sys.modules, "llmc.rag_nav.metadata", None)

    # The path to the script to run
    cli_script_path = Path(__file__).parents[1] / "llmc/cli.py"

    # Create a fake llmc package in a temporary directory
    # This will shadow the real llmc package and cause the import of submodules to fail
    fake_site_packages = tmp_path / "fake_site_packages"
    fake_site_packages.mkdir()
    (fake_site_packages / "llmc").mkdir()
    (fake_site_packages / "llmc" / "__init__.py").touch()

    # Prepend the fake package location to PYTHONPATH
    # We also explicitly add user site packages to ensure typer/rich are found,
    # as the subprocess environment seems to lose them otherwise.
    import site

    env = os.environ.copy()
    user_site = site.getusersitepackages()
    original_pythonpath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = (
        str(fake_site_packages)
        + os.pathsep
        + user_site
        + os.pathsep
        + original_pythonpath
    )

    result = subprocess.run(
        [sys.executable, str(cli_script_path), "monitor"],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )

    # Assert that it exits with an error code
    assert result.returncode == 1

    # Assert that the specific error message is shown to the user
    assert "LLMC core modules not found" in result.stdout
    assert "pip install" not in result.stdout  # Ensure it's not the rich/typer error


def test_cli_route_command(tmp_path):
    """
    Test the 'route' CLI command for a basic routing decision.
    """
    import os
    import site

    # Create a dummy file to test routing on
    test_file = tmp_path / "pyproject.toml"
    test_file.write_text("[tool.poetry]")

    # Create llmc.toml to define the routing rules
    # SDD expects 'pyproject.toml' -> 'config'
    config_file = tmp_path / "llmc.toml"
    config_file.write_text('[repository.path_overrides]\n"pyproject.toml" = "config"\n')

    project_root = Path(__file__).parents[1]
    cli_script_path = project_root / "llmc/cli.py"

    # Ensure typer/rich AND llmc package are found
    env = os.environ.copy()
    user_site = site.getusersitepackages()
    original_pythonpath = env.get("PYTHONPATH", "")
    # Prepend project root to PYTHONPATH
    env["PYTHONPATH"] = (
        str(project_root) + os.pathsep + user_site + os.pathsep + original_pythonpath
    )

    result = subprocess.run(
        [sys.executable, str(cli_script_path), "route", "--test", test_file.name],
        check=False,
        capture_output=True,
        text=True,
        cwd=tmp_path,  # Run from tmp_path to ensure relative paths work
        env=env,
    )

    assert result.returncode == 0
    # Note: rich console in subprocess strips markup by default, so we assert plain text
    assert "Domain: config" in result.stdout


def test_cli_route_command_show_reason(tmp_path):
    """
    Test the 'route' CLI command with the --show-domain-decisions flag.
    """
    import os
    import site

    test_file = tmp_path / "README.md"
    test_file.write_text("# My Project")

    # Create llmc.toml to define the routing rules
    # SDD expects 'README.md' -> 'docs'
    config_file = tmp_path / "llmc.toml"
    config_file.write_text('[repository.path_overrides]\n"README.md" = "docs"\n')

    project_root = Path(__file__).parents[1]
    cli_script_path = project_root / "llmc/cli.py"

    # Ensure typer/rich AND llmc package are found
    env = os.environ.copy()
    user_site = site.getusersitepackages()
    original_pythonpath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = (
        str(project_root) + os.pathsep + user_site + os.pathsep + original_pythonpath
    )

    result = subprocess.run(
        [
            sys.executable,
            str(cli_script_path),
            "route",
            "--test",
            test_file.name,
            "--show-domain-decisions",
        ],
        check=False,
        capture_output=True,
        text=True,
        cwd=tmp_path,
        env=env,
    )

    assert result.returncode == 0
    # Note: rich console in subprocess strips markup by default, so we assert plain text
    assert "Domain: docs" in result.stdout
    assert "Reason: " in result.stdout
