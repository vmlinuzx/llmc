from abc import ABC, abstractmethod
from typing import Any

from llmc.routing.query_type import classify_query


class Router(ABC):
    """Abstract base class for query routers."""
    
    @abstractmethod
    def decide_route(self, query_text: str, tool_context: dict[str, Any] | None = None) -> dict[str, Any]:
        """
        Decide the primary route for a given query.
        
        Returns:
            Dict containing:
            - route_name: str
            - confidence: float
            - reasons: List[str]
        """
        pass

class DeterministicRouter(Router):
    """Router implementation that uses deterministic heuristics (classify_query)."""
    
    def __init__(self, config: dict[str, Any] = None):
        self.config = config or {}
        
    def decide_route(self, query_text: str, tool_context: dict[str, Any] | None = None) -> dict[str, Any]:
        return classify_query(query_text, tool_context)

def create_router(config: dict[str, Any]) -> Router:
    """Factory to create a router instance based on configuration."""
    # Default to deterministic
    mode = config.get("routing", {}).get("options", {}).get("router_mode", "deterministic")
    
    if mode == "deterministic":
        return DeterministicRouter(config)
    
    # Future:
    # if mode == "learned":
    #     return LearnedRouter(config)
        
    raise ValueError(f"Unknown router_mode: {mode}")
