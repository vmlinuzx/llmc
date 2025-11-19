from __future__ import annotations

from pathlib import Path

import yaml


def _load_entries(mod, yaml_path: Path):
    # Try common entry points; adjust if the module evolves.
    if hasattr(mod, "load_registry_from_yaml"):
        return mod.load_registry_from_yaml(yaml_path)
    if hasattr(mod, "load_registry"):
        return mod.load_registry(yaml_path)
    if hasattr(mod, "_make_registry_entry_from_yaml"):
        with yaml_path.open("r", encoding="utf-8") as handle:
            doc = yaml.safe_load(handle)
        entries = []
        for item in (doc.get("repos", []) or []):
            entry = mod._make_registry_entry_from_yaml(item)
            if entry:
                entries.append(entry)
        return entries
    raise AttributeError("No known registry loader found in module. Implement loader per SDD.")


def _names(entries) -> list[str]:
    names: list[str] = []
    for entry in entries:
        if isinstance(entry, dict) and "name" in entry:
            names.append(entry["name"])
        elif hasattr(entry, "name"):
            names.append(entry.name)
    return names


def test_registry_workspace_validation(tmp_path: Path) -> None:
    from tools.rag_repo import registry as reg

    base = tmp_path / "repos"
    base.mkdir()
    (base / "okrepo").mkdir()
    (base / "badrepo").mkdir()

    payload = {
        "repos": [
            {
                "name": "okrepo",
                "repo_path": str(base / "okrepo"),
                "rag_workspace_path": ".llmc/work",
            },
            {
                "name": "badrepo",
                "repo_path": str(base / "badrepo"),
                "rag_workspace_path": "../../etc",
            },
        ]
    }
    yml = tmp_path / "registry.yaml"
    yml.write_text(yaml.safe_dump(payload), encoding="utf-8")

    entries = _load_entries(reg, yml)
    names = _names(entries)
    assert "okrepo" in names
    assert "badrepo" not in names

