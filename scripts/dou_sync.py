"""DOU Python listings, 0–1 and 1–3 years; explicit foreign locations by default."""
import concurrent.futures, html, http.cookiejar, json, re
from datetime import datetime
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from urllib.parse import urlencode, urljoin, urlsplit, urlunsplit
from urllib.request import Request, build_opener, HTTPCookieProcessor, HTTPSHandler
from daily_sync import TLS, OSLO, api, config, plain
from nav_search import page
SEARCHES={exp:'https://jobs.dou.ua/vacancies/?category=Python&exp='+exp for exp in ('1-3','0-1')}
FOREIGN=re.compile(r'за\s+кордоном|\babroad\b|\b(?:США|Канада|Польща|Німеччина|Чехія|Словаччина|Норвегія|Великобританія|Іспанія|Португалія|Нідерланди|Литва|Латвія|Естонія|Румунія|Кіпр|Франція|Швеція|Данія|США|USA|Poland|Germany|Czechia|Slovakia|Norway|UK|Canada)\b|Вашингтон|Варшава|Краків|Прага|Кошице|Берлін|Лондон|Лісабон|Лімасол|Таллінн|Вільнюс|Амстердам|Барселона|Стокгольм|Осло|Krakow|Kosice|Prague|Warsaw|Berlin|London|Washington',re.I)
UKRAINIAN=re.compile(r'Київ|Львів|Харків|Одеса|Дніпро|Вінниця|Івано.Франківськ|Хмельницький|Ужгород|Черкаси|Чернівці|Тернопіль|Рівне|Луцьк|Житомир|Суми|Полтава|Миколаїв|Запоріжжя|Донецьк|Херсон|Кропивницький|Kyiv|Kiev|Lviv|Kharkiv|Odesa|Ukraine|Україн',re.I)

def canonical(value):
    u=urlsplit(html.unescape(value));return urlunsplit((u.scheme,u.netloc,u.path,'',''))

def cards(source,exp):
    rows=[]
    for li in re.findall(r'<li class="l-vacancy[^\"]*">(.*?)</li>',source,re.S):
        a=re.search(r'<a class="vt" href="([^"]+)"[^>]*>(.*?)</a>',li,re.S)
        if not a:continue
        company=re.search(r'<a\s+[^>]*class="company"[^>]*>(.*?)</a>',li,re.S)
        city=re.search(r'class="cities[^\"]*"[^>]*>(.*?)</span>',li,re.S)
        date=re.search(r'<div class="date"[^>]*>(.*?)</div>',li,re.S)
        url=canonical(a.group(1));uid=re.search(r'/vacancies/(\d+)/',url)
        if not uid:continue
        rows.append({'id':'dou-'+uid.group(1),'title':plain(a.group(2)),'company':plain(company.group(1))if company else'', 'location':plain(city.group(1))if city else'','url':url,'experience':exp,'dateLabel':plain(date.group(1))if date else''})
    return rows

def listings(exp):
    url=SEARCHES[exp]
    opener=build_opener(HTTPCookieProcessor(http.cookiejar.CookieJar()),HTTPSHandler(context=TLS))
    headers={'User-Agent':'Mozilla/5.0 CareerWorkspace/1.0'}
    with opener.open(Request(url,headers=headers),timeout=45)as r:source=r.read().decode()
    rows=cards(source,exp)
    count=len(rows)
    endpoint=re.search(r'window.XHR_VS_URL\s*=\s*"([^"]+)"',source)
    token=re.search(r'window.CSRF_TOKEN\s*=\s*"([^"]+)"',source)
    if 'class="more-btn"' in source:
        if not endpoint or not token:raise RuntimeError('DOU pagination changed; complete search cannot be verified')
        target=urljoin(url,html.unescape(endpoint.group(1)))
        if urlsplit(target).hostname!='jobs.dou.ua':raise RuntimeError('Unexpected DOU pagination host')
        for _ in range(100):
            req=Request(target,data=urlencode({'csrfmiddlewaretoken':token.group(1),'count':count}).encode(),headers={**headers,'Referer':url,'Content-Type':'application/x-www-form-urlencoded','X-Requested-With':'XMLHttpRequest'})
            with opener.open(req,timeout=45)as r:result=json.loads(r.read())
            if result.get('error'):raise RuntimeError('DOU pagination returned an error')
            extra=cards(result.get('html',''),exp);rows.extend(extra);count+=len(extra)
            if result.get('last'):break
            if not extra:raise RuntimeError('DOU pagination stalled')
        else:raise RuntimeError('DOU exceeded pagination limit')
    heading=re.search(r'<h1[^>]*>(.*?)</h1>',source,re.S)
    total=re.search(r'\d+',plain(heading.group(1)))if heading else None
    unique={r['id']:r for r in rows}
    if total and int(total.group())!=len(unique):raise RuntimeError(f'DOU count mismatch: expected {total.group()}, read {len(unique)}')
    return list(unique.values())

class VacancyBody(HTMLParser):
    def __init__(self):super().__init__();self.depth=0;self.parts=[]
    def handle_starttag(self,tag,attrs):
        if self.depth:
            if tag not in ('br','img','hr','input','meta','link'):self.depth+=1
        elif 'vacancy-section' in dict(attrs).get('class','').split():self.depth=1
    def handle_endtag(self,tag):
        if self.depth and tag not in ('br','img','hr','input','meta','link'):self.depth-=1
    def handle_data(self,value):
        if self.depth and value.strip():self.parts.append(value.strip())

