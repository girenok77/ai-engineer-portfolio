"""Read the full public NAV English/IT search, without deadline/age exclusions."""
import concurrent.futures, html, json, re
from datetime import datetime
from html.parser import HTMLParser
from urllib.request import Request, urlopen
from daily_sync import TLS, OSLO, plain, request, api
SEARCH='https://arbeidsplassen.nav.no/stillinger?occupationLevel1=IT&v=6&workLanguage=Engelsk&sort=expires&pageCount=100'
BASE='https://pam-stilling-feed.nav.no'

class AdText(HTMLParser):
    def __init__(self):
        super().__init__(); self.inside=False; self.skip=0; self.parts=[]; self.title=''; self.heading=False
    def handle_starttag(self, tag, attrs):
        if tag=='main': self.inside=True
        if self.inside and tag in ('script','style','svg'): self.skip+=1
        if self.inside and tag=='h1': self.heading=True
    def handle_endtag(self, tag):
        if tag=='main': self.inside=False
        if self.inside and tag in ('script','style','svg'): self.skip=max(0,self.skip-1)
        if tag=='h1': self.heading=False
    def handle_data(self, value):
        if self.inside and not self.skip:
            if value.strip(): self.parts.append(value.strip())
            if self.heading: self.title+=value

def page(url):
    with urlopen(Request(url,headers={'User-Agent':'Mozilla/5.0 CareerWorkspace/1.0'}),context=TLS,timeout=45) as r:
        return r.read().decode()

def search_ids():
    ids=[]
    for offset in range(0,10000,100):
        source=page(SEARCH+('&from='+str(offset) if offset else ''))
        found=list(dict.fromkeys(re.findall(r'/stillinger/stilling/([0-9a-f-]{36})',source)))
        if not found: break
        fresh=[uid for uid in found if uid not in ids]
        ids.extend(fresh)
        if len(found)<100 or not fresh: break
    else: raise RuntimeError('NAV search exceeded 100 pages; do not report a complete review')
    if not ids: raise RuntimeError('No NAV IDs found; source layout may have changed')
    return ids

def public_token():
    raw=page(BASE+'/api/publicToken')
    m=re.search(r'eyJ[\w-]+\.[\w-]+\.[\w-]+',raw)
    if not m: raise RuntimeError('NAV public token unavailable')
    return m.group()

def detail(uid, token):
    try:
        d=request(BASE+'/api/v1/feedentry/'+uid,{'Authorization':'Bearer '+token})
        if d.get('ad_content'): return d
    except RuntimeError as exc:
        if 'HTTP 404' not in str(exc): raise
    # External listings are not always present in the public feed; read their public ad.
    source=page('https://arbeidsplassen.nav.no/stillinger/stilling/'+uid)
    parser=AdText(); parser.feed(source); parts=parser.parts
    if not parser.title: raise RuntimeError('NAV ad has no readable title: '+uid)
    decoded=source.replace('\\"','"')
    dates={}
    for key in ('published','expires'):
        match=re.search(r'"'+key+r'":"([^"]+)"',decoded)
        dates[key]=html.unescape(match.group(1)) if match else ''
    return {'uuid':uid,'htmlFallback':True,'status':'ACTIVE','ad_content':{'uuid':uid,'title':parser.title.strip(),'description':' '.join(parts),'employer':{'name':parts[1] if len(parts)>1 else ''},'workLocations':[{'city':parts[2] if len(parts)>2 else ''}],**dates}}

