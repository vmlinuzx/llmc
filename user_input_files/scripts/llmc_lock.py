#!/usr/bin/env python3
import argparse, json, os, sys, time, hashlib, pathlib
LOCK_ROOT = ".llmc/locks"

def _now(): return int(time.time())
def _res_key(p):
    return hashlib.sha1(p.encode("utf-8")).hexdigest()

def _lock_path(resource):
    os.makedirs(LOCK_ROOT, exist_ok=True)
    return os.path.join(LOCK_ROOT, _res_key(resource) + ".json")

def read_lock(path):
    if not os.path.exists(path): return None
    with open(path, "r") as f:
        try: return json.load(f)
        except: return None

def write_lock(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w") as f: json.dump(data, f)
    os.replace(tmp, path)

def acquire(args):
    res = args.resource
    tid = args.task_id
    ttl = int(args.ttl)
    started = int(args.started_at or _now())
    path = _lock_path(res)
    cur = read_lock(path)
    now = _now()
    if cur and cur.get("expires_at",0) < now:
        cur = None

    if not cur:
        write_lock(path, {"resource":res,"owner":tid,"started_at":started,"expires_at":now+ttl,"wounded":False})
        print(json.dumps({"status":"ACQUIRED","resource":res})); return 0

    owner = cur["owner"]; owner_started = cur.get("started_at", now)
    if owner == tid:
        cur["expires_at"] = now + ttl
        write_lock(path, cur)
        print(json.dumps({"status":"RENEWED","resource":res})); return 0

    # wound-wait-lite
    if started < owner_started:
        cur["wounded"] = True
        write_lock(path, cur)
        print(json.dumps({"status":"WOUNDED","resource":res,"owner":owner})); return 2
    else:
        wait_ms = int(os.getenv("LOCK_BACKOFF_MS","750"))
        print(json.dumps({"status":"WAIT","resource":res,"owner":owner,"sleep_ms":wait_ms})); return 1

def release(args):
    res = args.resource
    tid = args.task_id
    path = _lock_path(res)
    cur = read_lock(path)
    if not cur:
        print(json.dumps({"status":"NOLOCK","resource":res})); return 0
    if cur["owner"] != tid:
        print(json.dumps({"status":"NOT_OWNER","resource":res,"owner":cur['owner']})); return 3
    try:
        os.remove(path)
        print(json.dumps({"status":"RELEASED","resource":res})); return 0
    except:
        print(json.dumps({"status":"ERROR","resource":res})); return 4

def ls(_):
    os.makedirs(LOCK_ROOT, exist_ok=True)
    out=[]
    for f in pathlib.Path(LOCK_ROOT).glob("*.json"):
        try:
            out.append(json.load(open(f)))
        except Exception:
            pass
    print(json.dumps(out, indent=2)); return 0

def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    ac = sub.add_parser("acquire"); ac.add_argument("--resource",required=True); ac.add_argument("--task-id",required=True); ac.add_argument("--ttl",required=True); ac.add_argument("--started-at")
    rl = sub.add_parser("release"); rl.add_argument("--resource",required=True); rl.add_argument("--task-id",required=True)
    sub.add_parser("ls")
    args = ap.parse_args()
    if args.cmd=="acquire": sys.exit(acquire(args))
    if args.cmd=="release": sys.exit(release(args))
    if args.cmd=="ls": sys.exit(ls(args))
if __name__=="__main__": main()
