#!/usr/bin/env python3
import argparse, json, os, re, sys, hashlib, time
from pathlib import Path

LOG = ".llmc/logs/contracts_build.jsonl"
TOOLS_MANIFEST = Path(".codex/tools.json")

SEC = {
  "roles": re.compile(r"^##\s*Roles\b", re.I|re.M),
  "flows": re.compile(r"^##\s*Workflows?\b", re.I|re.M),
  "pol":   re.compile(r"^##\s*Policies\b", re.I|re.M),
  "gloss": re.compile(r"^##\s*Glossary\b", re.I|re.M),
}
H3   = re.compile(r"^###\s*([A-Za-z0-9_.-]+)\s*$", re.M)
BUL  = re.compile(r"^\s*-\s*([A-Za-z0-9_]+)\s*:\s*(.+)\s*$")
CODE = re.compile(r"```(json)?\s*\n(.*?)\n```", re.S)

IDENT_PATS = [
  r"`([^`]+)`",                            # inline code
  r"\b[A-Z0-9_]{3,}\b",                    # ENV/CONSTANTS
  r"[A-Za-z0-9_\-./]+?\.[A-Za-z0-9]{1,6}\b",  # filenames
  r"(?:/[\w\-./]{1,})"                     # paths
]

def _log(obj):
  os.makedirs(os.path.dirname(LOG), exist_ok=True)
  with open(LOG,"a", encoding="utf-8") as f: f.write(json.dumps(obj)+"\n")

def _spans(text):
  pos={}
  for k,rx in SEC.items():
    m=rx.search(text)
    if m: pos[k]=m.start()
  order=sorted(pos.items(), key=lambda kv: kv[1])
  spans={}
  for i,(k,start) in enumerate(order):
    end=len(text) if i==len(order)-1 else order[i+1][1]
    spans[k]=text[start:end]
  return spans

def _items(block):
  items=[]
  for m in H3.finditer(block):
    _id=m.group(1).strip()
    start=m.end(); nxt=H3.search(block,start)
    sub=block[start:(nxt.start() if nxt else len(block))]
    cm=CODE.search(sub)
    if cm and cm.group(1) == "json":
      try:
        data=json.loads(cm.group(2)); data["id"]=_id; items.append(data); continue
      except Exception:
        pass
    obj={"id":_id}
    for line in sub.splitlines():
      b=BUL.match(line)
      if b:
        k=b.group(1).lower(); v=b.group(2).strip()
        if "," in v and k not in ("sc","rule"):
          obj[k]=[x.strip() for x in v.split(",") if x.strip()]
        else:
          obj[k]=v
    items.append(obj)
  if items: return items
  # fallback: bullet "id: value"
  for line in block.splitlines():
    b=BUL.match(line)
    if b: items.append({"id":b.group(1), "sc":b.group(2)})
  return items

def _idents(text):
  s=set()
  for pat in IDENT_PATS:
    for m in re.findall(pat, text):
      if isinstance(m, tuple): m=m[0]
      if len(m)>=3: s.add(m.strip())
  return sorted(s)

def _stable(obj): return json.dumps(obj, ensure_ascii=False, separators=(",",":"), sort_keys=True)

def _load_llm_tools(manifest_path: Path):
  if not manifest_path.exists():
    return [], None
  try:
    data = json.load(open(manifest_path, "r", encoding="utf-8"))
  except Exception:
    return [], str(manifest_path)
  llm_tools = []
  S = lambda o,k,d=None: o.get(k,d)
  for entry in data.get("llm_tools", []):
    tool_id = S(entry, "id", "").strip()
    if not tool_id:
      continue
    schema = S(entry, "parameters", {}) or {}
    record = {
      "id": tool_id,
      "in": schema,
    }
    desc = S(entry, "description", "").strip()
    if desc:
      record["description"] = desc
    if "returns" in entry:
      record["out"] = entry["returns"]
    if "cost" in entry:
      record["cost"] = entry["cost"]
    if "strict" in entry:
      record["strict"] = bool(entry["strict"])
    llm_tools.append(record)
  return llm_tools, str(manifest_path)

def main():
  ap=argparse.ArgumentParser()
  ap.add_argument("--in","--inp","-i",dest="inp", default="CONTRACTS.md")
  ap.add_argument("--out","-o", default="contracts.min.json")
  ap.add_argument("--version", type=int, default=1)
  a=ap.parse_args()

  text=open(a.inp,"r",encoding="utf-8",errors="ignore").read()
  spans=_spans(text)
  roles=_items(spans.get("roles",""))
  flows=_items(spans.get("flows",""))
  pol  =_items(spans.get("pol",""))
  gloss=_items(spans.get("gloss",""))
  idents=_idents(text)
  manifest_tools, manifest_path = _load_llm_tools(TOOLS_MANIFEST)

  S=lambda o,k,d: o.get(k,d)
  sidecar={
    "v": a.version,
    "roles": sorted([{"id":S(r,"id",""),"sc":S(r,"sc",""),"cap":S(r,"cap",[]),"lim":S(r,"lim",[])} for r in roles], key=lambda x:x["id"]),
    "flows": sorted([{"id":S(f,"id",""),"steps":S(f,"steps",[]),**({"ent":f["ent"]} if "ent" in f else {}),**({"ok":f["ok"]} if "ok" in f else {})} for f in flows], key=lambda x:x["id"]),
    "pol":   sorted([{"id":S(p,"id",""),"rule":S(p,"rule",""),"sev":int(S(p,"sev",1) or 1)} for p in pol], key=lambda x:x["id"]),
    "gloss": sorted([{"term":S(g,"term",S(g,"id","")),"canon":S(g,"canon",""),"aka":S(g,"aka",[])} for g in gloss], key=lambda x:x["term"]),
    "idents": idents
  }
  sidecar["tools"] = sorted(manifest_tools, key=lambda x: x["id"]) if manifest_tools else []
  if manifest_path:
    sidecar["tool_manifest"] = manifest_path
    if manifest_path not in sidecar["idents"]:
      sidecar["idents"].append(manifest_path)

  out_json=_stable(sidecar)
  os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
  with open(a.out,"w",encoding="utf-8") as f: f.write(out_json)
  h=hashlib.sha256(out_json.encode("utf-8")).hexdigest()
  with open("contracts.sidecar.sha256","w") as f: f.write(h+"\n")

  os.makedirs(".llmc/logs", exist_ok=True)
  _log({"ts":int(time.time()),"out":a.out,"sha256":h,"roles":len(sidecar["roles"]),"tools":len(sidecar["tools"]),"flows":len(sidecar["flows"]),"idents":len(sidecar["idents"])})
  print(a.out)
if __name__=="__main__":
  main()
