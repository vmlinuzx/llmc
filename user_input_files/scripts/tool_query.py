#!/usr/bin/env python3
import json, os, sys

MANIFEST_PATH = os.path.join(os.path.dirname(__file__), "..", ".codex", "tools.json")

def _load_manifest(path=MANIFEST_PATH):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def _all_tools(data):
    out = []
    for key in ("cli_tools", "llm_tools"):
        out.extend(data.get(key, []) or [])
    return out

def search_tools(query: str):
    q = (query or "").strip().lower()
    if not q:
        return []
    data = _load_manifest()
    results = []
    for t in _all_tools(data):
        tid = (t.get("id") or "").lower()
        name = (t.get("name") or "").lower()
        desc = (t.get("description") or "").lower()
        caps = ", ".join(t.get("capabilities", [])).lower()
        if any(q in field for field in (tid, name, desc, caps)):
            label = t.get("name") or t.get("id")
            blurb = t.get("description") or caps or ""
            results.append(f"{t.get('id')} — {label}: {blurb}".strip())
    return results

def describe_tool(name: str):
    target = (name or "").strip().lower()
    if not target:
        return "Tool name required."
    data = _load_manifest()
    for t in _all_tools(data):
        tid = (t.get("id") or "").lower()
        tname = (t.get("name") or "").lower()
        if target in (tid, tname):
            lines = []
            label = t.get("name") or t.get("id")
            lines.append(f"**{label}** (ID: `{t.get('id')}`)")
            if t.get("description"):
                lines.append(f"- Description: {t['description']}")
            if t.get("capabilities"):
                lines.append(f"- Capabilities: {', '.join(t['capabilities'])}")
            if t.get("min_version"):
                lines.append(f"- Minimum Version: {t['min_version']}")
            if t.get("usage"):
                lines.append(f"- Usage: {t['usage']}")
            return "\n".join(lines)
    return f"Tool '{name}' not found."

def _main(argv):
    if len(argv) < 3:
        print("Usage: tool_query.py <search|describe> <query or tool_name>")
        return 2
    mode = argv[1].lower()
    arg = " ".join(argv[2:])
    if mode == "search":
        matches = search_tools(arg)
        if matches:
            print(f"Tool search results for query: {arg}")
            for m in matches:
                print(f"- {m}")
        else:
            print(f"No tools found matching query: {arg}")
        return 0
    if mode == "describe":
        print(describe_tool(arg))
        return 0
    print("Invalid mode. Use 'search' or 'describe'.")
    return 2

if __name__ == "__main__":
    sys.exit(_main(sys.argv))

