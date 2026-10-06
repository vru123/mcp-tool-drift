"""Merge data/raw/<server>/<version>.json into one file per server, data/raw/<server>.json
(keeps the repo under GitHub's 100-files-per-web-upload limit). Per-release files are left in place."""
import json, glob, os
rel = json.load(open('data/meta/releases.json'))
for sid, r in rel.items():
    recs = [json.load(open(f"data/raw/{sid}/{s['version']}.json")) for s in r['selected'] if os.path.exists(f"data/raw/{sid}/{s['version']}.json")]
    json.dump(recs, open(f'data/raw/{sid}.json', 'w'), indent=1)
    print(sid, len(recs))