# Individually reviewed non-development roles from the 2026-10-04 search.
REVIEWED_UNRELATED={
'a1908808-b952-4fa7-a307-e7c423236143': 'Vil du bidra til å bygge forsvarsevne gjennom sterk sikkerhetsfaglig rådgivning?',
'51d4b8db-9f80-44d5-b61f-05bde5661e24': 'Kickstart your career at a leading tech company',
'3e192256-efb7-448c-9379-ab20a83f72b0': 'Ansvarlig governance- og tjenestestyring for automatisering og plattformtjenester',
'b4df6548-6b75-47cb-b66d-85338338a8a0': 'Vil du være med på å forme fremtidens digitale forsvarsløsninger?',
'3970aa90-3622-4b16-b33e-6725a4912280': 'Hr du interesse for informasjonssikkerhet og F-35?',
'5ab5f7c3-70ad-432f-9a47-82672ffb88b6': 'Vil du jobbe med droner i Sjøforsvaret?',
'5ebb9aab-1535-4f9e-9759-e817d24df81c': 'Make an Impact - Protect innovations that help save lives',
'b471cc20-4e16-4f95-ba12-af1689f18057': 'Vil du jobbe med et av Norges mest avanserte og strategisk viktige våpensystemer?',
'bdd4b8cb-3507-4270-9878-cb1e8a6a85b9': 'Ønsker du å bidra til informasjonssikkerhet i Luftforsvaret?',
'2ce60fc5-cecd-4369-b32e-71599f5572e1': 'Commissioning System Responsible Telecommunication',
'03494034-14de-4ecd-a5b2-b3ad178ec0f2': 'Lead Operational Excellence in AI-Driven Transformation',
'5fa82ca8-4389-4b44-bf1a-3f8cd913d42e': 'Er du en nysgjerrig leder med teknisk kompetanse til å lede våre penetrasjonstestere?',
'd5af7ede-260e-4a48-b550-aa691109ee8b': 'Help shape the future of electrical and automation systems in the Maritime Industry!',
'2f34bd15-bf69-4cc3-86ae-f8aeeb5c14ef': 'Seniorrådgiver interoperabilitet',
'eb0d7184-3aff-4adb-96e4-65a6d906e29f': 'Vil du bygge luftforsvarets nye fagmiljø for data og analyse?',
'b8f2516d-ab75-4040-8f67-b098516f01ac': 'Er du vår nye analytiker innen operativ sikkerhetstjeneste?',
'13c70c13-b669-4608-b3a8-49598a30ca94': 'System Integration Lead',
'c8bfa948-a49a-48fd-93d4-d4d6b118eeda': 'Ønsker du en spennende stilling som utreder innen maritim teknologi?',
'bf852cb7-6361-4cb8-8cd6-a261f0bdbe5a': 'Har du SAP SuccessFactors i verktøykassen og HR i ryggmargen?',
'0d270ca7-6875-49b4-a9a9-84524bfd762c': 'Er du strukturert, detaljorientert og opptatt av gode leveranser?',
'cd949f2c-d616-4857-a382-c2c98a0cd0d7': 'Vil du kombinere teknisk analysearbeid med ledelse av leveranser på noen av verdens mest avanserte missilsystemer?',
'd95c8799-cecb-4af6-ab2c-492a6492b830': 'Avinor har startet boarding av teknologer – bli vår nye systemingeniør navigasjonssystemer!',
'edbc333e-73a1-44ec-9c4c-e79e44e79333': 'Audit Wizard – bring audit expertise into an AI product',
'f4a9e426-74eb-44a9-9eca-9a1c8010a376': 'Join NordicNeuroLab as a QA Technician',
'7b2acd4a-3b62-4535-bb83-0d0a874d33af': 'Shape the Future of Mobility',
}

TECH=re.compile(r'python|javascript|typescript|postgres|sql|flask|django|react|programmer|software|utvikl|developer|full.?stack|backend|front.?end|data.?scien|data.?analy|data.?engineer|machine.?learning|\bAI\b|\bKI\b|\bIT\b|\bIKT\b|support|automasjon|integrasjon|devops|cloud|plattform',re.I)
UNRELATED=re.compile(r'juridisk|warehouse|lagerteam|innholdsprodusent|content.*designer|graphic|grafisk designer|multimedia|customs administrator|hazardous materials|process designer|CNC.programmer|construction security|document controller|dokumentkontroller|prosjektkoordinator|project administrator|senior scientist.*nuclear|researcher in immunology|growth manager|product designer|tjenestedesigner',re.I)

