"""Headline numbers from data/derived/changes.csv (after manual review merge). Writes data/derived/summary.json
and data/derived/timeline.csv (one row per sampled release, for the chart)."""
import csv, json, collections
from common import load_snapshot
R=list(csv.DictReader(open('data/derived/changes.csv'))); P=list(csv.DictReader(open('data/derived/pairs.csv')))
by=collections.defaultdict(list)
for r in R: by[(r['server'],r['from'],r['to'])].append(r)
def cls(rows):
    if any(r['proposed_route']=='hold' for r in rows): return 'hold'
    if any(r['proposed_route']=='review' for r in rows): return 'review'
    if any(not r['proposed_code'].startswith('C0') for r in rows): return 'log'
    if rows: return 'noise'
    return 'none'
pairs=[]
for p in P:
    rows=by[(p['server'],p['from'],p['to'])]
    p['class']=cls(rows); p['riskier_flip']=any(r['change_type']=='HINT_FLIP' and 'riskier' in r['detail'] for r in rows)
    p['cap']=any(r['proposed_code'].startswith('C2 ') for r in rows) or any(r['change_type'] in('TOOL_ADDED','SCHEMA_PARAM_ADDED') for r in rows)
    pairs.append(p)
n=len(pairs); C=collections.Counter(p['class'] for p in pairs)
sig=lambda s: 'major' if s=='major' or s.startswith('minor on 0.x') else ('calver' if s.startswith('calver') else 'minor/patch')
hold=[p for p in pairs if p['class']=='hold']
xt=collections.Counter(sig(p['version_signal']) for p in hold)
servers_hold=sorted({p['server'] for p in hold})
flips=[r for r in R if r['change_type']=='HINT_FLIP']
S={'releases_selected':181,'releases_probed_ok':172,'release_pairs':n,'pair_class_counts':dict(C),
   'pairs_substantive':C['hold']+C['log']+C['review'],'pairs_hold':C['hold'],
   'servers':20,'servers_with_hold_change':len(servers_hold),'servers_without_hold_change':sorted({p['server'] for p in pairs}-set(servers_hold)),
   'hold_pairs_by_version_signal':dict(xt),
   'hint_flips':len(flips),'hint_flips_riskier':sum('riskier' in r['detail'] for r in flips),'hint_flip_servers':sorted({r['server'] for r in flips}),
   'hint_introduced':sum(r['change_type']=='HINT_INTRODUCED' for r in R),
   'pairs_with_capability_expansion':sum(p['cap'] for p in pairs),
   'code_counts':dict(collections.Counter(r['proposed_code'] for r in R))}
json.dump(S,open('data/derived/summary.json','w'),indent=1); print(json.dumps(S,indent=1))
rel=json.load(open('data/meta/releases.json'))
cl={(p['server'],p['to']):p for p in pairs}
with open('data/derived/timeline.csv','w',newline='') as f:
    w=csv.writer(f); w.writerow(['server','group','version','date','status','class','riskier_flip'])
    grp={s['id']:s['group'] for s in json.load(open('servers.json'))['servers']}
    for sid,r in rel.items():
        first=True
        for s in r['selected']:
            d=load_snapshot(sid,s['version'])
            if d['status']!='ok': w.writerow([sid,grp[sid],s['version'],s['published'][:10],'failed','',''] ); continue
            p=cl.get((sid,s['version']))
            w.writerow([sid,grp[sid],s['version'],s['published'][:10],'ok','baseline' if first else p['class'],int(p['riskier_flip']) if p else 0]); first=False
