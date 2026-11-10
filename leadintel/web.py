"""Loopback-only operator dashboard. Not a production web server."""
import html
import json
import secrets
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlencode, urlsplit

from .store import Store
from .research import ResearchController
from .research_ui import controls, progress
from .discovery_ui import home, result_page, classification_page
from .llm_classifier import record_lead_review
from .discovery import flag_candidate

STYLE = """body{font:16px system-ui;background:#f3f6fa;color:#172438;margin:0}
main{max-width:1100px;margin:auto;padding:30px}h1{font-size:30px;margin-bottom:6px}
.muted{color:#56667d}nav{display:flex;gap:18px;margin:24px 0}a{color:#1465ba}
.card{background:white;border:1px solid #dce3ee;border-radius:12px;padding:20px;margin:16px 0}
input,select,button{font:inherit;padding:10px;border:1px solid #bcc8da;border-radius:6px}
input{max-width:90%}button{background:#1465ba;color:white;cursor:pointer}table{width:100%;border-collapse:collapse}
td,th{text-align:left;padding:10px;border-bottom:1px solid #e2e8f0;overflow-wrap:anywhere}
.tag{background:#e6eef8;padding:4px 8px;border-radius:5px;display:inline-block}
pre{white-space:pre-wrap;overflow-wrap:anywhere}.notice{background:#fff3cc;padding:14px;border-radius:8px}
label{display:inline-block;margin:5px}code{overflow-wrap:anywhere}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:12px}
.grid label{display:flex;flex-direction:column;gap:8px}.grid .source{padding:14px;background:#f3f6fa;border-radius:8px}.source label{display:flex;flex-direction:row;align-items:flex-start;gap:12px}.source input{margin-top:5px}.source small{display:block;overflow-wrap:anywhere;color:#56667d;margin-top:6px}.source-direct{display:inline-block;margin:12px 0 0 30px;font-weight:700}
.wide{display:flex;flex-direction:column;gap:8px;width:95%}input,select{box-sizing:border-box}
.eyebrow{font-size:12px;letter-spacing:1.5px;color:#56667d;margin-top:32px}h2{font-size:28px}
.stats strong{font-size:30px}.stats .card{margin:12px 0}button:disabled{background:#718096;cursor:default}summary{cursor:pointer}
.query-list{max-height:420px;overflow:auto;border:1px solid #dce3ee;border-radius:8px;margin:16px 0}
.query-option{display:flex;align-items:flex-start;gap:12px;padding:14px;margin:0;border-bottom:1px solid #e2e8f0;cursor:pointer;overflow-wrap:anywhere}
.query-option input{flex-shrink:0;width:18px;height:18px;accent-color:#1465ba}
.query-option small{display:block;color:#56667d;margin-top:4px}.query-option:has(input:checked){background:#eaf3ff}
.secondary{background:white;color:#1465ba}#query-count{font-weight:600}.picker-tools button{margin-bottom:6px}
.link-block{position:relative;margin:16px 0;overflow-wrap:anywhere}
.link-domain{display:block;color:#56667d;font-size:13px;margin-top:4px}
.link-preview{display:none;position:absolute;left:0;top:100%;z-index:20;width:max-content;max-width:min(260px,calc(100vw - 100px));box-sizing:border-box;background:#fff;border:1px solid #dce3ee;border-radius:6px;padding:8px 10px;box-shadow:0 3px 12px #17243820;color:#172438;overflow-wrap:anywhere;font-size:12px;line-height:1.4;pointer-events:none}
.link-preview strong{display:block;font-weight:500;margin-bottom:3px}
.link-preview span{display:block;color:#56667d}
.link-block.preview-open .link-preview{display:block}.alternatives{margin:10px 0;padding:10px 14px;background:#f3f6fa;border-radius:8px}
.alternatives summary{color:#1465ba}.destination-link:focus-visible{outline:3px solid #1465ba;outline-offset:3px}
.source-icon{display:inline-flex;align-items:center;justify-content:center;width:22px;height:22px;border-radius:50%;background:#1465ba;color:white;font-weight:700;text-decoration:none}.classification-title .link-block{margin:0 0 18px}.classification-title .destination-link{font-size:18px;font-weight:700;line-height:1.45}
.lead-actions{display:flex;flex-wrap:wrap;gap:10px;align-items:center;margin-top:14px}.lead-actions form,.lead-actions p{margin:0}.lead-actions button{height:100%}
.contractor-status:not(:empty){margin-top:12px}.contractor-progress,.contractor-error,.contractor-result{padding:12px 14px;border-radius:8px}.contractor-progress{background:#eaf3ff;color:#123f71}.contractor-progress:before{content:'';display:inline-block;width:12px;height:12px;margin-right:9px;border:2px solid #7aa9da;border-top-color:#1465ba;border-radius:50%;animation:spin .8s linear infinite}.contractor-error{background:#ffe8e8;color:#812222}.contractor-result{background:#e9f7ee}.contractor-result>strong,.contractor-result>span{display:block}.contractor-result>span{font-size:13px;color:#486152;margin-top:3px}.contractor-result details{margin-top:9px}@keyframes spin{to{transform:rotate(360deg)}}
@media(max-width:600px){main{padding:16px}nav{gap:12px;flex-wrap:wrap}.grid{grid-template-columns:1fr}}"""

