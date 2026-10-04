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
    base='https://pam-stilling-feed.nav.no'
    token=cfg.get('NAV_TOKEN')
    if not token:
        with urlopen(base+'/api/publicToken',context=TLS,timeout=30) as r: raw=r.read().decode()
        m=re.search(r'eyJ[\w-]+\.[\w-]+\.[\w-]+',raw)
        if not m: raise RuntimeError('NAV public experimental token unavailable; configure NAV_TOKEN')
        token=m.group()
    headers={'Authorization':'Bearer '+token,'Accept':'application/json'}
    state_dir=ROOT/'.private';state_dir.mkdir(exist_ok=True)
    statefile=state_dir/'nav-state.json'
    state=json.loads(statefile.read_text()) if statefile.exists() else {}
    # Re-read the recent window to apply changed filters and refresh active listings.
    page='/api/v1/feed'
    headers['If-Modified-Since']=format_datetime(datetime.now(timezone.utc)-timedelta(days=14),usegmt=True)
    known={j['id'] for j in api(cfg)['jobs']}
    seen=set(); matched=0; processed=0; batches=0
    words=[x.strip().lower() for x in prefs.get('keywords','Python, Flask, SQL').split(',') if x.strip()]
    categories=prefs.get('categories',['backend','fullstack','automation','ai'])
    title_re=re.compile(r'utvikler|developer|software|programmer|full.?stack|backend|front.?end|data.?engineer|machine.?learning|artificial|kunstig|\bAI\b|\bML\b|test.?automat|integrasjon|automatisering',re.I)
    senior_re=re.compile(r'\b(senior|lead|principal|staff|head|director|sjef|leder)\b',re.I)
    norsk_re=re.compile(r'(fluent|fluency|proficien\w*|excellent|must|require\w*).{0,45}(norwegian|norsk)|(norwegian|norsk).{0,45}(fluent|fluency|require\w*|must)|må.{0,30}(norsk|skandinavisk)|beherske.{0,25}norsk|gode.{0,30}norsk',re.I)
    def detail(item):
        e=item.get('_feed_entry',{});uid=e.get('uuid')
        if not uid: return None
        if e.get('status')!='ACTIVE': return {'id':uid,'active':False}
        title=e.get('title') or item.get('title','')
        if not title_re.search(title):return None
        if re.search(r'\b(phd|postdoc|postdoktor|professor|researcher|forsker|selger|sales|auditor|audit wizard|mellomleder|driftsmedarbeider)\b',title,re.I):return {'id':uid,'active':False}
        target=urljoin(base,item['url'])
        if urlparse(target).netloc!=urlparse(base).netloc:raise RuntimeError('Unexpected NAV detail host')
        d=request(target,{k:v for k,v in headers.items() if k!='If-Modified-Since'})
        content=d.get('ad_content',d.get('json',{}))
        if isinstance(content,str):content=json.loads(content)
        if d.get('status','ACTIVE')!='ACTIVE':return {'id':uid,'active':False}
        title=content.get('title') or title
        text=plain(content.get('description',''));combined=(title+' '+text).lower()
        if prefs.get('excludeSenior',True) and senior_re.search(title):return {'id':uid,'active':False}
        if prefs.get('language')=='english' and (norsk_re.search(combined) or re.search(r'norsk.{0,35}(muntlig|skriftlig)|(muntlig|skriftlig).{0,35}norsk|norsk statsborgerskap|norwegian citizen|norsk statsborger|sikkerhetsklarer',combined)):return {'id':uid,'active':False}
        location=', '.join(dict.fromkeys(x.get('city') or x.get('municipal') or '' for x in content.get('workLocations',[]))) or e.get('municipal','Norway')
        locations=[x.strip().lower() for x in prefs.get('locations','').split(',') if x.strip()]
        if locations and not any(x in location.lower() for x in locations):return {'id':uid,'active':False}
        cat='ai' if re.search(r'\bai\b|\bllm\b|machine.?learning|kunstig|artificial',title,re.I) else 'data' if re.search('data.?engineer',title,re.I) else 'qa' if re.search('test|quality',title,re.I) else 'fullstack' if re.search('full.?stack|front.?end',title,re.I) else 'automation' if re.search('automat|integras',title,re.I) else 'backend'
        if cat not in categories:return {'id':uid,'active':False}
        hits=[w for w in words if re.search(r'(?<!\w)'+re.escape(w)+r'(?!\w)',combined)]
        if 'python' not in hits and not (cat in ('fullstack','backend','automation') and len(hits)>=2):return {'id':uid,'active':False}
        if re.search(r'c\+\+|php|\.net|c#',title,re.I):return {'id':uid,'active':False}
        return {'id':uid,'title':title,'company':content.get('employer',{}).get('name') or e.get('businessName',''),'location':location,'description':text,'url':'https://arbeidsplassen.nav.no/stillinger/stilling/'+uid,'published':content.get('published',item.get('date_modified','')),'expires':content.get('expires',''),'active':True,'category':cat,'score':min(95,40+len(hits)*9),'reasons':[w.upper() if w=='sql' else w.title() for w in hits]+['Перевірити вимоги вручну']}
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
        for _ in range(60):
            target=urljoin(base,page)
            if urlparse(target).netloc!=urlparse(base).netloc:raise RuntimeError('Unexpected NAV feed host')
            feed=request(target,headers)
            headers.pop('If-Modified-Since',None)
            if not feed:break
            items=[]
            for item in feed.get('items',[]):
                uid=item.get('_feed_entry',{}).get('uuid')
                # Details always return latest state; process a uuid only once this run.
                if uid and uid not in seen:items.append(item);seen.add(uid)
            rows=[x for x in pool.map(detail,items) if x and (x.get('active') or x['id'] in known)]
            for i in range(0,len(rows),250):api(cfg,{'kind':'jobs','jobs':rows[i:i+250]})
            matched+=sum(x.get('active') is True for x in rows);processed+=len(items);batches+=1
            page=feed.get('next_url')
            if not page:break
        else:raise RuntimeError('NAV backfill page limit reached; partial results saved; repeat needed')
    statefile.write_text(json.dumps({'lastSuccessfulAt':datetime.now(timezone.utc).isoformat(),'matched':matched,'scanned':processed}))
    api(cfg,{'kind':'run','runKind':'nav','status':'ok','message':f'NAV: {matched} відповідних оголошень за 14 днів; перевірено {processed} записів.'})
    return {'matched':matched,'scanned':processed,'pages':batches}

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
