from collections.abc import Callable
import time

from llmc.client import RAGClient
from llmc.ruta.trace import TraceRecorder
from llmc.ruta.types import Scenario


# Define a simple Tool interface
class Tool:
    def __init__(self, name: str, func: Callable, description: str):
        self.name = name
        self.func = func
        self.description = description

    def __call__(self, **kwargs):
        return self.func(**kwargs)


class Toolbox:
    def __init__(self, repo_root):
        self.client = RAGClient(repo_root)
        self.tools: dict[str, Tool] = {}
        self._register_defaults()

    def _register_defaults(self):
        self.register(
            "rag_search",
            self.client.search,
            "Search the codebase. Args: query (str), limit (int)",
        )
        self.register(
            "rag_where_used",
            self.client.where_used,
            "Find usages of a symbol. Args: symbol (str), limit (int)",
        )
        # Add more tools as needed (e.g. run_cmd wrapper)

    def register(self, name: str, func: Callable, description: str):
        self.tools[name] = Tool(name, func, description)

    def get(self, name: str) -> Tool | None:
        return self.tools.get(name)

    def list_tools(self) -> list[dict[str, str]]:
        return [
            {"name": t.name, "description": t.description} for t in self.tools.values()
        ]


class UserExecutor:
    """
    The User Executor Agent.
    In Phase 2, this uses a simulated 'brain' (heuristic or scripted)
    instead of a full LLM to demonstrate the loop.
    """

    def __init__(self, scenario: Scenario, recorder: TraceRecorder, repo_root):
        self.scenario = scenario
        self.recorder = recorder
        self.toolbox = Toolbox(repo_root)
        self.max_steps = 10

    def run(self):
        self.recorder.log_event(
            "system", "user_executor", metadata={"msg": "Agent starting"}
        )

        # 1. Understand Goal (Simulated)
        goal = self.scenario.goal
        self.recorder.log_event(
            "thought",
            "user_executor",
            metadata={"thought": f"I need to achieve: {goal}"},
        )

        # 2. Planning (Simulated)
        # For Phase 2, we look at the 'queries' in the scenario to drive behavior
        # This acts as a "Scripted Agent"
        queries = []
        if "base" in self.scenario.queries:
            queries.append(self.scenario.queries["base"])
        if "variants" in self.scenario.queries:
            variants = self.scenario.queries["variants"]
            if isinstance(variants, list):
                queries.extend(variants)

        # If no explicit queries, we might try to infer from goal (future LLM work)
        if not queries:
            self.recorder.log_event(
                "thought",
                "user_executor",
                metadata={
                    "thought": "No explicit queries found in scenario. I am confused."
                },
            )
            return

        # 3. Execution Loop
        for q in queries:
            self._step_search(q)

        self.recorder.log_event(
            "system", "user_executor", metadata={"msg": "Agent finished"}
        )

    def _step_search(self, query: str):
        tool_name = "rag_search"
        tool = self.toolbox.get(tool_name)

        if not tool:
            self.recorder.log_event(
                "error",
                "user_executor",
                metadata={"msg": f"Tool {tool_name} not found"},
            )
            return

        self.recorder.log_event(
            "thought",
            "user_executor",
            metadata={"thought": f"I will search for '{query}'"},
        )

        # Log Call
        self.recorder.log_event(
            "tool_call", "user_executor", tool_name=tool_name, args={"query": query}
        )

        start_time = time.time()
        try:
            # Execute
            result = tool(query=query, limit=100)
            duration = (time.time() - start_time) * 1000

            # Serialize result (assuming it has to_dict or similar, or is a dataclass)
            if hasattr(result, "to_dict"):
                res_data = result.to_dict()
            else:
                res_data = str(result)

            # Log Result
            items = res_data.get("items", []) if isinstance(res_data, dict) else []

            # Extract IDs/Paths for metamorphic checks (e.g. Jaccard)
            item_ids = []
            for item in items:
                if isinstance(item, dict):
                    # Try common fields: path, id, file
                    val = item.get("path") or item.get("id") or item.get("file")
                    if val:
                        item_ids.append(str(val))
                else:
                    item_ids.append(str(item))

            summary = {
                "hit_count": len(items),
                "truncated": (
                    res_data.get("truncated", False)
                    if isinstance(res_data, dict)
                    else False
                ),
                "item_ids": item_ids,
            }

            self.recorder.log_event(
                "tool_result",
                "user_executor",
                tool_name=tool_name,
                result_summary=summary,
                latency_ms=duration,
                success=True,
            )

        except Exception as e:
            duration = (time.time() - start_time) * 1000
            self.recorder.log_event(
                "tool_result",
                "user_executor",
                tool_name=tool_name,
                result_summary={"error": str(e)},
                latency_ms=duration,
                success=False,
            )
