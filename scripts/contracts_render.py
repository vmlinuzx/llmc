#!/usr/bin/env python3
import argparse, json, sys
from pathlib import Path

MANIFEST_PATH = Path(".codex/tools.json")

def load(path):
    return json.load(open(path,'r',encoding='utf-8'))

def load_manifest_tools():
    if not MANIFEST_PATH.exists():
        return []
    try:
        data = json.load(open(MANIFEST_PATH, 'r', encoding='utf-8'))
    except Exception:
        return []
    return [t for t in data.get("llm_tools", []) if t.get("id")]

def pick(sc, sl):
    if sl=='all':
        return sc
    out={'v':sc.get('v',1)}
    parts=[p.strip() for p in sl.split(',') if p.strip()]
    for p in parts:
        if p.startswith('workflows:') or p.startswith('flows:'):
            wid=p.split(':',1)[1]
            out['flows']=[f for f in sc.get('flows',[]) if f.get('id')==wid]
        else:
            key={'roles':'roles','tools':'tools','pol':'pol','policies':'pol','gloss':'gloss','glossary':'gloss'}.get(p,p)
            if key in sc: out[key]=sc[key]
    return out

def as_text(vendor, slice_name, obj):
    head=f"@contracts:v{obj.get('v',1)};vendor={vendor};slice={slice_name}\n"
    body=json.dumps(obj, ensure_ascii=False, separators=(',',':'), sort_keys=True)
    return head+body

def _tool_schema(tool):
    params = tool.get("in") or tool.get("parameters") or {}
    desc = tool.get("description") or f"Contract tool {tool.get('id','')}"
    return params, desc

def oai_tools(tools):
    arr=[]
    for t in tools:
        params, desc = _tool_schema(t)
        arr.append({
            "type":"function",
            "function":{
                "name": t["id"],
                "description": desc,
                "parameters": params or {"type":"object","properties":{}}
            }
        })
    return {"tools":arr}

def claude_tools(tools):
    arr=[]
    for t in tools:
        params, desc = _tool_schema(t)
        arr.append({
            "name": t["id"],
            "description": desc,
            "input_schema": params or {"type":"object","properties":{}}
        })
    return {"tools":arr}

def gemini_tools(tools):
    arr=[]
    for t in tools:
        params, desc = _tool_schema(t)
        arr.append({
            "name": t["id"],
            "description": desc,
            "parameters": params or {"type":"object","properties":{}}
        })
    return {"tools":{"function_declarations":arr}}

def main():
    import os
    ap=argparse.ArgumentParser()
    ap.add_argument("--sidecar", default="contracts.min.json")
    ap.add_argument("--vendor", choices=["codex","claude","gemini"], default="codex")
    ap.add_argument("--slice", default="roles,tools")
    ap.add_argument("--format", choices=["text","json","tools"], default="text")
    a=ap.parse_args()

    exec_root = os.environ.get('LLMC_EXEC_ROOT', '.')
    sidecar_path = os.path.join(exec_root, a.sidecar)

    sc=load(sidecar_path)
    sl=pick(sc,a.slice)
    manifest_tools = load_manifest_tools()

    requested_parts = {p.strip() for p in a.slice.split(',')} if a.slice != 'all' else {'all'}
    if ('tools' in requested_parts or a.slice == 'all') and not sl.get("tools") and manifest_tools:
        sl = dict(sl)
        sl["tools"] = [
            {
                "id": t["id"],
                "description": t.get("description",""),
                "in": t.get("parameters",{}) or {}
            }
            for t in manifest_tools
        ]

    tools_slice = sl.get("tools") or [
        {
            "id": t["id"],
            "description": t.get("description",""),
            "in": t.get("parameters",{}) or {}
        }
        for t in manifest_tools
    ]

    if a.format=="text":
        sys.stdout.write(as_text(a.vendor, a.slice, sl)); return
    if a.format=="json":
        sys.stdout.write(json.dumps(sl, ensure_ascii=False, separators=(',',':'), sort_keys=True)); return

    tools=tools_slice
    if a.vendor=="codex":
        out=oai_tools(tools)
    elif a.vendor=="claude":
        out=claude_tools(tools)
    else:
        out=gemini_tools(tools)
    sys.stdout.write(json.dumps(out, ensure_ascii=False, separators=(',',':'), sort_keys=True))

if __name__=="__main__":
    main()