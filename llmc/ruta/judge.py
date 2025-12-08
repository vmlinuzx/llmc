import json
from pathlib import Path
from typing import Any

from simpleeval import simple_eval, EvalWithCompoundTypes

from llmc.ruta.types import Scenario, TraceEvent


def _safe_eval(expr: str, context: dict) -> Any:
    """
    Safely evaluate an expression using simpleeval.
    
    This replaces Python's eval() to prevent arbitrary code execution.
    Only allows basic operations, comparisons, and pre-defined functions.
    
    SECURITY: This is the fix for VULN-002 (RUTA eval injection).
    """
    evaluator = EvalWithCompoundTypes(
        names=context,
        functions={
            # Whitelist only safe functions
            "len": len,
            "min": min,
            "max": max,
            "abs": abs,
            "sum": sum,
            "round": round,
        }
    )
    return evaluator.eval(expr)


class Judge:
    """
    Evaluates a RUTA run based on the scenario expectations and the generated trace.
    """
    def __init__(self, scenario: Scenario, trace_path: Path):
        self.scenario = scenario
        self.trace_path = trace_path
        self.incidents = []
        self.metrics = {}

    def evaluate(self) -> dict[str, Any]:
        trace_events = self._load_trace()
        
        # Calculate basic metrics
        tool_calls = [e for e in trace_events if e["event"] == "tool_call"]
        self.metrics["total_steps"] = len(trace_events)
        self.metrics["total_tool_calls"] = len(tool_calls)
        
        # Check Expectations
        self._check_tool_usage(trace_events)
        self._check_properties(trace_events)
        
        status = "FAIL" if self.incidents else "PASS"
        
        return {
            "run_id": trace_events[0]["run_id"] if trace_events else "unknown",
            "scenario_id": self.scenario.id,
            "status": status,
            "incidents": self.incidents,
            "metrics": self.metrics
        }

    def _load_trace(self) -> list[TraceEvent]:
        events = []
        if not self.trace_path.exists():
            return []
            
        with open(self.trace_path, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    events.append(json.loads(line))
        return events

    def _check_tool_usage(self, events: list[TraceEvent]):
        used_tools = set()
        for e in events:
            if e["event"] == "tool_call" and e.get("tool_name"):
                used_tools.add(e["tool_name"])
        
        # Must Use
        for tool in self.scenario.expectations.must_use_tools:
            if tool not in used_tools:
                self.incidents.append({
                    "id": f"INC-TOOL-MISSING-{tool}",
                    "severity": "P1",
                    "type": "TOOL_NOT_USED",
                    "summary": f"Required tool '{tool}' was not used.",
                    "details": {"required": tool, "used": list(used_tools)}
                })

        # Must Not Use
        for tool in self.scenario.expectations.must_not_use_tools:
            if tool in used_tools:
                self.incidents.append({
                    "id": f"INC-TOOL-FORBIDDEN-{tool}",
                    "severity": "P1",
                    "type": "TOOL_FORBIDDEN",
                    "summary": f"Forbidden tool '{tool}' was used.",
                    "details": {"forbidden": tool, "used": list(used_tools)}
                })

    def _check_properties(self, events: list[TraceEvent]):
        for prop in self.scenario.expectations.properties:
            if prop.type == "assertion":
                self._check_assertion(prop, events)
            elif prop.type == "metamorphic":
                self._check_metamorphic(prop, events)

    def _check_metamorphic(self, prop, events: list[TraceEvent]):
        # Helper functions for the DSL
        def get_results(query):
            results = []
            for i, e in enumerate(events):
                if e["event"] == "tool_call" and e.get("tool_name") == "rag_search":
                    q = e["args"].get("query")
                    if q == query:
                        # Find corresponding result
                        for j in range(i + 1, len(events)):
                            next_e = events[j]
                            if next_e["event"] == "tool_result" and next_e["tool_name"] == "rag_search":
                                results.append(next_e["result_summary"])
                                break
            return results

        def result_count(query):
            res = get_results(query)
            if not res:
                return 0
            # Return the count from the LAST execution of this query
            return res[-1].get("hit_count", 0)

        def results(query):
            res = get_results(query)
            if not res:
                return set()
            return set(res[-1].get("item_ids", []))

        def jaccard(s1, s2):
            if not s1 and not s2:
                return 1.0
            if not s1 or not s2:
                return 0.0
            return len(s1.intersection(s2)) / len(s1.union(s2))

        # Context for evaluation
        context = {
            "result_count": result_count,
            "results": results,
            "jaccard": jaccard
        }

        # 1. Evaluate Relation (Optional, but used for variable binding like 'jaccard')
        relation_val = None
        if prop.relation:
            try:
                # If relation starts with jaccard(, evaluate it and bind to 'jaccard' variable
                # This is a heuristic to support the specific YAML format
                if prop.relation.strip().startswith("jaccard("):
                     relation_val = _safe_eval(prop.relation, context)
                     context["jaccard"] = relation_val
            except Exception:
                # We don't fail here, we might fail in constraint if variable is missing
                pass

        # 2. Evaluate Constraint
        try:
            # Replace YAML operators with Python ones
            expr = prop.constraint.replace("AND", "and").replace("OR", "or")
            success = _safe_eval(expr, context)
            
            if not success:
                 self.incidents.append({
                    "id": f"INC-META-FAIL-{prop.name}",
                    "severity": self.scenario.severity_policy.property_failures.get(prop.name, "P2"),
                    "type": "METAMORPHIC_VIOLATION",
                    "summary": f"Metamorphic property '{prop.name}' failed.",
                    "details": {
                        "constraint": prop.constraint, 
                        "relation": prop.relation, 
                        "relation_val": relation_val
                    }
                })

        except Exception as e:
            self.incidents.append({
                "id": f"INC-META-ERROR-{prop.name}",
                "severity": "P1",
                "type": "METAMORPHIC_ERROR",
                "summary": f"Error evaluating constraint for '{prop.name}': {e}",
                "details": {"error": str(e)}
            })

    def _check_assertion(self, prop, events: list[TraceEvent]):
        # Simple assertion logic for Phase 3
        # Supported: "result.success == true"
        if prop.constraint == "result.success == true":
            # Check if all tool results were successful
            failures = []
            for e in events:
                if e["event"] == "tool_result" and e.get("success") is False:
                    failures.append(e)
            
            if failures:
                self.incidents.append({
                    "id": f"INC-PROP-{prop.name}",
                    "severity": self.scenario.severity_policy.property_failures.get(prop.name, "P2"),
                    "type": "PROPERTY_VIOLATION",
                    "summary": f"Property '{prop.name}' failed: Found {len(failures)} failed tool calls.",
                    "details": {"failures": failures[:3]} # Show first 3
                })
