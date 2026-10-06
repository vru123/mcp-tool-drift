#!/bin/sh
# Full pipeline. Run from the repo root. Requires Node 20+, npm, Python 3.11+, uv.
#   ./scripts/run_all.sh            -> analysis only, from the committed snapshots in data/raw/<server>.json
#   ./scripts/run_all.sh --resweep  -> re-probe every release first (about 15-20 minutes)
set -e
if [ "$1" = "--resweep" ]; then
  mkdir -p /tmp/mcpsandbox
  [ -d /tmp/mcpsandbox/repo ] || (git init -q /tmp/mcpsandbox/repo && git -C /tmp/mcpsandbox/repo -c user.email=a@b -c user.name=probe commit -q --allow-empty -m init)
  cp scripts/fixtures/kubeconfig /tmp/mcpsandbox/kubeconfig
  # releases.json is committed so the sample is fixed; run scripts/list_releases.py only to draw a new sample
  until python3 scripts/run_batch.py --budget 600 | tee /dev/stderr | grep -q "remaining=0"; do :; done
  python3 scripts/bundle_raw.py
fi
python3 scripts/diff.py
python3 scripts/apply_review.py
python3 scripts/summarize.py > /dev/null
[ -f data/notes/filesystem.json ] || python3 scripts/fetch_notes.py
python3 scripts/disclosure.py > /dev/null
echo "Done. See data/derived/summary.json and data/derived/disclosure_summary.json"
