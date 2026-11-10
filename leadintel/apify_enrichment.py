"""Manual, score-gated Apify evidence enrichment for qualified discovery results."""
import json
import os
import urllib.error
import urllib.request
from urllib.parse import quote, urlencode, urlsplit

from .llm_classifier import PASS_SCORE
from .store import now

ACTOR = 'apify~website-content-crawler'
MAX_CHARGE_USD = 0.25


class ApifyConnection:
    def __init__(self):
        self._token=None

    def key(self):
        return self._token or os.environ.get('APIFY_API_TOKEN','').strip()

    def configure(self,value):
        value=value.strip() if isinstance(value,str) else ''
        if not 20<=len(value)<=512 or any(c.isspace() for c in value):
            raise ValueError('Enter a valid Apify API token')
        self._token=value

    def clear(self):
        self._token=None


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):
        raise ValueError('Apify redirect refused')


def request_apify(body,token):
    params=urlencode({'timeout':120,'maxItems':5,'maxTotalChargeUsd':MAX_CHARGE_USD,
                      'format':'json','clean':'true','limit':5})
    url='https://api.apify.com/v2/actors/'+quote(ACTOR,safe='~')+'/run-sync-get-dataset-items?'+params
    request=urllib.request.Request(url,data=json.dumps(body).encode('utf-8'),
        headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'},method='POST')
    try:
        with urllib.request.build_opener(NoRedirect()).open(request,timeout=150) as response:
            raw=response.read(5_000_001)
            if len(raw)>5_000_000:
                raise ValueError('Apify response exceeded size limit')
            payload=json.loads(raw)
        if not isinstance(payload,list):
            raise ValueError('Apify returned an invalid result format')
        return payload
    except urllib.error.HTTPError as exc:
        messages={401:'Apify rejected the API token.',403:'Apify denied this Actor run.',
                  408:'Apify enrichment timed out.',429:'Apify rate or account limit reached.'}
        raise ValueError(messages.get(exc.code,'Apify returned HTTP '+str(exc.code))) from None
    except (urllib.error.URLError,OSError):
        raise ValueError("Could not reach Apify. Check this computer's network access.") from None


def eligible_result(store,result_id):
    rows=store.rows("""SELECT d.*,c.classification_json,c.score,c.score_json
      FROM discovery_results d JOIN llm_classifications c ON c.result_id=d.id
      WHERE d.id=? AND c.status='completed'""",(result_id,))
    if not rows:
        raise ValueError('Result has no completed LLM classification')
    row=rows[0]
    score=json.loads(row['score_json']) if row['score_json'] else {}
    if row['score']<PASS_SCORE or not score.get('passes'):
        raise ValueError('Apify enrichment requires a lead that passed the score threshold')
    row['classification']=json.loads(row['classification_json'])
    return row


def enrichment_plan(store,result_id,mode):
    if mode not in ('project','company'):
        raise ValueError('Choose project or company enrichment')
    row=eligible_result(store,result_id)
    classification=row['classification']
    if mode=='project':
        target=row['url']
        body={'startUrls':[{'url':target}],'crawlerType':'cheerio','maxCrawlPages':1,
              'maxCrawlDepth':0,'saveHtml':False,'saveMarkdown':True,'maxResults':1}
    else:
        if not classification.get('source_is_company_owned') or not classification.get('company_website'):
            raise ValueError('A company-site crawl requires a passing result from the company’s own website')
        target=classification['company_website']
        root=target.rstrip('/')
        body={'startUrls':[{'url':target}],'crawlerType':'cheerio','maxCrawlPages':5,
              'maxCrawlDepth':2,'saveHtml':False,'saveMarkdown':True,
              'includeUrlGlobs':[root+'/**/careers**',root+'/**/jobs**',root+'/**/projects**',root+'/**/news**']}
    return {'result':row,'mode':mode,'target_url':target,'actor':ACTOR,'input':body,
            'max_items':5,'max_total_charge_usd':MAX_CHARGE_USD}


def save_items(store,run_id,items):
    saved=0
    for item in items[:5]:
        if not isinstance(item,dict):
            continue
        url=str(item.get('url') or '')[:2048]
        parsed=urlsplit(url)
        if parsed.scheme not in ('http','https') or not parsed.hostname:
            continue
        title=str(item.get('title') or item.get('metadata',{}).get('title') or 'Enriched page')[:500]
        content=str(item.get('markdown') or item.get('text') or item.get('content') or '')[:50000]
        if not content.strip():
            continue
        with store.db:
            store.db.execute("INSERT OR IGNORE INTO apify_evidence(run_id,url,title,content,created_at) VALUES (?,?,?,?,?)",
                (run_id,url,title,content,now()))
        saved+=1
    return saved


def run_enrichment(store,run_id,token,transport=request_apify):
    rows=store.rows('SELECT * FROM apify_runs WHERE id=?',(run_id,))
    if not rows:
        raise ValueError('Unknown Apify enrichment run')
    run=rows[0]
    plan=enrichment_plan(store,run['result_id'],run['mode'])
    items=transport(plan['input'],token)
    if not isinstance(items,list):
        raise ValueError('Apify returned an invalid result format')
    count=save_items(store,run_id,items)
    return count
