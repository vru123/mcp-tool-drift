"""Resumable sweep. Each run works until a time budget is spent, then stops cleanly.
For every (server, release) not yet in data/raw/: install date-pinned, probe, save, delete install.
Usage: python3 scripts/run_batch.py [--budget 240] [--workers 3] [--retry-errors] [--only id,id]"""
import json, os, sys, time, shutil, subprocess, datetime as dt, argparse, threading
from concurrent.futures import ThreadPoolExecutor
ap=argparse.ArgumentParser(); ap.add_argument('--budget',type=int,default=240); ap.add_argument('--workers',type=int,default=3)
ap.add_argument('--retry-errors',action='store_true'); ap.add_argument('--only',default='')
a=ap.parse_args()
T0=time.time(); ROOT=os.getcwd()
cfg={s['id']:s for s in json.load(open('servers.json'))['servers']}
rel=json.load(open('data/meta/releases.json'))
WORK='/home/claude/work'; os.makedirs(WORK,exist_ok=True); os.makedirs('data/raw',exist_ok=True)
INSTALL_T, PROBE_T = 100, 40
def pin_date(published):  # release date + 2 days, as YYYY-MM-DD
    d=dt.datetime.fromisoformat(published.replace('Z','+00:00')).date()+dt.timedelta(days=2)
    return d.isoformat()
def outpath(sid,ver): return f'data/raw/{sid}/{ver}.json'
def todo():
    only=set(filter(None,a.only.split(',')))
    for sid,r in rel.items():
        if only and sid not in only: continue
        for s in r['selected']:
            p=outpath(sid,s['version'])
            if os.path.exists(p):
                if not a.retry_errors: continue
                if json.load(open(p)).get('status')=='ok': continue
            yield sid,s
def run(sid,s):
    srv=cfg[sid]; ver=s['version']; pin=pin_date(s['published'])
    rec={'server':sid,'pkg':srv['pkg'],'registry':srv['registry'],'version':ver,'published':s['published'],
         'pinned_before':pin,'probed_at':dt.datetime.now(dt.timezone.utc).isoformat()}
    env=dict(os.environ, PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD='1', PUPPETEER_SKIP_DOWNLOAD='1', CI='1', NO_UPDATE_NOTIFIER='1',
             HOME='/tmp/mcpsandbox/home', **srv.get('env',{}))
    os.makedirs('/tmp/mcpsandbox/home',exist_ok=True)
    d=f"{WORK}/{sid}@{ver}"
    try:
        if srv['registry']=='npm':
            os.makedirs(d,exist_ok=True)
            open(f'{d}/package.json','w').write('{"private":true}')
            ins=subprocess.run(['npm','install',f"{srv['pkg']}@{ver}",f'--before={pin}','--no-audit','--no-fund','--loglevel=error','--omit=dev'],
                               cwd=d,capture_output=True,text=True,timeout=INSTALL_T,env=env)
            if ins.returncode:  # fallback: skip install scripts (native optional deps that cannot build here)
                ins=subprocess.run(['npm','install',f"{srv['pkg']}@{ver}",f'--before={pin}','--no-audit','--no-fund','--loglevel=error','--omit=dev','--ignore-scripts'],
                                   cwd=d,capture_output=True,text=True,timeout=INSTALL_T,env=env)
                rec['install_note']='installed with --ignore-scripts after normal install failed'
            if ins.returncode: raise RuntimeError('install failed: '+ins.stderr[-1500:])
            pj=json.load(open(f"{d}/node_modules/{srv['pkg']}/package.json"))
            b=pj.get('bin')
            if isinstance(b,dict) and b:   # launch through the .bin symlink, as npx would (some CLIs check argv[1])
                b=os.path.relpath(os.path.join(d,'node_modules','.bin',list(b)[0]),os.path.join(d,'node_modules',srv['pkg']))
            elif isinstance(b,str):
                b2=os.path.join(d,'node_modules','.bin',srv['pkg'].split('/')[-1])
                b=os.path.relpath(b2,os.path.join(d,'node_modules',srv['pkg'])) if os.path.exists(b2) else b
            else: b=pj.get('main')
            rec['installed']={'resolved_version':pj['version']}
            pre=['--require',os.path.join(ROOT,srv['node_preload'])] if srv.get('node_preload') else []
            cmd=['node']+pre+[os.path.join(d,'node_modules',srv['pkg'],b)]+srv.get('args',[])
        else:
            ins=subprocess.run(['uv','tool','run','--exclude-newer',pin+'T00:00:00Z','--from',f"{srv['pkg']}=={ver}",'python','-c','import sys;print(sys.executable)'],
                               capture_output=True,text=True,timeout=INSTALL_T,env=env)
            if ins.returncode: raise RuntimeError('install failed: '+ins.stderr[-1500:])
            cmd=['uvx','--exclude-newer',pin+'T00:00:00Z','--from',f"{srv['pkg']}=={ver}",srv['pkg']]+srv.get('args',[])
        p=subprocess.run(['node',f'{ROOT}/scripts/probe.js',str(PROBE_T*1000),'--']+cmd,capture_output=True,text=True,timeout=PROBE_T+15,env=env,cwd='/tmp/mcpsandbox')
        res=json.loads(p.stdout) if p.stdout.strip() else {'error':'no probe output','stderr_tail':p.stderr[-1500:]}
        rec.update(res); rec['status']='ok' if (res.get('error') is None and res.get('initialize')) else 'error'
    except Exception as e:
        rec['status']='error'; rec['error']=str(e)[-2000:]
    finally:
        shutil.rmtree(d,ignore_errors=True)
    os.makedirs(f'data/raw/{sid}',exist_ok=True)
    json.dump(rec,open(outpath(sid,ver),'w'),indent=1)
    n=len(rec.get('tools') or [])
    print(f"[{time.time()-T0:5.0f}s] {sid}@{ver}: {rec['status']} tools={n} {('' if rec['status']=='ok' else rec.get('error','')[:160])}",flush=True)
lock=threading.Lock(); it=iter(list(todo()))
def worker():
    while True:
        if time.time()-T0 > a.budget-(INSTALL_T+PROBE_T+15)*0.6: return
        with lock:
            try: sid,s=next(it)
            except StopIteration: return
        run(sid,s)
with ThreadPoolExecutor(a.workers) as ex:
    for _ in range(a.workers): ex.submit(worker)
left=len(list(todo()))
print(f'BATCH DONE in {time.time()-T0:.0f}s; remaining={left}')