def assessment(d):
    c=d.get('ad_content',{}); title=plain(c.get('title')); text=plain(c.get('description')); combined=title+' '+text
    if not c or d['uuid'] in REVIEWED_UNRELATED or UNRELATED.search(title) or not TECH.search(combined): return None
    # Pure senior management/HR/legal or industrial disciplines are outside the candidate's work.
    role=re.search(r'Stillingstittel (.+?) Type ansettelse',text)
    role=role.group(1) if role else title
    if re.search(r'Director|Head of Software|Team Manager|HRIS Lead|IT Business Relationship Manager|IP Manager|Information System Security (?:Manager|Operator)|Ellisiv|Prosjekt Engineer.*Materials|Power System Physicist|Hydrocarbon Management|subsea team|visuelle uttrykket',title+' '+role,re.I):return None
    skills=[label for pattern,label in [(r'\bpython\b','Python'),(r'\bflask\b','Flask'),(r'postgres|\bsql\b','SQL / бази даних'),(r'javascript|typescript|react|frontend|front.end|full.stack','Web / frontend'),(r'machine.learning|data.scien|\bML\b|\bAI\b|\bKI\b','ML / AI'),(r'test|feilsøk|debug','Тестування / налагодження')] if re.search(pattern,combined,re.I)]
    limits=[]
    if re.search(r'\b(senior|principal|lead|staff|architect|arkitekt)\b',role,re.I) or re.search(r'(?:[3-9]|10)\+?\s*(?:years|års).{0,30}(?:experience|erfaring)|(?:minimum|minst).{0,8}[3-9].{0,8}års',text,re.I):limits.append('Рівень досвіду вищий за поточний')
    if re.search(r'norsk statsborg|norwegian citizen',text,re.I):limits.append('Вимога громадянства — перешкода')
    if re.search(r'sikkerhetsklar|security clearance',text,re.I):limits.append('Потрібна перевірка допуску')
    if re.search(r'(?:fluent|fluency|excellent|must|require\w*).{0,45}(?:norwegian|norsk)|(?:norwegian|norsk).{0,45}(?:fluent|fluency|required|flytende)|beherske.{0,25}norsk|gode.{0,30}norsk|arbeidspråk.?-?norsk',text,re.I):limits.append('Перевірити вимогу норвезької')
    if re.search(r'graduate|nyutdann|intern|student|phd|researcher',role+' '+title,re.I):limits.append('Перевірити студентський статус / диплом / рік випуску')
    if re.search(r'phd|postdoc|researcher|scientist within',title,re.I):limits.append('Академічна роль: перевірити вимогу магістра / PhD')
    cat='ai' if re.search(r'\bai\b|\bki\b|\bml\b|machine.learning',role+' '+title,re.I) else 'data' if re.search(r'data|scientific|programmer',role+' '+title,re.I) else 'qa' if re.search(r'test|quality|\bqa\b',role,re.I) else 'fullstack' if re.search('full.stack|front.end|mobile|android|ios',role,re.I) else 'automation' if re.search('automat|integr|support|devops|cloud|plattform|nettverk|network|IKT|IT ',role,re.I) else 'backend'
    if not skills: skills=['Суміжна IT-роль: освіта й досвід налагодження']
    score=max(15,min(85,40+len(skills)*8-len(limits)*9))
    notes='Частковий збіг: '+', '.join(skills)+'. '+('Обмеження: '+'; '.join(limits)+'. ' if limits else '')+'Перевірити всі обов’язкові вимоги. Збережено до приватної черги, не надіслано.'
    locations=', '.join(dict.fromkeys(x.get('city') or x.get('municipal') or '' for x in c.get('workLocations',[])))
    return {'id':d['uuid'],'title':title,'company':c.get('employer',{}).get('name',''),'location':locations or 'Norway','url':'https://arbeidsplassen.nav.no/stillinger/stilling/'+d['uuid'],'description':text,'published':c.get('published',''),'expires':c.get('expires',''),'active':True,'category':cat,'score':score,'reasons':skills+limits,'reviewNotes':notes}

def sync(cfg,prefs):
    ids=search_ids(); token=cfg.get('NAV_TOKEN') or public_token()
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
        details=list(pool.map(lambda uid:detail(uid,token),ids))
    rows=[r for d in details if (r:=assessment(d))]
    for i in range(0,len(rows),200):api(cfg,{'kind':'jobs','jobs':rows[i:i+200]})
    # User requested saving every partial match; do not limit this to draft-preparation quotas.
    state=api(cfg);existing={a['job_id'] for a in state['applications']};saved=0
    for row in rows:
        if row['id'] not in existing:api(cfg,{'kind':'action','action':'save','jobId':row['id']});saved+=1
    state=api(cfg);by_job={a['job_id']:a for a in state['applications']}
    for row in rows:
        a=by_job.get(row['id'])
        if a and a['status']=='draft' and not a.get('notes'):
            api(cfg,{'kind':'action','action':'application','id':a['id'],'status':'draft','notes':row['reviewNotes']})
    message=f'NAV English/IT: перевірено {len(ids)} оголошень, {len(rows)} часткових збігів, нових у черзі {saved}. Дедлайн не є фільтром.'
    api(cfg,{'kind':'run','runKind':'nav','status':'ok','message':message})
    return {'scanned':len(ids),'matched':len(rows),'newSaved':saved}
