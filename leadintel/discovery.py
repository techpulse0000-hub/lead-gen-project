"""Broad web discovery. Company candidates come only from returned evidence, never seed lists."""
import json
import os
import re
import urllib.error
import urllib.request
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

from .crawler import classify
from .llm_classifier import score_classification
from .store import now

class SearchConnection:
    """Session key is never returned to the browser or written to disk."""
    def __init__(self):
        self._key=None

    def key(self):
        return self._key or os.environ.get('TAVILY_API_KEY','').strip()

    def configure(self, value):
        if not isinstance(value,str) or not 10<=len(value.strip())<=512 or any(c.isspace() for c in value.strip()):
            raise ValueError('Enter a valid Tavily API key')
        self._key=value.strip()

    def clear(self):
        self._key=None


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):
        raise ValueError('Search provider redirect refused')


def request_search(body,key):
    req=urllib.request.Request('https://api.tavily.com/search',data=json.dumps(body).encode(),
        headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'},method='POST')
    try:
        with urllib.request.build_opener(NoRedirect()).open(req,timeout=30) as response:
            raw=response.read(2_000_001)
            if len(raw)>2_000_000:
                raise ValueError('Search response exceeded size limit')
            payload=json.loads(raw)
        if not isinstance(payload,dict) or not isinstance(payload.get('results'),list):
            raise ValueError('Search provider returned an invalid result format')
        return payload
    except urllib.error.HTTPError as exc:
        messages={401:'Tavily rejected the API key. Update it in Search connection.',403:'Tavily denied this request.',429:'Tavily rate limit reached. Try again later.',432:'Tavily account usage limit reached.',433:'Tavily account spending limit reached.'}
        raise ValueError(messages.get(exc.code,'Search provider returned HTTP '+str(exc.code))) from None
    except (urllib.error.URLError,OSError):
        raise ValueError('Could not reach Tavily. Check this computer’s network access.') from None


def budget_remaining(store):
    stamp=now()
    daily=store.db.execute('SELECT COALESCE(SUM(MAX(reserved_credits,COALESCE(reported_credits,0))),0) FROM provider_attempts WHERE substr(started_at,1,10)=?',(stamp[:10],)).fetchone()[0]
    monthly=store.db.execute('SELECT COALESCE(SUM(MAX(reserved_credits,COALESCE(reported_credits,0))),0) FROM provider_attempts WHERE substr(started_at,1,7)=?',(stamp[:7],)).fetchone()[0]
    return max(0,int(min(30-daily,900-monthly)))


def reserve_search(store,run_id,query):
    """Atomic local engine credit ledger. Old CLI ledger is separate and execution is disabled there."""
    stamp=now()
    store.db.execute('BEGIN IMMEDIATE')
    try:
        if budget_remaining(store)<1:
            raise ValueError('Local search budget exhausted (30 credits/day, 900/month UTC).')
        ident=store.db.execute("INSERT INTO provider_attempts(run_id,provider,query,started_at,status,reserved_credits) VALUES (?,'tavily',?,?,'reserved',1)",(run_id,query,stamp)).lastrowid
        store.db.commit()
        return ident
    except Exception:
        store.db.rollback()
        raise


def safe_result_url(value):
    if not isinstance(value,str) or len(value)>2048 or any(c.isspace() or ord(c)<32 for c in value):
        return None
    try:
        p=urlsplit(value)
        if p.scheme not in ('http','https') or not p.hostname or p.username or p.password or p.port not in (None,80,443):
            return None
        # Never fetch these links automatically; validate local/private literals nevertheless.
        import ipaddress
        if p.hostname.lower()=='localhost' or p.hostname.lower().endswith(('.local','.internal')):
            return None
        try:
            if not ipaddress.ip_address(p.hostname).is_global:
                return None
        except ValueError:
            pass
        query=urlencode([(k,v) for k,v in parse_qsl(p.query) if not k.lower().startswith('utm_') and k.lower() not in ('fbclid','gclid')])
        return urlunsplit((p.scheme,p.netloc.lower(),p.path,query,''))
    except ValueError:
        return None


NAME=re.compile(r"\b([A-Z][A-Za-z0-9&’'.-]*(?:[ \t]+(?:[A-Z][A-Za-z0-9&’'.-]*|&|and|of)){0,4}[ \t]+(?:Construction|Contractors|Contracting|Builders|Mechanical|Roofing|Electrical|Plumbing|Concrete|Engineering|Industries)(?:[ \t]+(?:Company|Group|Services|Inc\.?|LLC|Ltd\.?))?)\b")
GENERIC={'construction companies','construction company','general contractors','general contractor',
         'commercial construction','residential construction','construction jobs','electrical contractors',
         'mechanical contractors','roofing contractors','now hiring','job opportunities','career opportunities',
         'indeed','linkedin','facebook','careers','jobs','employment','apply now','dallas construction',
         'fort worth construction','texas construction','construction dive','enr','business wire'}
SIGNAL_WORDS={
    'hiring':r'\b(?:hiring|recruiting|vacanc(?:y|ies)|job openings|open positions|join our team)\b',
    'award':r'\b(?:awarded|contract award|selected contractor|selected as (?:the )?(?:general )?contractor)\b',
    'mobilization':r'\b(?:groundbreaking|breaking ground|mobilization|mobilisation|construction starts)\b',
    'expansion':r'\b(?:expansion|expanding|new office|new facility|opens (?:a |its )?new)\b',
}


def company_candidates(title,snippet,requested_signal):
    """Conservative rule extraction, explicitly unverified. No publisher/domain-to-company inference."""
    text=title+'\n'+snippet
    signal_matches=[k for k,p in SIGNAL_WORDS.items() if re.search(p,text,re.I)]
    if requested_signal!='all' and requested_signal not in signal_matches:
        return [],signal_matches
    if not signal_matches:
        return [],[]
    if re.search(r'\b(?:not|no longer)\s+(?:currently\s+)?(?:hiring|recruiting)\b',text,re.I) and requested_signal=='hiring':
        return [],signal_matches
    found=[]
    for match in NAME.finditer(text):
        name=re.sub(r'^(?:The|About|Careers at|Hiring at)\s+','',match[1]).strip()
        local=text[max(0,match.start()-100):min(len(text),match.end()+220)]
        # A company mention far from a signal is not enough to attach another firm's event to it.
        nearby=[s for s in signal_matches if re.search(SIGNAL_WORDS[s],local,re.I)]
        if nearby and (requested_signal=='all' or requested_signal in nearby):
            found.append((name,local))
    # Explicit subject predicates also cover company brands without a trade suffix.
    predicate=re.compile(r"\b([A-Z][A-Za-z0-9&’'.-]*(?:[ \t]+(?:[A-Z][A-Za-z0-9&’'.-]*|&|and)){0,4})\s+(?:(?:is|are)\s+(?:now\s+)?(?:hiring|recruiting)|(?:has been|was)\s+awarded|is\s+expanding)\b")
    for match in predicate.finditer(text):
        name=match[1].strip()
        if name.lower() not in {'we','they','our team','the company','this company'}:
            local=text[max(0,match.start()-20):min(len(text),match.end()+200)]
            if requested_signal=='all' or re.search(SIGNAL_WORDS[requested_signal],local,re.I):
                found.append((name,local))
    # Careers titles can identify brands without an industry suffix, e.g. "Careers | TDIndustries".
    if requested_signal in ('all','hiring') and 'hiring' in signal_matches:
        m=re.search(r'^(?:Careers|Jobs|Job openings|Join our team)\s*(?:at\s+|[|–—:-]\s*)([A-Z][\w &’\'.-]{2,70})$',title,re.I)
        if m and re.search(r'construction|contractor|mechanical|roofing|plumbing|electrical',snippet,re.I):
            found.append((m[1].strip(),text[:500]))
    output,seen=[],set()
    for name,evidence in found:
        normalized=re.sub(r'[^a-z0-9]','',name.lower())
        if name.lower() in GENERIC or len(name)>100 or normalized in seen:
            continue
        if re.match(r'^(?:top|best|find|hiring|jobs|careers|local|new|search)\b',name,re.I):
            continue
        seen.add(normalized)
        output.append({'name':name,'identity_key':normalized,'evidence_excerpt':evidence[:500],
            'status':'unverified_company_candidate','method':'company_name_near_signal_text'})
    return output[:10],signal_matches


def save_results(store,run_id,body,response,signal):
    for item in response.get('results',[])[:10]:
        if not isinstance(item,dict):
            continue
        url=safe_result_url(item.get('url'))
        if not url:
            continue
        title=str(item.get('title') or '')[:500]
        snippet=str(item.get('content') or '')[:6000]
        # Company identity is deliberately left for structured LLM classification. The legacy
        # regex remains available only for the old-vs-new evaluation of already stored results.
        text=title+'\n'+snippet
        signals=[k for k,p in SIGNAL_WORDS.items() if re.search(p,text,re.I)]
        _,places=classify(title+'\n'+snippet)
        stamp=str(item.get('published_date') or '')[:120] or None
        # Persist index snippets distinctly from fetched originals. Do not overwrite crawler documents.
        with store.db:
            store.db.execute('INSERT OR IGNORE INTO discovery_results(run_id,url,title,snippet,provider_date,companies_json,signals_json,places_json,query) VALUES (?,?,?,?,?,?,?,?,?)',
                (run_id,url,title,snippet,stamp,'[]',json.dumps(signals),json.dumps(places),body['query']))


def execute(store,run,config,key,transport=request_search):
    requests=json.loads(config['requests_json'])
    status,note='completed',None
    for body in requests:
        if store.rows('SELECT status FROM research_runs WHERE id=?',(run['id'],))[0]['status']=='stopping':
            return 'cancelled','Stopped by user. Search results retained.'
        attempt=reserve_search(store,run['id'],body['query'])
        try:
            response=transport(body,key)
            if not isinstance(response,dict) or not isinstance(response.get('results'),list):
                raise ValueError('Search provider returned an invalid result format')
            save_results(store,run['id'],body,response,run['signal'])
            usage=response.get('usage',{})
            credits=usage.get('credits') if isinstance(usage,dict) else None
            credits=credits if isinstance(credits,(int,float)) and 0<=credits<10000 else None
            with store.db:
                store.db.execute("UPDATE provider_attempts SET status='completed',reported_credits=? WHERE id=?",(credits,attempt))
        except Exception as exc:
            # Do not persist raw provider bodies, request headers, credentials or exception URLs.
            message=str(exc) if isinstance(exc,ValueError) else 'Search request failed: '+type(exc).__name__
            message=message.replace(key,'[redacted]') if key else message
            with store.db:
                store.db.execute("UPDATE provider_attempts SET status='failed',note=? WHERE id=?",(message[:300],attempt))
            return 'failed',message[:300]
        if credits is not None and credits>1:
            return 'completed_with_gaps','Provider reported more than the reserved credit. Further requests stopped for review.'
    return status,note


def details(store,ident):
    run=store.rows('SELECT * FROM research_runs WHERE id=?',(ident,))
    config=store.rows('SELECT * FROM discovery_config WHERE run_id=?',(ident,))
    if not run or not config:
        raise ValueError('Unknown company discovery run')
    rows=store.rows("""SELECT d.*,c.status AS classification_status,c.model AS classification_model,
      c.classification_json,c.score,c.score_json,c.error AS classification_error
      FROM discovery_results d LEFT JOIN llm_classifications c ON c.result_id=d.id
      WHERE d.run_id=? ORDER BY d.id""",(ident,))
    companies={}
    unresolved=[]
    for row in rows:
        row['legacy_companies']=json.loads(row['companies_json'])
        row['companies']=[]
        row['signals']=json.loads(row['signals_json'])
        row['places']=json.loads(row['places_json'])
        row['classification']=json.loads(row['classification_json']) if row['classification_json'] else None
        row['score_detail']=json.loads(row['score_json']) if row['score_json'] else None
        if row['classification_status']=='completed':
            classification=row['classification']
            score=row['score_detail'] or score_classification(classification)
            if score['passes']:
                name=classification['company_name']
                normalized=re.sub(r'[^a-z0-9]','',name.lower())
                row['companies']=[{'name':name,'identity_key':normalized,
                    'evidence_excerpt':classification.get('evidence_summary') or row['snippet'][:500],
                    'status':'scored_lead_candidate','method':'llm_structured_classification',
                    'classification':classification,'score':score}]
        if not row['companies']:
            unresolved.append(row)
        for company in row['companies']:
            group=companies.setdefault(company['identity_key'],dict(company,evidence=[]))
            group['evidence'].append(row)
    return dict(run=run[0],config=config[0],companies=list(companies.values()),unresolved=unresolved,
        result_count=len(rows), classified_count=sum(r['classification_status']=='completed' for r in rows),
        pending_classification=sum(not r['classification_status'] for r in rows),
        attempts=store.rows('SELECT * FROM provider_attempts WHERE run_id=? ORDER BY id',(ident,)))


def flag_candidate(store,result_id,identity_key):
    rows=store.rows("""SELECT d.*,c.status AS classification_status,c.classification_json,c.score_json
      FROM discovery_results d LEFT JOIN llm_classifications c ON c.result_id=d.id WHERE d.id=?""",(result_id,))
    if not rows:
        raise ValueError('Unknown discovery result')
    row=rows[0]
    if row['classification_status']!='completed' or not row['classification_json']:
        raise ValueError('This result has not been classified')
    classification=json.loads(row['classification_json'])
    score=json.loads(row['score_json']) if row['score_json'] else score_classification(classification)
    name=classification.get('company_name')
    normalized=re.sub(r'[^a-z0-9]','',name.lower()) if name else ''
    if identity_key!=normalized or not score['passes']:
        raise ValueError('This result does not meet the lead threshold')
    # Copy the search excerpt into an evidence document only when flagged, under a distinct provenance URL.
    document_id=store.ingest(None,'urn:leadintel:discovery-result:'+str(row['id']),row['title'],
        'Public search-index excerpt; original not fetched.\nSource URL: '+row['url']+'\n\n'+row['snippet'],
        signals=json.loads(row['signals_json']),geography=json.loads(row['places_json']),access_method='tavily_search_excerpt')
    with store.db:
        store.db.execute('UPDATE discovery_results SET document_id=? WHERE id=?',(document_id,result_id))
    reason=(classification.get('evidence_summary') or 'Structured classification passed the lead threshold')
    return store.flag(document_id,name,reason+' Verify the original source, company identity, geography, timing and apparel relevance.')