PICKER_SCRIPT = """const picker = document.getElementById('query-picker');
document.querySelectorAll('.link-block').forEach(block => {
  const link = block.querySelector('.destination-link');
  let hovered = false, focused = false, dismissed = false;
  const update = () => {
    const open = !dismissed && (hovered || focused);
    block.classList.toggle('preview-open', open);
  };
  link.addEventListener('pointerenter', event => { hovered = event.pointerType !== 'touch'; dismissed = false; update(); });
  link.addEventListener('pointerleave', () => { hovered = false; update(); });
  link.addEventListener('focus', () => { focused = link.matches(':focus-visible'); dismissed = false; update(); });
  link.addEventListener('blur', () => { focused = false; update(); });
  link.addEventListener('keydown', event => {
    if (event.key === 'Escape') { dismissed = true; update(); }
  });
});
if (picker) {
  let filtersChanged = false;
  let connectionReady = picker.querySelector('#run-queries').dataset.ready === '1';
  function setupPicker() {
    const filters = document.getElementById('query-filters');
    const form = document.getElementById('query-picker');
    const boxes = [...form.querySelectorAll('input[name="query_ids"]')];
    const count = form.querySelector('#query-count');
    const run = form.querySelector('#run-queries');
    const update = () => {
      const n = boxes.filter(b => b.checked).length;
      boxes.forEach(b => b.disabled = n >= 10 && !b.checked);
      count.textContent = filtersChanged ? 'Filters changed. Click Update query list before searching.' : `${n} / 10 selected · ${n} Basic search credits · up to ${n * 10} web results before deduplication`;
      run.disabled = filtersChanged || !connectionReady || n === 0;
    };
    filters.addEventListener('input', () => { filtersChanged = true; update(); });
    form.querySelector('.picker-tools').hidden = false;
    boxes.forEach(b => b.addEventListener('change', update));
    form.querySelector('#select-ten').addEventListener('click', () => { boxes.forEach((b, i) => b.checked = i < 10); update(); });
    form.querySelector('#clear-queries').addEventListener('click', () => { boxes.forEach(b => b.checked = false); update(); });
    form.addEventListener('submit', event => { const n=boxes.filter(b=>b.checked).length; if(filtersChanged || n<1 || n>10 || !connectionReady) { event.preventDefault(); update(); } });
    filters.addEventListener('submit', async event => {
      event.preventDefault();
      const button=filters.querySelector('button'), status=filters.querySelector('#filter-status');
      const params = new URLSearchParams(new FormData(filters));
      const snapshot = params.toString();
      const selected = new Map(boxes.filter(b => b.checked).map(b => [b.value, b.parentElement.querySelector('span').childNodes[0].textContent]));
      button.disabled=true; status.textContent='Updating query list…';
      try {
        const response=await fetch('/?'+snapshot,{cache:'no-store'});
        if(!response.ok) throw new Error('Could not update the query list. Check the selected filters.');
        const page=new DOMParser().parseFromString(await response.text(),'text/html');
        const nextFilters=page.querySelector('#query-filters'), nextPicker=page.querySelector('#query-picker');
        if(!nextFilters || !nextPicker) throw new Error('The query list response was incomplete.');
        if(new URLSearchParams(new FormData(filters)).toString() !== snapshot) throw new Error('Filters changed while updating. Click Update query list again.');
        let kept=0;
        nextPicker.querySelectorAll('input[name="query_ids"]').forEach(box=>{
          if(selected.get(box.value) === box.parentElement.querySelector('span').childNodes[0].textContent) { box.checked=true; kept++; }
        });
        filters.replaceWith(nextFilters); form.replaceWith(nextPicker);
        filtersChanged=false;
        nextFilters.querySelector('#filter-status').textContent=`Query list updated. ${kept} selection(s) kept` + (selected.size>kept ? `; ${selected.size-kept} no longer matched the new filters.` : '.');
        setupPicker();
      } catch(error) { status.textContent=error.message || 'Could not update the query list.'; }
      finally { button.disabled=false; }
    });
    update();
  }
  setupPicker();
  const connect = document.getElementById('search-connect-form');
  connect.addEventListener('submit', async event => {
    event.preventDefault();
    const button=connect.querySelector('button'), status=connect.querySelector('#connection-status');
    button.disabled=true; status.textContent='Connecting Tavily…';
    try {
      const response=await fetch(connect.action,{method:'POST',body:new URLSearchParams(new FormData(connect)),headers:{'X-Requested-With':'SearchConnection'}});
      const data=await response.json();
      if(!response.ok) throw new Error(data.error || 'Could not connect Tavily.');
      connectionReady=!!data.ready;
      connect.querySelector('input[name="api_key"]').value='';
      document.querySelector('#connection summary').textContent='Search connection · key provided (validated when searching)';
      document.getElementById('search-connection-notice')?.remove();
      document.getElementById('search-connection-hint')?.remove();
      status.textContent=data.ready ? 'Key saved for this session. It will be validated when you search.' : 'Key saved. A search is already running.';
      const run=document.getElementById('run-queries');
      run.dataset.ready=data.ready ? '1' : '0';
      run.disabled=filtersChanged || !connectionReady || !document.querySelector('#query-picker input[name="query_ids"]:checked');
    } catch(error) { status.textContent=error.message || 'Could not connect Tavily.'; }
    finally { button.disabled=false; }
  });
}

const contractorText = (parent, tag, text) => {
  const node = document.createElement(tag); node.textContent = text; parent.appendChild(node); return node;
};
const showContractor = (box, data) => {
  box.replaceChildren();
  if (data.status === 'queued' || data.status === 'running') {
    const line = contractorText(box, 'div', data.status === 'queued' ? 'Contractor lookup queued…' : 'Checking ranked sources for the general contractor…');
    line.className = 'contractor-progress'; return;
  }
  if (data.status === 'failed' || data.status === 'interrupted') {
    const line = contractorText(box, 'div', 'Contractor lookup stopped: ' + (data.error || data.status));
    line.className = 'contractor-error'; return;
  }
  if (data.status !== 'completed') return;
  const result = document.createElement('div'); result.className = 'contractor-result'; box.appendChild(result);
  const status = data.contractor_status || ({confirmed:'confirmed', probable:'likely'}[data.confidence] || 'unresolved');
  const labels = {confirmed:'Verified general contractor', pending_award:'Proposed contractor (decision pending)', likely:'Likely general contractor', unresolved:'General contractor'};
  const statusLabels = {confirmed:'Final award or role verified', pending_award:'Awaiting final approval', likely:'Credible evidence; final proof not found', unresolved:'Unresolved'};
  contractorText(result, 'strong', labels[status] + ': ' + (data.contractor_name || 'Unresolved'));
  contractorText(result, 'span', 'Status: ' + statusLabels[status]);
  const more = document.createElement('details'); result.appendChild(more);
  contractorText(more, 'summary', 'More information');
  if (data.developer_name) contractorText(more, 'p', 'Developer: ' + data.developer_name);
  if (data.explanation) contractorText(more, 'p', data.explanation);
  if ((data.methods_attempted || []).length) contractorText(more, 'p', 'Search path: ' + data.methods_attempted.map(x => x.replaceAll('_', ' ')).join(' → '));
  (data.evidence || []).forEach(source => {
    const link = document.createElement('a'); link.href = source.url; link.target = '_blank'; link.rel = 'noopener noreferrer';
    link.textContent = source.title || 'Supporting source'; more.appendChild(link);
    try { contractorText(more, 'span', new URL(source.url).hostname); } catch (_) {}
  });
};
const pollContractor = async (id, box, button) => {
  for (let attempt = 0; attempt < 80; attempt += 1) {
    const response = await fetch('/contractor/status?id=' + encodeURIComponent(id), {cache:'no-store'});
    const data = await response.json(); showContractor(box, data);
    if (!['queued','running'].includes(data.status)) { button.disabled = false; return; }
    await new Promise(resolve => setTimeout(resolve, 1500));
  }
  showContractor(box, {status:'failed',error:'The lookup is taking longer than expected. You can continue using the page and try again later.'});
  button.disabled = false;
};
document.querySelectorAll('.contractor-form').forEach(form => {
  form.addEventListener('submit', async event => {
    event.preventDefault();
    const id = form.dataset.resultId, button = form.querySelector('button');
    const box = document.getElementById('contractor-status-' + id);
    button.disabled = true; showContractor(box, {status:'queued'});
    try {
      const response = await fetch(form.action, {method:'POST',body:new URLSearchParams(new FormData(form)),headers:{'X-Requested-With':'ContractorLookup'}});
      const data = await response.json();
      if (data.target) { button.disabled = false; box.replaceChildren(); window.location.assign(data.target); return; }
      if (!response.ok) throw new Error(data.error || 'Contractor lookup could not start.');
      await pollContractor(id, box, button);
    } catch (error) {
      showContractor(box, {status:'failed',error:error.message || 'Contractor lookup could not start.'}); button.disabled = false;
    }
  });
});
const showContacts = (box, data) => {
  box.replaceChildren();
  if (['queued','running'].includes(data.status)) {
    const line = contractorText(box, 'div', data.status === 'queued' ? 'Contact lookup queued…' : 'Finding operational contacts and professional emails…');
    line.className = 'contractor-progress'; return;
  }
  if (data.status === 'failed' || data.status === 'interrupted') {
    const line = contractorText(box, 'div', 'Contact lookup stopped: ' + (data.error || data.status)); line.className = 'contractor-error'; return;
  }
  if (data.status !== 'completed') return;
  const result = document.createElement('div'); result.className = 'contractor-result'; box.appendChild(result);
  contractorText(result, 'strong', 'Contacts for ' + data.company);
  if (data.note) contractorText(result, 'span', data.note);
  if (!(data.contacts || []).length) { contractorText(result, 'p', (data.note || '').startsWith('AI role review:') ? 'No contacts passed the AI role review.' : 'Apify returned no contacts. The reason may be the filters, limited coverage, or an issue the provider did not report.'); return; }
  data.contacts.forEach(contact => {
    const details = document.createElement('details'); result.appendChild(details);
    contractorText(details, 'summary', contact.name + ' · ' + (contact.title || 'Role unavailable') + (contact.relevance == null ? '' : ' · ' + contact.relevance + '/100'));
    if (contact.rank_reason) contractorText(details, 'p', contact.rank_reason);
    const link = document.createElement('a'); link.href = contact.linkedin_url; link.target = '_blank'; link.rel = 'noopener noreferrer'; link.textContent = 'LinkedIn profile'; details.appendChild(link);
    contractorText(details, 'p', (contact.emails || []).length ? 'Professional email: ' + contact.emails.join(', ') + (contact.provider_verified ? ' · provider-validated' : ' · provider-found') : 'No email returned by the provider.');
  });
};
const pollContacts = async (id, box, button) => {
  for (let attempt = 0; attempt < 240; attempt += 1) {
    const response = await fetch('/contacts/status?id=' + encodeURIComponent(id), {cache:'no-store'});
    const data = await response.json(); showContacts(box, data);
    if (!['queued','running'].includes(data.status)) { button.disabled = false; return; }
    await new Promise(resolve => setTimeout(resolve, 1500));
  }
  showContacts(box, {status:'failed',error:'The lookup is taking longer than expected. You can continue using the page and check later.'}); button.disabled = false;
};
document.querySelectorAll('.contact-form').forEach(form => {
  form.addEventListener('submit', async event => {
    event.preventDefault(); const id=form.dataset.resultId, button=form.querySelector('button');
    const box=document.getElementById('contact-status-' + id); button.disabled=true; showContacts(box,{status:'queued'});
    try {
      const response=await fetch(form.action,{method:'POST',body:new URLSearchParams(new FormData(form)),headers:{'X-Requested-With':'ContactLookup'}});
      const data=await response.json();
      if (data.target) { button.disabled=false; box.replaceChildren(); window.location.assign(data.target); return; }
      if (!response.ok) throw new Error(data.error || 'Contact lookup could not start.');
      await pollContacts(id,box,button);
    } catch (error) { showContacts(box,{status:'failed',error:error.message || 'Contact lookup could not start.'}); button.disabled=false; }
  });
});
document.querySelectorAll('.apify-form').forEach(form => {
  form.addEventListener('submit', async event => {
    event.preventDefault();
    const button = form.querySelector('button');
    const box = document.getElementById('apify-status-' + form.dataset.resultId + '-' + form.dataset.mode);
    const show = (message, type) => { box.replaceChildren(); const line=contractorText(box,'div',message); line.className=type; };
    button.disabled=true; show('Starting Apify enrichment…','contractor-progress');
    try {
      const response=await fetch(form.action,{method:'POST',body:new URLSearchParams(new FormData(form)),headers:{'X-Requested-With':'ApifyLookup'}});
      const data=await response.json();
      if (!response.ok) throw new Error(data.error || 'Could not start enrichment.');
      for (let attempt=0; attempt<200; attempt++) {
        const res=await fetch('/apify/status?id='+encodeURIComponent(data.run_id),{cache:'no-store'});
        const state=await res.json();
        if (!res.ok) throw new Error(state.error || 'Could not read enrichment status.');
        if (['queued','running'].includes(state.status)) {
          show('Apify is collecting project evidence… You can continue scrolling.','contractor-progress');
          await new Promise(resolve=>setTimeout(resolve,1500)); continue;
        }
        if (state.status!=='completed') throw new Error(state.note || state.status);
        show(state.note || 'Enrichment completed.','contractor-result');
        state.evidence.forEach(item=>{
          const details=document.createElement('details'); box.appendChild(details);
          contractorText(details,'summary',item.title || 'Evidence page');
          contractorText(details,'p',item.content.slice(0,1500));
          if (item.url.startsWith('https://') || item.url.startsWith('http://')) { const a=document.createElement('a'); a.href=item.url; a.target='_blank'; a.rel='noopener noreferrer'; a.textContent='Open source'; details.appendChild(a); }
        });
        return;
      }
      throw new Error('Still running. Refresh later to check the saved result.');
    } catch(error) { show('Apify enrichment: '+(error.message || 'Could not complete lookup.'),'contractor-error'); }
    finally { button.disabled=false; }
  });
});
"""


