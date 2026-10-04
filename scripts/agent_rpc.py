#!/usr/bin/env python3
"""Authenticated agent bridge. Reads secrets from ignored .env, not arguments."""
import argparse,json,sys
from pathlib import Path
from urllib.request import Request,urlopen
from daily_sync import api,config,TLS
p=argparse.ArgumentParser();p.add_argument('--payload',help='Path to JSON POST payload');p.add_argument('--download-cv');p.add_argument('--output');a=p.parse_args();cfg=config()
if a.download_cv:
 if not a.output:sys.exit('--output required')
 request=Request(cfg['SITE_URL'].rstrip('/')+'/api/cv/'+a.download_cv,headers={'User-Agent':'Mozilla/5.0 CareerWorkspace/1.0','Authorization':'Bearer '+cfg['UPDATE_TOKEN']})
 with urlopen(request,context=TLS,timeout=45) as r:Path(a.output).write_bytes(r.read())
 print(json.dumps({'ok':True,'saved':a.output}))
else:
 payload=json.loads(Path(a.payload).read_text()) if a.payload else None
 print(json.dumps(api(cfg,payload),ensure_ascii=False))
