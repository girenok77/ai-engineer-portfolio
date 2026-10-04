#!/usr/bin/env python3
"""Local NAV + Codex metadata updater. Never reads mail or submits applications."""
import argparse, base64, concurrent.futures, hashlib, html, json, os, re, ssl, sys
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo
ROOT = Path(__file__).resolve().parents[1]
TLS = ssl.create_default_context(cafile='/etc/ssl/cert.pem' if Path('/etc/ssl/cert.pem').exists() else None)
OSLO = ZoneInfo('Europe/Oslo')

def config():
    values = {}
    p = ROOT / '.env'
    if p.exists():
        for line in p.read_text().splitlines():
            if '=' in line and not line.startswith('#'):
                k,v = line.split('=',1); values[k] = v.strip().strip('"').strip("'")
    values.update(os.environ)
    if not values.get('SITE_URL') or not values.get('UPDATE_TOKEN'): raise RuntimeError('Set SITE_URL and UPDATE_TOKEN in local .env')
    return values

def request(url, headers=None, data=None):
    req = Request(url,headers={'User-Agent':'Mozilla/5.0 CareerWorkspace/1.0',**(headers or {})},data=json.dumps(data).encode() if data is not None else None)
    if data is not None: req.add_header('Content-Type','application/json')
    try:
        with urlopen(req,context=TLS,timeout=45) as r: return json.loads(r.read())
    except HTTPError as e:
        if e.code == 304: return None
        raise RuntimeError(f'HTTP {e.code} from {urlparse(url).hostname}') from None

def api(cfg, data=None):
    return request(cfg['SITE_URL'].rstrip('/')+'/api/agent',{'Authorization':'Bearer '+cfg['UPDATE_TOKEN']},data)

def plain(v): return re.sub(r'\s+',' ',html.unescape(re.sub(r'<[^>]+>',' ',str(v or '')))).strip()

def nav_sync(cfg, prefs):
    from nav_search import sync
    return sync(cfg, prefs)

def timestamp(value):
    if isinstance(value,(float,int)):return datetime.fromtimestamp(value,timezone.utc)
    return datetime.fromisoformat(value.replace('Z','+00:00'))

def collect_sessions(days=60):
    cutoff=datetime.now(timezone.utc)-timedelta(days=days); rows=[]
    keys=('input_tokens','cached_input_tokens','output_tokens','total_tokens')
    for path in (Path.home()/'.codex/sessions').rglob('*.jsonl'):
        if path.stat().st_mtime<cutoff.timestamp():continue
        thread=path.stem;project='Codex';turn=None;previous={};turns=[];subagent=False
        for line in path.open(errors='replace'):
            try:record=json.loads(line)
            except ValueError:continue
            payload=record.get('payload') or {};kind=record.get('type')
            if kind=='session_meta':
                project=Path(payload.get('cwd') or 'Codex').name or 'Codex'
                subagent=isinstance(payload.get('source'),dict) and 'subagent' in payload['source']
            if kind!='event_msg':continue
            typ=payload.get('type');ts=timestamp(record['timestamp'])
            if typ=='task_started':
                if turn:turns.append(turn)
                turn={'id':payload.get('turn_id',str(ts)), 'start':timestamp(payload.get('started_at',record['timestamp'])),'end':ts,'tokens':None}
            elif typ=='token_count':
                total=(payload.get('info') or {}).get('total_token_usage')
                if not total:continue
                delta={k:max(0,total.get(k,0)-previous.get(k,0)) if total.get(k,0)>=previous.get(k,0) else total.get(k,0) for k in keys}
                previous=total
                if turn:
                    turn['tokens']={k:(turn['tokens'] or {}).get(k,0)+delta[k] for k in keys}
                    turn['end']=ts
            elif typ=='task_complete' and turn:
                turn['end']=timestamp(payload.get('completed_at',record['timestamp']));turns.append(turn);turn=None
        if turn:turns.append(turn) # unfinished turn: measure only through its last observed event
        if subagent:continue
        groups=[]
        for t in sorted(turns,key=lambda x:x['start']):
            if t['start']<cutoff:continue
            day=t['start'].astimezone(OSLO).date().isoformat()
            if not groups or groups[-1]['day']!=day or (t['start']-groups[-1]['end']).total_seconds()>1800:
                groups.append({'day':day,'start':t['start'],'end':t['end'],'first':t['id'],'active':0,'tokens':None})
            g=groups[-1];g['end']=max(g['end'],t['end']);g['active']+=max(0,(t['end']-t['start']).total_seconds())
            if t['tokens'] is not None:g['tokens']={k:(g['tokens'] or {}).get(k,0)+t['tokens'][k] for k in keys}
        for g in groups:
            tokens=g['tokens'] or {}
            rows.append({'id':hashlib.sha256((thread+g['first']).encode()).hexdigest()[:32],'day':g['day'],'project':project,'startedAt':g['start'].isoformat(),'endedAt':g['end'].isoformat(),'activeSeconds':round(g['active']),'elapsedSeconds':round((g['end']-g['start']).total_seconds()),'inputTokens':tokens.get('input_tokens'),'cachedTokens':tokens.get('cached_input_tokens'),'outputTokens':tokens.get('output_tokens'),'totalTokens':tokens.get('total_tokens')})
    return rows

def sessions_sync(cfg):
    rows=collect_sessions()
    for i in range(0,len(rows),200):api(cfg,{'kind':'sessions','sessions':rows[i:i+200]})
    api(cfg,{'kind':'run','runKind':'codex','status':'ok','message':f'Codex: імпортовано {len(rows)} сесій за 60 днів; лише час і токени.'})
    return {'sessions':len(rows)}

def upload_cv(cfg,path,application_id=None):
    path=Path(path);current=api(cfg)
    if any(c['filename']==path.name and c['application_id']==application_id for c in current['cvs']):return {'alreadyUploaded':True}
    text=''
    if path.suffix.lower()=='.docx':
        import zipfile,xml.etree.ElementTree as ET
        with zipfile.ZipFile(path) as z:text='\n'.join(n.text or '' for n in ET.fromstring(z.read('word/document.xml')).iter('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t'))
    return api(cfg,{'kind':'cv','cvKind':'adapted' if application_id else 'base','applicationId':application_id,'filename':path.name,'base64':base64.b64encode(path.read_bytes()).decode(),'text':text})

def main():
    p=argparse.ArgumentParser();p.add_argument('--only',choices=['nav','sessions','all'],default='all');p.add_argument('--upload-cv');p.add_argument('--application-id');p.add_argument('--inspect',action='store_true');args=p.parse_args()
    if args.inspect:
        rows=collect_sessions();print(json.dumps({'sessions':len(rows),'days':len(set(s['day'] for s in rows)),'tokens':sum(s['totalTokens'] or 0 for s in rows)}));return
    cfg=config();results={}
    if args.upload_cv:results['cv']=upload_cv(cfg,args.upload_cv,args.application_id)
    if args.only in ('nav','all'):results['nav']=nav_sync(cfg,api(cfg)['preferences'])
    if args.only in ('sessions','all'):results['codex']=sessions_sync(cfg)
    print(json.dumps(results,ensure_ascii=False))
if __name__=='__main__':
    try:main()
    except Exception as e:print(f'Sync failed: {e}',file=sys.stderr);sys.exit(1)
