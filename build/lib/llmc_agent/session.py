"""Session management for llmc_agent.

Sessions persist conversation state across invocations.
Storage: ~/.llmc/sessions/<id>.json
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any
import uuid


@dataclass
class Message:
    """A single message in a conversation."""

    role: str  # "user", "assistant", "system"
    content: str
    tokens: int
    timestamp: str  # ISO format
    rag_sources: list[str] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Message:
        return cls(**data)


@dataclass
class Session:
    """A conversation session."""

    id: str
    created_at: str  # ISO format
    updated_at: str  # ISO format
    model: str
    repo_path: str | None = None
    messages: list[Message] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "model": self.model,
            "repo_path": self.repo_path,
            "messages": [m.to_dict() for m in self.messages],
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Session:
        messages = [Message.from_dict(m) for m in data.get("messages", [])]
        return cls(
            id=data["id"],
            created_at=data["created_at"],
            updated_at=data["updated_at"],
            model=data["model"],
            repo_path=data.get("repo_path"),
            messages=messages,
            metadata=data.get("metadata", {}),
        )

    def add_message(
        self,
        role: str,
        content: str,
        tokens: int,
        rag_sources: list[str] | None = None,
    ) -> None:
        """Add a message to the session."""
        self.messages.append(
            Message(
                role=role,
                content=content,
                tokens=tokens,
                timestamp=datetime.now(UTC).isoformat(),
                rag_sources=rag_sources,
            )
        )
        self.updated_at = datetime.now(UTC).isoformat()

    def total_tokens(self) -> int:
        """Total tokens in the session."""
        return sum(m.tokens for m in self.messages)

    def get_history_messages(self) -> list[dict[str, str]]:
        """Get messages in OpenAI format for context."""
        return [
            {"role": m.role, "content": m.content}
            for m in self.messages
            if m.role in ("user", "assistant")
        ]


class SessionManager:
    """Manages session storage and retrieval."""

    def __init__(self, storage_path: str | Path):
        self.storage = Path(storage_path).expanduser()
        self.sessions_dir = self.storage / "sessions"
        self.current_file = self.storage / "current_session"

        # Ensure directories exist
        self.sessions_dir.mkdir(parents=True, exist_ok=True)

    def get_current_id(self) -> str | None:
        """Get the current session ID."""
        if not self.current_file.exists():
            return None
        return self.current_file.read_text().strip() or None

    def set_current(self, session_id: str) -> None:
        """Set the current session ID."""
        self.current_file.write_text(session_id)

    def get_current(self) -> Session | None:
        """Load the current session."""
        session_id = self.get_current_id()
        if not session_id:
            return None
        return self.load(session_id)

    def create(
        self,
        model: str,
        repo_path: str | None = None,
    ) -> Session:
        """Create a new session."""
        now = datetime.now(UTC).isoformat()
        session = Session(
            id=self._generate_id(),
            created_at=now,
            updated_at=now,
            model=model,
            repo_path=repo_path,
            messages=[],
            metadata={},
        )
        self.save(session)
        self.set_current(session.id)
        return session

    def load(self, session_id: str) -> Session | None:
        """Load a session from disk."""
        path = self.sessions_dir / f"{session_id}.json"
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text())
            return Session.from_dict(data)
        except (json.JSONDecodeError, KeyError):
            return None

    def save(self, session: Session) -> None:
        """Save a session to disk."""
        session.updated_at = datetime.now(UTC).isoformat()
        path = self.sessions_dir / f"{session.id}.json"
        path.write_text(json.dumps(session.to_dict(), indent=2))

    def is_stale(self, session: Session, max_hours: float) -> bool:
        """Check if a session is stale."""
        try:
            updated = datetime.fromisoformat(session.updated_at.replace("Z", "+00:00"))
            now = datetime.now(UTC)
            age_hours = (now - updated).total_seconds() / 3600
            return age_hours > max_hours
        except (ValueError, TypeError):
            return True

    def list_recent(self, limit: int = 10) -> list[Session]:
        """List recent sessions, newest first."""
        sessions = []
        for path in self.sessions_dir.glob("*.json"):
            session = self.load(path.stem)
            if session:
                sessions.append(session)

        sessions.sort(key=lambda s: s.updated_at, reverse=True)
        return sessions[:limit]

    def _generate_id(self) -> str:
        """Generate a short unique ID."""
        return uuid.uuid4().hex[:8]


def get_session_manager(storage_path: str = "~/.llmc") -> SessionManager:
    """Get a session manager instance."""
    return SessionManager(storage_path)