def geography(row,include_remote=False):
    loc=row['location']
    if FOREIGN.search(loc):return 'foreign'
    if include_remote and re.search(r'віддалено|remote',loc,re.I) and not UKRAINIAN.search(loc):return 'remote-unconfirmed'
    return None

def details(row):
    source=page(row['url']);parser=VacancyBody();parser.feed(source);text=' '.join(parser.parts)
    months={'січня':1,'лютого':2,'березня':3,'квітня':4,'травня':5,'червня':6,'липня':7,'серпня':8,'вересня':9,'жовтня':10,'листопада':11,'грудня':12}
    date=re.search(r'<div class="date"[^>]*>(.*?)</div>',source,re.S)
    stamp=re.search(r'(\d{1,2})\s+([а-яіїєґ]+)\s+(\d{4})',plain(date.group(1)))if date else None
    published=datetime(int(stamp.group(3)),months[stamp.group(2)],int(stamp.group(1)),12,tzinfo=OSLO).isoformat()if stamp and stamp.group(2)in months else ''
    if not text:raise RuntimeError('DOU vacancy body missing: '+row['id'])
    row=dict(row,description=text)
    skills=[label for pattern,label in [(r'python','Python'),(r'flask','Flask'),(r'postgres|\bsql\b','SQL / PostgreSQL'),(r'javascript|react|full.stack','Web / full-stack'),(r'\bML\b|\bLLM\b|\bAI\b|\bRAG\b','ML / AI')]if re.search(pattern,text,re.I)]
    gaps=[]
    if re.search(r'\b(?:senior|lead)\b|[3-9]\+?\s*(?:рок|years)' ,row['title']+' '+text,re.I):gaps.append('Потрібен більший досвід, ніж підтверджений')
    if re.search(r'продакшн|production.{0,40}(?:LLM|AI|RAG)|\bRAG\b',text,re.I):gaps.append('Production LLM / RAG не підтверджені')
    if re.search(r'Kubernetes|Helm|ArgoCD|AWS|GCP|DevOps',text,re.I):gaps.append('Cloud / DevOps потребують перевірки')
    if re.search(r'Scrapy|proxy|anti.bot|fingerprint',text,re.I):gaps.append('Спеціалізований scraping досвід не підтверджений')
    if row['geo']=='remote-unconfirmed':gaps.append('Remote: робота з Норвегії не підтверджена')
    else:gaps.append('Перевірити право роботи / доступність із Норвегії')
    if re.search('hybrid',text,re.I):gaps.append('Hybrid: потрібні переїзд і відвідування офісу')
    cat='ai'if re.search(r'\bAI\b|\bML\b',row['title'],re.I)else'fullstack'if re.search(r'full.stack',row['title'],re.I)else'automation'if re.search('scrap|integr|support',row['title'],re.I)else'backend'
    return {**row,'active':True,'source':'dou','published':published,'expires':'','category':cat,'score':max(20,min(80,45+len(skills)*7-len(gaps)*7)),'reasons':['DOU · '+row['experience']+' роки']+skills+gaps,'reviewNotes':'DOU Python '+row['experience']+' роки. Місце: '+row['location']+'. Часткові збіги: '+', '.join(skills)+'. Прогалини: '+'; '.join(gaps)+'. Повний текст перевірено. Збережено, не надіслано. Норвезький дозвіл роботи не дає автоматичного права працювати в інших країнах. Дедлайн не є причиною пропускати вакансію.'}

def sync(cfg):
    include_remote=cfg.get('DOU_INCLUDE_REMOTE','false').lower()in ('true','1','yes')
    all_rows={}
    counts={}
    for exp in SEARCHES:
        items=listings(exp);counts[exp]=len(items)
        for row in items:
            geo=geography(row,include_remote)
            if geo:all_rows[row['id']]={**row,'geo':geo}
    with concurrent.futures.ThreadPoolExecutor(max_workers=3)as pool:rows=list(pool.map(details,all_rows.values()))
    for i in range(0,len(rows),150):api(cfg,{'kind':'jobs','jobs':rows[i:i+150]})
    state=api(cfg);existing={a['job_id']for a in state['applications']};saved=0
    for row in rows:
        if row['id']not in existing:api(cfg,{'kind':'action','action':'save','jobId':row['id']});saved+=1
    state=api(cfg);byjob={a['job_id']:a for a in state['applications']}
    for row in rows:
        a=byjob.get(row['id'])
        if a and a['status']=='draft'and not a.get('notes'):
            api(cfg,{'kind':'action','action':'application','id':a['id'],'status':'draft','notes':row['reviewNotes']})
    api(cfg,{'kind':'run','runKind':'dou','status':'ok','message':f'DOU Python: перевірено {sum(counts.values())} оголошень у двох категоріях досвіду; {len(rows)} географічних/часткових збігів, нових у черзі {saved}. Remote без іноземної локації: '+('включено з перевіркою Норвегії'if include_remote else'не включено')+'. Без відсіву за дедлайном.'})
    return {'scanned':counts,'matched':len(rows),'newSaved':saved,'includeRemote':include_remote}

if __name__=='__main__':
    import sys
    try:print(json.dumps(sync(config()),ensure_ascii=False))
    except Exception as exc:print('DOU sync failed: '+str(exc),file=sys.stderr);sys.exit(1)