def esc(value):
    return html.escape(str(value),quote=True)


def handler(db_path, controller=None):
    token=secrets.token_urlsafe(32)
    controller=controller or ResearchController(db_path)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def valid_host(self):
            return self.headers.get("Host") in ("127.0.0.1:"+str(self.server.server_port),
                                                 "localhost:"+str(self.server.server_port))

        def send_page(self, body, status=200, refresh=False):
            nonce=secrets.token_urlsafe(24)
            content=("<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
                     "<title>Lead intelligence · Research engine</title><style>"+STYLE+"</style></head><body><main>"
                     "<h1>Lead intelligence</h1><div class='muted'>Research engine prototype · local operator workspace</div>"
                     "<nav><a href='/'>Find companies</a><a href='/classification'>Classification review</a><a href='/monitor'>Monitor sources</a><a href='/search'>Saved evidence</a><a href='/leads'>Lead review</a></nav>"
                     +body+"</main><script nonce='"+nonce+"'>"+PICKER_SCRIPT+"</script></body></html>").encode()
            self.send_response(status)
            self.send_header("Content-Type","text/html; charset=utf-8")
            self.send_header("Content-Length",str(len(content)))
            self.send_header("Content-Security-Policy","default-src 'none'; connect-src 'self'; style-src 'unsafe-inline'; script-src 'nonce-"+nonce+"'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'")
            self.send_header("X-Content-Type-Options","nosniff")
            self.send_header("Cache-Control","no-store")
            if refresh:
                self.send_header("Refresh","3")
            self.end_headers()
            self.wfile.write(content)

        def send_json(self, value, status=200):
            content=json.dumps(value,ensure_ascii=False).encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type','application/json; charset=utf-8')
            self.send_header('Content-Length',str(len(content)))
            self.send_header('Cache-Control','no-store')
            self.send_header('X-Content-Type-Options','nosniff')
            self.end_headers()
            self.wfile.write(content)

        def do_GET(self):
            if not self.valid_host():
                self.send_error(403)
                return
            store=Store(db_path)
            try:
                p=urlsplit(self.path)
                q=parse_qs(p.query)
                refresh=False
                if p.path=="/":
                    body=home(store,token,controller.connection,controller.classifier_connection,q)
                elif p.path=="/classification":
                    body,refresh=classification_page(store,token,controller)
                elif p.path=="/contractor/status":
                    result_id=int(q.get('id',['0'])[0])
                    rows=store.rows('SELECT * FROM contractor_verifications WHERE result_id=?',(result_id,))
                    if not rows:
                        self.send_json({'status':'not_started'}); return
                    row=rows[0]
                    payload={'status':row['status'],'contractor_name':row['contractor_name'],
                      'developer_name':row['developer_name'],'confidence':row['confidence'],
                      'error':row['error'],'explanation':'','evidence':[]}
                    verified=json.loads(row['verification_json']) if row['verification_json'] else {}
                    payload['explanation']=verified.get('explanation') or ''
                    payload['methods_attempted']=verified.get('methods_attempted') or []
                    payload['contractor_status']=verified.get('contractor_status') or ({'confirmed':'confirmed','probable':'likely'}.get(row['confidence'],'unresolved'))
                    cited=set(verified.get('evidence_urls') or [])
                    payload['evidence']=[{'url':source['url'],'title':source['title']}
                      for source in store.rows('SELECT url,title FROM contractor_evidence WHERE result_id=? ORDER BY id',(result_id,))
                      if source['url'] in cited]
                    self.send_json(payload); return
                elif p.path=="/apify/status":
                    ident=int(q.get('id',['0'])[0])
                    rows=store.rows('SELECT status,note FROM apify_runs WHERE id=?',(ident,))
                    if not rows:
                        self.send_json({'error':'Unknown Apify run'},404); return
                    self.send_json({'status':rows[0]['status'],'note':rows[0]['note'],
                        'evidence':store.rows('SELECT title,url,content FROM apify_evidence WHERE run_id=? ORDER BY id',(ident,))}); return
                elif p.path=="/contacts/status":
                    result_id=int(q.get('id',['0'])[0])
                    rows=store.rows('SELECT * FROM contact_runs WHERE result_id=? ORDER BY id DESC LIMIT 1',(result_id,))
                    if not rows:
                        self.send_json({'status':'not_started'}); return
                    run=rows[0]
                    contacts=store.rows('SELECT * FROM lead_contacts WHERE run_id=? ORDER BY relevance DESC,name',(run['id'],))
                    for contact in contacts:
                        contact['emails']=json.loads(contact.pop('emails_json'))
                    self.send_json({'status':run['status'],'company':run['company'],'note':run['note'],
                                    'error':run['error'],'contacts':contacts}); return
                elif p.path=='/monitor':
                    body=controls(store,token)
                elif p.path=="/research/run":
                    ident=int(q.get('id',['0'])[0])
                    if store.rows('SELECT run_id FROM discovery_config WHERE run_id=?',(ident,)):
                        body,refresh=result_page(store,ident,token,controller)
                    else:
                        body,refresh=progress(store,ident,token)
                elif p.path=="/search":
                    term=q.get("q",[""])[0]
                    signal=q.get("signal",[""])[0]
                    geo=q.get("geography",[""])[0]
                    results=store.search(term,signal or None,geo or None)
                    def select(name, values, selected):
                        return "<select name='"+name+"'><option value=''>Any "+name+"</option>"+"".join("<option "+("selected " if v==selected else "")+"value='"+v+"'>"+v+"</option>" for v in values)+"</select>"
                    body="<div class='notice'>Results are research evidence. Geography tags are text mentions, not verified project locations. Demo records are explicitly labelled.</div>"
                    body+="<form class='card' method='get'><input name='q' placeholder='Search collected evidence' value='"+esc(term)+"'> "+select("signal",["award","hiring","mobilization","expansion"],signal)+" "+select("geography",["Dallas","Tarrant","Collin","Denton"],geo)+" <button>Search</button></form>"
                    body+="<p>"+str(len(results))+" results · searches only stored evidence; sends no network requests</p>"
                    for r in results:
                        body+="<article class='card'><span class='tag'>"+("SYNTHETIC DEMO" if r["is_demo"] else "UNVERIFIED EVIDENCE")+"</span><h2><a href='/evidence?id="+str(r["id"])+"'>"+esc(r["title"])+"</a></h2><p>"+esc(r["excerpt"])+"</p><p class='muted'>"+esc(r["url"])+"</p><p>Signals: "+esc(", ".join(r["signals"]))+" · Geography mentions: "+esc(", ".join(r["geography"]))+"</p></article>"
                    if not results:
                        body+="<div class='card'>No matching stored evidence. <a href='/'>Start a research run</a> to collect fresh pages.</div>"
                elif p.path=="/evidence":
                    ident=int(q.get("id",["0"])[0])
                    rows=store.rows("SELECT * FROM documents WHERE id=?", (ident,))
                    if not rows:
                        raise ValueError("Unknown evidence")
                    r=rows[0]
                    body="<article class='card'><h2>"+esc(r["title"])+"</h2><p>"+("SYNTHETIC DEMO · " if r["is_demo"] else "")+"Unverified evidence</p><p>Source: "+esc(r["url"])+"</p><p>Retrieved: "+esc(r["retrieved_at"])+"<br>Last checked: "+esc(r["checked_at"])+"<br>Reported publication date: "+esc(r["publication_date"] or "Unknown")+"<br>Event date: Unknown</p><pre>"+esc(r["body"])+"</pre></article>"
                    body+="<form class='card' method='post' action='/flag'><h2>Flag a potential lead</h2><p>This saves a candidate. It does not run the company/contact scraper.</p><input type='hidden' name='csrf' value='"+token+"'><input type='hidden' name='document_id' value='"+str(ident)+"'><label>Company <input name='company' required maxlength='200'></label><label>Evidence reason <input name='reason' required maxlength='2000'></label><button>Flag candidate</button></form>"
                elif p.path=="/leads":
                    body="<div class='notice'>Company/contact enrichment is queued only when qualification begins. The enrichment worker is not implemented yet.</div>"
                    for r in store.rows("SELECT * FROM leads ORDER BY id DESC"):
                        body+="<article class='card'><h2>"+esc(r["company"])+"</h2><span class='tag'>"+esc(r["status"])+"</span><p>"+esc(r["reason"])+"</p><a href='/evidence?id="+str(r["document_id"])+"'>Supporting evidence</a>"
                        if r["status"]=="flagged":
                            body+="<form method='post' action='/qualify'><input type='hidden' name='csrf' value='"+token+"'><input type='hidden' name='lead_id' value='"+str(r["id"])+"'><p><button>Begin qualification</button></p></form>"
                        body+="</article>"
                    body+="<div class='card'><h2>Qualification enrichment queue</h2><pre>"+esc(json.dumps(store.enrichment_tasks(),indent=2))+"</pre></div>"
                elif p.path=="/coverage":
                    body="<div class='card'><h2>Sources, jobs and request accounting</h2><p>Failures and pending work remain visible. Recurring monitoring is off.</p><pre>"+esc(json.dumps(store.coverage(),indent=2))+"</pre></div>"
                else:
                    self.send_error(404)
                    return
                self.send_page(body,refresh=refresh)
            except (ValueError,OverflowError) as exc:
                self.send_page("<p>"+esc(exc)+"</p>",400)
            finally:
                store.close()

        def do_POST(self):
            if not self.valid_host():
                self.send_error(403)
                return
            expected="http://"+self.headers.get("Host","")
            if self.headers.get("Origin") not in (None,expected):
                self.send_error(403)
                return
            try:
                ajax=self.headers.get('X-Requested-With') in ('ContractorLookup','ContactLookup','ApifyLookup','SearchConnection')
                size=int(self.headers.get("Content-Length","0"))
                if not 0<size<=8192:
                    raise ValueError("Request too large or empty")
                if self.headers.get("Content-Type","").split(";")[0]!="application/x-www-form-urlencoded":
                    raise ValueError("Form encoding required")
                data=parse_qs(self.rfile.read(size).decode("utf-8"))
                if not secrets.compare_digest(data.get("csrf",[""])[0],token):
                    self.send_error(403)
                    return
                store=Store(db_path)
                location='/leads'
                try:
                    if self.path=='/discover/connect':
                        controller.connection.configure(data['api_key'][0])
                        if ajax:
                            active=bool(store.rows("SELECT id FROM research_runs WHERE status IN ('queued','running','stopping')"))
                            self.send_json({'status':'connected','ready':not active},200); return
                        location='/classification' if data.get('return_to',[''])[0]=='classification' else '/'
                    elif self.path=='/classifier/connect':
                        controller.classifier_connection.configure(data['api_key'][0])
                        location='/classification'
                    elif self.path=='/classification/start':
                        controller.start_classification(int(data.get('limit',['500'])[0]))
                        location='/classification'
                    elif self.path=='/classification/review':
                        record_lead_review(store,int(data['result_id'][0]),data['decision'][0],data.get('note',[''])[0])
                        location='/classification'
                    elif self.path=='/apify/connect':
                        controller.apify_connection.configure(data['api_key'][0])
                        location='/classification'
                    elif self.path=='/apify/start':
                        result_id=int(data['result_id'][0])
                        if not controller.apify_connection.key():
                            if ajax:
                                self.send_json({'status':'failed','error':'Connect your Apify token in the connection section first.'},409); return
                            location='/classification#apify-connection'
                        else:
                            ident=controller.start_apify(result_id,data['mode'][0])
                            if ajax:
                                self.send_json({'status':'queued','run_id':ident},202); return
                            run=store.rows('SELECT run_id FROM discovery_results WHERE id=?',(result_id,))
                            location='/classification' if data.get('return_to',[''])[0]=='classification' else '/research/run?id='+str(run[0]['run_id'])
                    elif self.path=='/contractor/verify':
                        result_id=int(data['result_id'][0])
                        if not controller.connection.key():
                            if ajax:
                                self.send_json({'status':'needs_connection','target':'/classification#search-connection'},409); return
                            location='/classification#search-connection'
                        elif not controller.classifier_connection.key():
                            if ajax:
                                self.send_json({'status':'needs_connection','target':'/classification#classifier-connection'},409); return
                            location='/classification#classifier-connection'
                        else:
                            controller.start_contractor_verification(result_id)
                            if ajax:
                                self.send_json({'status':'queued','result_id':result_id},202); return
                            run=store.rows('SELECT run_id FROM discovery_results WHERE id=?',(result_id,))
                            location='/classification' if data.get('return_to',[''])[0]=='classification' else '/research/run?id='+str(run[0]['run_id'])
                    elif self.path=='/contacts/start':
                        result_id=int(data['result_id'][0])
                        if not controller.apify_connection.key():
                            if ajax:
                                self.send_json({'status':'needs_connection','target':'/classification#apify-connection'},409); return
                            location='/classification#apify-connection'
                        else:
                            controller.start_contact_enrichment(result_id)
                            if ajax:
                                self.send_json({'status':'queued','result_id':result_id},202); return
                            location='/classification'
                    elif self.path=='/discover/start':
                        ident=controller.start_discovery(data)
                        location='/research/run?id='+str(ident)
                    elif self.path=='/discover/flag':
                        flag_candidate(store,int(data['result_id'][0]),data['identity_key'][0])
                    elif self.path=="/research/start":
                        ident=controller.start(data)
                        location='/research/run?id='+str(ident)
                    elif self.path=="/research/stop":
                        ident=int(data['run_id'][0])
                        controller.stop(ident)
                        location='/research/run?id='+str(ident)
                    elif self.path=="/flag":
                        store.flag(int(data["document_id"][0]),data["company"][0],data["reason"][0])
                    elif self.path=="/qualify":
                        store.begin_qualification(int(data["lead_id"][0]))
                    else:
                        self.send_error(404)
                        return
                finally:
                    store.close()
                self.send_response(303)
                self.send_header("Location",location)
                self.end_headers()
            except (ValueError,KeyError,UnicodeError) as exc:
                message=str(exc) if isinstance(exc,ValueError) else 'Invalid form submission'
                if self.headers.get('X-Requested-With') in ('ContractorLookup','ContactLookup','ApifyLookup','SearchConnection'):
                    self.send_json({'status':'failed','error':message},400)
                else:
                    self.send_page("<p>"+esc(message)+"</p><p><a href='/'>Return to research controls</a></p>",400)
    return Handler


def serve(db_path, port=8765):
    controller=ResearchController(db_path)
    server=HTTPServer(("127.0.0.1",port),handler(db_path,controller))
    controller.recover()
    print("Local dashboard: http://127.0.0.1:"+str(server.server_port),flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
