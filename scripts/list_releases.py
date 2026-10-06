"""Pick up to N stable releases per server between window_start and today, evenly spread
(first and last always included). Writes data/meta/releases.json"""
import json, re, subprocess, urllib.request, datetime as dt
N=10
cfg=json.load(open('servers.json'))
start=cfg['window_start']; today=dt.date.today().isoformat()
STABLE_NPM=re.compile(r'^\d+\.\d+\.\d+$')
def npm_times(pkg):
    out=subprocess.run(['npm','view',pkg,'time','--json'],capture_output=True,text=True,timeout=60).stdout
    t=json.loads(out)
    # 'time' keeps entries for unpublished versions; keep only versions still installable
    live=set(json.loads(subprocess.run(['npm','view',pkg,'versions','--json'],capture_output=True,text=True,timeout=60).stdout))
    return {v:d for v,d in t.items() if v in live and STABLE_NPM.match(v)}
def pypi_times(pkg):
    j=json.load(urllib.request.urlopen(f'https://pypi.org/pypi/{pkg}/json',timeout=60))
    res={}
    for v,files in j['releases'].items():
        if not files or not re.match(r'^\d+(\.\d+)*$',v): continue
        if all(f.get('yanked') for f in files): continue
        res[v]=min(f['upload_time_iso_8601'] for f in files)
    return res
def spread(items,n):
    if len(items)<=n: return items
    idx=sorted({round(i*(len(items)-1)/(n-1)) for i in range(n)})
    return [items[i] for i in idx]
out={}
for s in cfg['servers']:
    t=npm_times(s['pkg']) if s['registry']=='npm' else pypi_times(s['pkg'])
    inwin=sorted([(d,v) for v,d in t.items() if start<=d[:10]<=today])
    pick=spread(inwin,N)
    out[s['id']]={'pkg':s['pkg'],'registry':s['registry'],'n_in_window':len(inwin),
                  'selected':[{'version':v,'published':d} for d,v in pick]}
    print(f"{s['id']:20s} in-window={len(inwin):4d} selected={len(pick)} {pick[0][1] if pick else '-'} .. {pick[-1][1] if pick else '-'}",flush=True)
json.dump(out,open('data/meta/releases.json','w'),indent=1)
