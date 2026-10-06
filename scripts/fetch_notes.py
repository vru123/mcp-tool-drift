"""Collect public release notes per server version, from GitHub release pages (HTML, no API token)
and/or CHANGELOG.md files. Writes data/notes/<server>.json = {version: notes text}."""
import re, html, json, os, urllib.request, time
os.makedirs('data/notes',exist_ok=True)
SRC={
 'filesystem':('releases','modelcontextprotocol/servers',None),'memory':('releases','modelcontextprotocol/servers',None),
 'everything':('releases','modelcontextprotocol/servers',None),'sequential-thinking':('releases','modelcontextprotocol/servers',None),
 'fetch':('releases','modelcontextprotocol/servers',None),'git':('releases','modelcontextprotocol/servers',None),'time':('releases','modelcontextprotocol/servers',None),
 'azure':('changelog','https://raw.githubusercontent.com/microsoft/mcp/main/servers/Azure.Mcp.Server/CHANGELOG.md',None),
 'supabase':('changelog','https://raw.githubusercontent.com/supabase/mcp/main/packages/mcp-server-supabase/CHANGELOG.md',None),
 'kubernetes':('releases','Flux159/mcp-server-kubernetes',None),'notion':('releases','makenotion/notion-mcp-server',None),
 'hubspot':('none','closed source; no public repository or changelog found',None),
 'stripe':('releases','stripe/ai','mcp'),'figma':('changelog','https://raw.githubusercontent.com/GLips/Figma-Context-MCP/main/CHANGELOG.md',None),
 'sentry':('releases','getsentry/sentry-mcp',None),'heroku':('changelog','https://raw.githubusercontent.com/heroku/heroku-mcp-server/main/CHANGELOG.md',None),
 'playwright':('releases','microsoft/playwright-mcp',None),'firecrawl':('changelog','https://raw.githubusercontent.com/firecrawl/firecrawl-mcp-server/main/CHANGELOG.md',None),
 'browserbase':('releases','browserbase/mcp-server-browserbase',None),'context7':('changelog','https://raw.githubusercontent.com/upstash/context7/master/packages/mcp/CHANGELOG.md',None)}
def get(u):
    for i in range(3):
        try: return urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'tool-drift-study'}),timeout=60).read().decode('utf-8','replace')
        except Exception as e: err=e; time.sleep(3)
    raise err
VER=re.compile(r'(\d+\.\d+\.\d+)')
def releases(repo,filt):
    out={};cache={}
    for page in range(1,20):
        s=get(f'https://github.com/{repo}/releases?page={page}')
        secs=s.split('<section')[1:]
        if not secs: break
        oldest='9999'
        for x in secs:
            tags=re.findall(r'releases/tag/([^"]+)"',x); dts=re.findall(r'datetime="([^"]+)"',x)
            if not tags: continue
            tag=html.unescape(tags[0]); oldest=min(oldest,dts[0] if dts else '9999')
            if filt and filt not in tag.lower(): continue
            m=re.search(r'class="markdown-body[^"]*"[^>]*>(.*?)</div>\s*</div>',x,re.S)
            body=html.unescape(re.sub(r'\s+',' ',re.sub(r'<[^>]+>',' ',m.group(1)))).strip() if m else ''
            v=VER.search(tag)
            if v: out[v.group(1)]={'tag':tag,'date':dts[0] if dts else '','text':body,'url':f'https://github.com/{repo}/releases/tag/{tag}'}
        if oldest<'2025-03-01': break
        time.sleep(1)
    return out
def changelog(url):
    s=get(url); out={}; cur=None; buf=[]
    for line in s.splitlines():
        if line.startswith('#'):
            v=VER.search(line)
            if v and line.lstrip('#').strip()[:1] in '[0123456789vV':
                if cur: out[cur]['text']=' '.join(buf).strip()
                cur=v.group(1); out[cur]={'tag':line.strip('# ').strip(),'date':'','text':'','url':url}; buf=[]; continue
        if cur: buf.append(line.strip())
    if cur: out[cur]['text']=' '.join(buf).strip()
    return out
cache={}
for sid,(kind,where,filt) in SRC.items():
    if kind=='none': notes={'_source':where}
    else:
        key=(kind,where,filt)
        if key not in cache: cache[key]=releases(where,filt) if kind=='releases' else changelog(where)
        notes=dict(cache[key]); notes['_source']=f'{kind}: {where}'
    json.dump(notes,open(f'data/notes/{sid}.json','w'),indent=1)
    print(sid,kind,len(notes)-1,'versions with notes',flush=True)
