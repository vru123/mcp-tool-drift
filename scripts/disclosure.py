"""For every change routed 'hold', check whether public release notes for the releases in the interval
(from, to] mention it. Generous matching: the tool name anywhere in the notes counts; for risk-hint changes
any of annotation/hint/readOnly/destructive/idempotent/openWorld also counts. Writes data/derived/disclosure.csv
and data/derived/disclosure_summary.json."""
import csv, json, re, collections
def vt(v): return tuple(int(x) for x in re.findall(r'\d+',v))
R=list(csv.DictReader(open('data/derived/changes.csv')))
notes={}
def span(sid,a,b):
    if sid not in notes: notes[sid]=json.load(open(f'data/notes/{sid}.json'))
    n=notes[sid]; A,B=vt(a),vt(b)
    vs=[v for v in n if v[0].isdigit() and A<vt(v)<=B and n[v]['text'].strip()]
    return vs,' '.join(n[v]['text'] for v in vs)
HINTKW=re.compile(r'annotation|hint|read-?only|destructive|idempoten|open-?world',re.I)
out=[]
for r in R:
    if r['proposed_route']!='hold': continue
    vs,txt=span(r['server'],r['from'],r['to'])
    if not vs: status='no notes published'
    else:
        t=r['tool']; pats=[re.escape(t),re.escape(t.replace('_',' ')),re.escape(t.replace('_','-'))]
        named=any(re.search(p,txt,re.I) for p in pats)
        hint=r['change_type'].startswith('HINT') and bool(HINTKW.search(txt))
        status='tool named' if named else ('hints mentioned generally' if hint else 'not mentioned')
    out.append({**{k:r[k] for k in('server','from','to','tool','change_type','detail','proposed_code','version_signal')},
                'notes_versions':' '.join(vs),'disclosure':status})
OV=json.load(open('data/meta/disclosure_overrides.json'))
for o in out:
    o['manual_note']=''
    for v in OV:
        if o['server']==v['server'] and o['tool']==v['tool'] and o['change_type']==v.get('change_type',o['change_type']):
            if 'disclosure' in v: o['disclosure']=v['disclosure']
            o['manual_note']=v['note']
with open('data/derived/disclosure.csv','w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(out[0])); w.writeheader(); w.writerows(out)
C=collections.Counter(o['disclosure'] for o in out)
pairs=collections.defaultdict(list)
for o in out: pairs[(o['server'],o['from'],o['to'])].append(o['disclosure'])
def pc(ds):
    if all(d=='no notes published' for d in ds): return 'no notes'
    m=sum(d in('tool named','hints mentioned generally') for d in ds)
    return 'all mentioned' if m==len(ds) else ('some mentioned' if m else 'none mentioned')
# note: counts above are computed after overrides because 'out' was updated in place
P=collections.Counter(pc(v) for v in pairs.values())
key=[o for o in out if o['change_type']=='HINT_FLIP' or '(manual)' in o['proposed_code']]
flips=[o for o in out if o['change_type']=='HINT_FLIP']
S={'hint_flip_disclosure':dict(collections.Counter(o['disclosure'] for o in flips)),'hold_changes':len(out),'hold_change_disclosure':dict(C),'hold_pairs':len(pairs),'hold_pair_disclosure':dict(P),
   'by_server':{s:dict(collections.Counter(o['disclosure'] for o in out if o['server']==s)) for s in sorted({o['server'] for o in out})},
   'key_changes':[{k:o[k] for k in('server','from','to','tool','detail','notes_versions','disclosure')} for o in key]}
json.dump(S,open('data/derived/disclosure_summary.json','w'),indent=1); print(json.dumps(S,indent=1)[:6000])
