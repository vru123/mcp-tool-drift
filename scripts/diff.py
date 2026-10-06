"""Diff consecutive successfully-probed releases per server. Writes data/derived/changes.csv (one row per
change), data/derived/pairs.csv (one row per release pair) and data/derived/summary.json.
Every change gets a PROPOSED code for human review (column proposed_code)."""
import json, glob, os, re, csv, difflib
from common import load_snapshot
from collections import defaultdict
os.makedirs('data/derived',exist_ok=True)
cfg={s['id']:s for s in json.load(open('servers.json'))['servers']}
rel=json.load(open('data/meta/releases.json'))
HINTS=['readOnlyHint','destructiveHint','idempotentHint','openWorldHint']
DEFAULT={'readOnlyHint':False,'destructiveHint':True,'idempotentHint':False,'openWorldHint':True}  # MCP spec defaults
def vkey(v): return [int(x) for x in re.findall(r'\d+',v)]
def version_signal(a,b,calver):
    if calver: return 'calver (no semantic signal)'
    A,B=vkey(a),vkey(b)
    if B[0]>A[0]: return 'major'
    if B[0]==0 and B[1]>A[1]: return 'minor on 0.x (breaking by convention)'
    if B[1]>A[1]: return 'minor'
    return 'patch'
def strip(o,keys):
    if isinstance(o,dict): return {k:strip(v,keys) for k,v in o.items() if k not in keys}
    if isinstance(o,list): return [strip(x,keys) for x in o]
    return o
def canon(o): return json.dumps(o,sort_keys=True)
def norm_text(s): return re.sub(r'[\W_]+',' ',(s or '').lower()).strip()
def props(schema): return set(((schema or {}).get('properties') or {}).keys())
def schema_change(a,b):
    """returns list of (subtype, detail)"""
    out=[]
    pa,pb=props(a),props(b)
    if pb-pa: out.append(('SCHEMA_PARAM_ADDED',','.join(sorted(pb-pa))))
    if pa-pb: out.append(('SCHEMA_PARAM_REMOVED',','.join(sorted(pa-pb))))
    ra,rb=set((a or {}).get('required') or []),set((b or {}).get('required') or [])
    if ra!=rb and not out: out.append(('SCHEMA_REQUIRED_CHANGED',f"+{sorted(rb-ra)} -{sorted(ra-rb)}"))
    if out: return out
    noise={'$schema','additionalProperties'}
    if canon(strip(a,noise|{'description','title'}))!=canon(strip(b,noise|{'description','title'})):
        return [('SCHEMA_CONSTRAINT','types/enums/defaults/limits changed')]
    if canon(strip(a,noise))!=canon(strip(b,noise)):
        return [('SCHEMA_PARAM_DOC','parameter descriptions only')]
    if canon(a)!=canon(b): return [('SCHEMA_SERIALIZATION','$schema/additionalProperties only')]
    return []
RISKY=re.compile(r'\b(delete|remove|overwrite|destroy|drop|execute|exec|run|write|create|update|modify|move|deploy|send|payment|refund|charge|any file|all files|arbitrary|shell|command|sql)\b',re.I)
def desc_change(a,b):
    if (a or '')==(b or ''): return []
    if norm_text(a)==norm_text(b): return [('DESC_FORMAT','whitespace/punctuation only')]
    na,nb=set(RISKY.findall(a or '')), set(RISKY.findall(b or ''))
    added={x.lower() for x in nb}-{x.lower() for x in na}
    r=difflib.SequenceMatcher(None,a or '',b or '').ratio()
    if added: return [('DESC_SCOPE_CANDIDATE',f"new action words: {','.join(sorted(added))}; similarity {r:.2f}")]
    return [('DESC_REWORD',f'similarity {r:.2f}')]
def eff(ann):
    ann=ann or {}
    return {h:(ann[h] if h in ann and ann[h] is not None else DEFAULT[h]) for h in HINTS}, {h for h in HINTS if h in ann and ann[h] is not None}
def hint_change(a,b):
    """Effective hint = declared value, else the MCP spec default. Three kinds of effective change:
    HINT_FLIP (declared in both releases, value changed), HINT_INTRODUCED (newly declared, differs from default),
    HINT_WITHDRAWN (declaration dropped, falls back to a different default)."""
    out=[]
    ea,da=eff(a); eb,db=eff(b)
    for h in HINTS:
        if ea[h]!=eb[h]:
            riskier=(h=='destructiveHint' and eb[h]) or (h=='readOnlyHint' and not eb[h]) or (h=='openWorldHint' and eb[h]) or (h=='idempotentHint' and not eb[h])
            kind='HINT_FLIP' if (h in da and h in db) else ('HINT_INTRODUCED' if h in db else 'HINT_WITHDRAWN')
            out.append((kind,f"{h}: {ea[h]}->{eb[h]} ({'riskier' if riskier else 'safer'})"))
        elif (h in da)!=(h in db):
            out.append(('HINT_DECLARED_SAME_VALUE',f"{h}: {'declared' if h in db else 'undeclared'} at default value {eb[h]}"))
    return out
