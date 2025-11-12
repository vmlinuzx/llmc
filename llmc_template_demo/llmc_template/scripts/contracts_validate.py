#!/usr/bin/env python3
import json, sys, hashlib, os, time
LOG = '.llmc/logs/contracts_validate.jsonl'
def main():
    side='contracts.min.json'; sha_file='contracts.sidecar.sha256'
    if not os.path.exists(side):
        print('contracts.min.json missing', file=sys.stderr); sys.exit(2)
    raw=open(side,'rb').read(); sha=hashlib.sha256(raw).hexdigest()
    expected=open(sha_file,'r').read().strip() if os.path.exists(sha_file) else ''
    ok=(sha==expected if expected else True)
    os.makedirs('.llmc/logs', exist_ok=True)
    open(LOG,'a',encoding='utf-8').write(json.dumps({'ts':int(time.time()),'sha':sha,'expected':(expected or None),'ok':ok})+'\\n')
    if not ok:
        print('Sidecar checksum drift: rebuild required', file=sys.stderr); sys.exit(3)
    print('OK', sha)
if __name__=='__main__':
    main()
