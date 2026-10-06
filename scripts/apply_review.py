"""Merge the manual review of description changes (data/derived/scope_review.csv) into changes.csv."""
import csv
rev = {(r['server'], r['from'], r['to'], r['tool']): r for r in csv.DictReader(open('data/derived/scope_review.csv'))}
R = list(csv.DictReader(open('data/derived/changes.csv')))
route = {'C2': 'hold', 'C1': 'log', 'C1s': 'log'}
n = 0
for r in R:
    k = (r['server'], r['from'], r['to'], r['tool'])
    if k in rev and r['change_type'] in ('DESC_SCOPE_CANDIDATE', 'DESC_REWORD'):
        c = rev[k]['proposed_code']
        r['proposed_code'] = c + ' (manual)'; r['proposed_route'] = route[c.split()[0]]; r['reviewer_note'] = rev[k]['rationale']; n += 1
with open('data/derived/changes.csv', 'w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=list(R[0])); w.writeheader(); w.writerows(R)
print('merged', n, 'manual reviews')
