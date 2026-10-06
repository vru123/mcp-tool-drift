"""Load probe snapshots from either per-release files (written by run_batch.py) or the per-server
bundles committed to the repo (data/raw/<server>.json, written by bundle_raw.py)."""
import json, os
_bundles = {}
def load_snapshot(sid, ver):
    p = f'data/raw/{sid}/{ver}.json'
    if os.path.exists(p):
        return json.load(open(p))
    b = f'data/raw/{sid}.json'
    if os.path.exists(b):
        if sid not in _bundles:
            _bundles[sid] = {r['version']: r for r in json.load(open(b))}
        return _bundles[sid].get(ver)
    return None
