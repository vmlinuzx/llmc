"""File-based state store for LLMC RAG Daemon."""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional
from collections.abc import Callable

from .models import RepoState


class StateStore:
    """Persist per-repo state as individual JSON files."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def _path_for(self, repo_id: str) -> Path:
        return self.root / f"{repo_id}.json"

    def load_all(self) -> Dict[str, RepoState]:
        states: Dict[str, RepoState] = {}
        for path in self.root.glob("*.json"):
            try:
                state = self._load_path(path)
                states[state.repo_id] = state
            except Exception:
                # Corrupt state for a single repo should not break the daemon.
                continue
        return states

    def get(self, repo_id: str) -> Optional[RepoState]:
        path = self._path_for(repo_id)
        if not path.exists():
            return None
        return self._load_path(path)

    def upsert(self, state: RepoState) -> None:
        path = self._path_for(state.repo_id)
        tmp = path.with_suffix(".json.tmp")
        payload = self._serialize(state)
        tmp.write_text(payload, encoding="utf-8")
        tmp.replace(path)

    def update(self, repo_id: str, mutator: Callable[[RepoState], RepoState]) -> RepoState:
        state = self.get(repo_id) or RepoState(repo_id=repo_id)
        new_state = mutator(state)
        self.upsert(new_state)
        return new_state

    # Internal helpers -------------------------------------------------

    def _load_path(self, path: Path) -> RepoState:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return self._deserialize(raw)

    def _serialize(self, state: RepoState) -> str:
        data = asdict(state)

        def encode_dt(dt: Optional[datetime]) -> Optional[str]:
            return dt.isoformat() if dt is not None else None

        data["last_run_started_at"] = encode_dt(state.last_run_started_at)
        data["last_run_finished_at"] = encode_dt(state.last_run_finished_at)
        data["next_eligible_at"] = encode_dt(state.next_eligible_at)
        return json.dumps(data, sort_keys=True)

    def _deserialize(self, data: Dict) -> RepoState:
        def parse_dt(value):
            if not value:
                return None
            return datetime.fromisoformat(value)

        return RepoState(
            repo_id=data["repo_id"],
            last_run_started_at=parse_dt(data.get("last_run_started_at")),
            last_run_finished_at=parse_dt(data.get("last_run_finished_at")),
            last_run_status=data.get("last_run_status", "never"),
            last_error_reason=data.get("last_error_reason"),
            consecutive_failures=int(data.get("consecutive_failures", 0)),
            next_eligible_at=parse_dt(data.get("next_eligible_at")),
            last_job_summary=data.get("last_job_summary"),
        )