# proposed codes (for review) and governance route from the draft's routing rule
CODE={'TOOL_ADDED':('C4 new tool','hold'),'TOOL_REMOVED':('C5 tool removed','log'),
 'HINT_FLIP':('C3a risk-hint flip','hold'),'HINT_INTRODUCED':('C3b risk hint introduced','hold'),'HINT_WITHDRAWN':('C3c risk hint withdrawn','hold'),'HINT_DECLARED_SAME_VALUE':('C1 cosmetic','log'),
 'SCHEMA_PARAM_ADDED':('C2 capability expansion','hold'),'SCHEMA_PARAM_REMOVED':('C5 capability removed','log'),
 'SCHEMA_REQUIRED_CHANGED':('C2b contract change','hold'),'SCHEMA_CONSTRAINT':('C2b contract change','hold'),
 'SCHEMA_PARAM_DOC':('C1 cosmetic','log'),'SCHEMA_SERIALIZATION':('C0 serialization noise','log'),
 'DESC_FORMAT':('C0 serialization noise','log'),'DESC_REWORD':('C1 cosmetic (review)','log'),
 'DESC_SCOPE_CANDIDATE':('C2? scope change candidate (review)','review')}
rows=[];pairs=[]
for sid,r in rel.items():
    calver=r['registry']=='pypi' or sid in('filesystem','memory','everything','sequential-thinking')
    snaps=[]
    for s in r['selected']:
        d=load_snapshot(sid,s['version'])
        if d and d['status']=='ok': snaps.append(d)
    for A,B in zip(snaps,snaps[1:]):
        ta={t['name']:t for t in A['tools']}; tb={t['name']:t for t in B['tools']}
        ch=[]
        for n in sorted(set(tb)-set(ta)): ch.append((n,'TOOL_ADDED',''))
        for n in sorted(set(ta)-set(tb)): ch.append((n,'TOOL_REMOVED',''))
        for n in sorted(set(ta)&set(tb)):
            a,b=ta[n],tb[n]
            for t,dt in desc_change(a.get('description'),b.get('description')): ch.append((n,t,dt))
            for t,dt in schema_change(a.get('inputSchema'),b.get('inputSchema')): ch.append((n,t,dt))
            for t,dt in hint_change(a.get('annotations'),b.get('annotations')): ch.append((n,t,dt))
        vs=version_signal(A['version'],B['version'],calver)
        real=[c for c in ch if CODE[c[1]][0][:2] not in('C0',)]
        pairs.append({'server':sid,'group':cfg[sid]['group'],'from':A['version'],'to':B['version'],'from_date':A['published'][:10],'to_date':B['published'][:10],
            'tools_from':len(ta),'tools_to':len(tb),'version_signal':vs,'n_changes':len(ch),'n_substantive':len(real),
            'n_hold':sum(CODE[c[1]][1]=='hold' for c in ch),'n_hint_flips':sum(c[1]=='HINT_FLIP' for c in ch),'n_hint_flips_riskier':sum(c[1]=='HINT_FLIP' and 'riskier' in c[2] for c in ch),
            'n_hint_introduced':sum(c[1]=='HINT_INTRODUCED' for c in ch),'n_hint_withdrawn':sum(c[1]=='HINT_WITHDRAWN' for c in ch),
            'n_capability':sum(c[1] in('TOOL_ADDED','SCHEMA_PARAM_ADDED') for c in ch),
            'n_tools_added':sum(c[1]=='TOOL_ADDED' for c in ch),'n_tools_removed':sum(c[1]=='TOOL_REMOVED' for c in ch)})
        for n,t,dt in ch:
            rows.append({'server':sid,'from':A['version'],'to':B['version'],'to_date':B['published'][:10],'tool':n,'change_type':t,'detail':dt,
                         'proposed_code':CODE[t][0],'proposed_route':CODE[t][1],'version_signal':vs,'reviewer_code':'','reviewer_note':''})
with open('data/derived/changes.csv','w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
with open('data/derived/pairs.csv','w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(pairs[0])); w.writeheader(); w.writerows(pairs)
print('pairs',len(pairs),'changes',len(rows))
