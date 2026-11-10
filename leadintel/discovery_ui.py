"""Company discovery is the primary workflow; known-company crawling is secondary."""
import json
import secrets

from .discovery import details, budget_remaining, safe_result_url
from .query_bank import TRADES, SIGNALS, query_bank, tested_top_queries
from .research_ui import esc
from .research import ACTIVE
from .link_ui import preview_link, alternative_links
from .llm_classifier import comparison, DEFAULT_MODEL, PASS_SCORE
from .contractor_verification import is_project_lead


def contractor_panel(store,result_id):
    panel=f"<div id='contractor-status-{result_id}' class='contractor-status' aria-live='polite'>"
    rows=store.rows('SELECT * FROM contractor_verifications WHERE result_id=?',(result_id,))
    if not rows:
        return panel+'</div>'
    row=rows[0]
    if row['status'] in ('queued','running'):
        return panel+"<div class='contractor-progress'>Checking ranked sources for the general contractor…</div></div>"
    if row['status']!='completed':
        return panel+f"<div class='contractor-error'>Contractor lookup stopped: {esc(row['error'] or row['status'])}</div></div>"
    verified=json.loads(row['verification_json']) if row['verification_json'] else {}
    status=verified.get('contractor_status') or {'confirmed':'confirmed','probable':'likely'}.get(row['confidence'],'unresolved')
    labels={'confirmed':'Verified general contractor','pending_award':'Proposed contractor (decision pending)',
            'likely':'Likely general contractor','unresolved':'General contractor'}
    status_labels={'confirmed':'Final award or role verified','pending_award':'Awaiting final approval',
                   'likely':'Credible evidence; final proof not found','unresolved':'Unresolved'}
    panel+=f"<div class='contractor-result'><strong>{esc(labels[status])}: {esc(row['contractor_name'] or 'Unresolved')}</strong><span>Status: {esc(status_labels[status])}</span>"
    panel+="<details><summary>More information</summary>"
    if row['developer_name']:
        panel+=f"<p><strong>Developer:</strong> {esc(row['developer_name'])}</p>"
    if verified.get('explanation'):
        panel+=f"<p>{esc(verified['explanation'])}</p>"
    if verified.get('methods_attempted'):
        methods=' → '.join(str(item).replace('_',' ') for item in verified['methods_attempted'])
        panel+=f"<p><strong>Search path:</strong> {esc(methods)}</p>"
    cited=set(verified.get('evidence_urls') or [])
    for source in store.rows('SELECT * FROM contractor_evidence WHERE result_id=? ORDER BY id',(result_id,)):
        if source['url'] in cited:
            panel+=preview_link(source['url'],source['title'])
    return panel+'</details></div></div>'


def contact_panel(store,result_id):
    rows=store.rows('SELECT * FROM contact_runs WHERE result_id=? ORDER BY id DESC LIMIT 1',(result_id,))
    panel=f"<div id='contact-status-{result_id}' class='contractor-status' aria-live='polite'>"
    if not rows:
        return panel+'</div>'
    run=rows[0]
    if run['status'] in ('queued','running'):
        return panel+"<div class='contractor-progress'>Finding and checking operational contacts…</div></div>"
    if run['status']!='completed':
        return panel+f"<div class='contractor-error'>Contact lookup stopped: {esc(run['error'] or run['status'])}</div></div>"
    panel+=f"<div class='contractor-result'><strong>Contacts for {esc(run['company'])}</strong><span>{esc(run['note'] or '')}</span>"
    contacts=store.rows('SELECT * FROM lead_contacts WHERE run_id=? ORDER BY relevance DESC,name',(run['id'],))
    if not contacts:
        if (run['note'] or '').startswith('AI role review:'):
            return panel+"<p>No contacts passed the AI role review.</p></div></div>"
        previous=store.rows("SELECT r.id,r.created_at FROM contact_runs r WHERE r.result_id=? AND r.id<>? AND r.status='completed' AND EXISTS (SELECT 1 FROM lead_contacts c WHERE c.run_id=r.id) ORDER BY r.id DESC LIMIT 1",(result_id,run['id']))
        if not previous:
            return panel+"<p>No contacts were saved for this lookup.</p></div></div>"
        contacts=store.rows('SELECT * FROM lead_contacts WHERE run_id=? ORDER BY relevance DESC,name',(previous[0]['id'],))
        panel+=f"<p>The latest lookup found no saved contacts. Showing {len(contacts)} contacts from an earlier lookup ({esc(previous[0]['created_at'])}); check that they are still current.</p>"
    for contact in contacts:
        emails=json.loads(contact['emails_json'])
        panel+=f"<details><summary>{esc(contact['name'])} · {esc(contact['title'] or 'Role unavailable')}"
        if contact['relevance'] is not None: panel+=f" · {esc(contact['relevance'])}/100"
        panel+="</summary>"
        if contact['rank_reason']: panel+=f"<p>{esc(contact['rank_reason'])}</p>"
        panel+=preview_link(contact['linkedin_url'],contact['name'])
        if emails: panel+=f"<p><strong>Professional email:</strong> {esc(', '.join(emails))} · provider-found</p>"
        else: panel+="<p>No email returned by the provider.</p>"
        panel+="</details>"
    return panel+'</div></div>'


def apify_status_panel(store, result_id, mode):
    rows=store.rows('SELECT status,note FROM apify_runs WHERE result_id=? AND mode=? ORDER BY id DESC LIMIT 1',(result_id,mode))
    body=f"<div id='apify-status-{result_id}-{mode}' aria-live='polite'>"
    if rows:
        row=rows[0]
        if row['status'] in ('failed','interrupted'):
            body+=f"<div class='contractor-error'>Apify enrichment: {esc(row['note'] or row['status'])}</div>"
        elif row['status'] in ('queued','running'):
            body+="<div class='contractor-progress'>Apify enrichment is running. Refresh later to check the result.</div>"
        elif row['status']=='completed':
            body+=f"<div class='contractor-result'>{esc(row['note'] or 'Enrichment completed.')}</div>"
    return body+'</div>'


def home(store,token,connection,classifier_connection=None,filters=None):
    filters=filters or {}
    trade=filters.get('trade',['construction'])[0]
    location=filters.get('location',['Dallas Fort Worth Texas'])[0]
    signal=filters.get('signal',['hiring'])[0]
    period=filters.get('period',['month'])[0]
    terms=filters.get('query',[''])[0]
    query_set=filters.get('query_set',['tested'])[0]
    if query_set not in ('tested','full'):
        raise ValueError('Choose a supported query set')
    if query_set=='tested':
        signal='all'
        bank=tested_top_queries(trade,location,terms)
    else:
        bank=query_bank(trade,location,signal,terms)
    if period not in ('week','month','year'):
        raise ValueError('Choose a supported search window')
    ready=bool(connection.key())
    classifier_ready=bool(classifier_connection and classifier_connection.key())
    body="<p class='eyebrow'>CONSTRUCTION LEAD DISCOVERY</p><h2>Find companies with buying signals</h2><p>Tell the engine what to look for. It searches the web and builds a list of company candidates from the evidence it finds.</p>"
    active=store.rows("SELECT id,status FROM research_runs WHERE status IN ('queued','running','stopping')")
    if active:
        body+=f"<p class='notice'>A run is {esc(active[0]['status'])}. <a href='/research/run?id={active[0]['id']}'>View progress / stop</a>.</p>"
    if not ready:
        body+="<div id='search-connection-notice' class='notice'>You can preview queries now. <a href='#connection'>Add your Tavily key</a> to run a search. Keys entered here are cleared when the server restarts.</div>"
    if not classifier_ready:
        body+="<div class='notice'>The classifier is not connected. You can still run the search now; the results will be saved and wait for classification. <a href='/classification'>Connect the classifier</a> when you are ready to score them.</div>"
    def select(name,values,current):
        return f"<select name='{name}'>"+''.join(f"<option value='{esc(k)}' {'selected' if k==current else ''}>{esc(v)}</option>" for k,v in values.items())+'</select>'
    body+="<form id='query-filters' class='card' method='get' action='/'><h3>1. Build your query list</h3><div class='grid'>"
    body+="<label>Query set "+select('query_set',{'tested':'Tested top 15 · recommended','full':'Full experimental bank'},query_set)+"</label>"
    body+="<label>Construction trade / subcategory "+select('trade',{k:v[0] for k,v in TRADES.items()},trade)+"</label>"
    body+=f"<label>Location <input name='location' maxlength='100' value='{esc(location)}' required></label>"
    if query_set=='tested':
        body+="<label>Signals <input value='Hiring, awards, project starts and expansion' disabled><input type='hidden' name='signal' value='all'></label>"
    else:
        body+="<label>Signal to find "+select('signal',dict(SIGNALS,all='All four signals'),signal)+"</label>"
    body+="<label>Search window "+select('period',{'week':'Past week','month':'Past month','year':'Past year'},period)+"</label></div>"
    body+=f"<label class='wide'>Optional keywords <input name='query' maxlength='300' value='{esc(terms)}' placeholder='e.g. school projects'></label>"
    if query_set=='tested':
        body+="<p class='muted'>These 15 searches were selected from the DFW pilot and independent public-web testing on 14 October 2026. Results change over time and still require qualification.</p>"
    else:
        body+="<p class='muted'>20 experimental queries per trade and signal. DFW expands across five cities. These have not all been validated for lead quality.</p>"
    body+="<button>Update query list</button><small> Free preview · matching selections are kept</small><p id='filter-status' role='status' aria-live='polite'></p></form>"
    body+=f"<form id='query-picker' class='card' method='post' action='/discover/start'><input type='hidden' name='csrf' value='{token}'><input type='hidden' name='request_key' value='{secrets.token_urlsafe(24)}'>"
    for name,value in [('query_set',query_set),('trade',trade),('location',location),('signal',signal),('period',period),('query',terms)]:
        body+=f"<input type='hidden' name='{name}' value='{esc(value)}'>"
    body+=f"<h3>2. Choose up to 10 queries</h3><p>{len(bank)} options · {esc(TRADES[trade][0])} · {esc(location)}</p>"
    body+="<div class='picker-tools' hidden><button type='button' id='select-ten'>Select first 10</button> <button type='button' id='clear-queries' class='secondary'>Clear selection</button></div><div class='query-list'>"
    for row in bank:
        rank=f"Tested rank #{row['tested_rank']} · " if row.get('tested_rank') else ''
        body+=f"<label class='query-option'><input type='checkbox' name='query_ids' value='{esc(row['id'])}'><span>{esc(row['query'])}<small>{esc(rank+SIGNALS[row['signal']])}</small></span></label>"
    body+="</div><p id='query-count' role='status' aria-live='polite'>Select 1–10 queries. Each selected query uses 1 Basic search credit.</p>"
    body+=f"<p class='muted'>{budget_remaining(store)} credits remain in the local budget (30/day, 900/month UTC). Up to 10 web results per query; duplicate pages and company names are grouped. More queries do not guarantee more matching companies.</p>"
    # Discovery and classification are separate stages. A missing classifier key must not
    # prevent Tavily from collecting results; the worker keeps those rows pending until the
    # classifier is connected later.
    disabled=not ready or bool(active)
    body+=f"<p><button id='run-queries' data-ready='{int(not disabled)}' {'disabled' if disabled else ''}>Find companies with selected queries</button>"
    if not ready:
        body+=" <small id='search-connection-hint'><a href='#connection'>Connect Tavily below</a> to enable this button.</small>"
    elif active:
        body+=" <small>A search is already running. Open its progress above.</small>"
    elif not classifier_ready:
        body+=" <small>The search will run now and save results for later classification.</small>"
    body+="</p></form>"
    body+=f"<details id='connection' class='card' {'open' if not ready else ''}><summary>Search connection · {'key provided (validated when searching)' if ready else 'setup needed'}</summary>"
    body+="<p>Get an API key from <a href='https://app.tavily.com/' target='_blank' rel='noopener noreferrer'>your Tavily dashboard</a>. Enter it here, not in the chat. It stays in this server’s memory and is sent only to Tavily for searches. Restarting clears a key entered here.</p>"
    body+=f"<form id='search-connect-form' method='post' action='/discover/connect'><input type='hidden' name='csrf' value='{token}'><label class='wide'>Tavily API key <input type='password' name='api_key' autocomplete='off' minlength='10' maxlength='512' required></label><button>Use key for this session</button><p id='connection-status' role='status' aria-live='polite'></p></form></details>"
    body+="<p class='muted'>Search coverage is partial. Job-board and social domains are excluded from recommended general searches; selected trade-news queries use provider domain restrictions. Single vacancies cannot pass the lead score. Dates, identities and locations still need source verification.</p>"
    body+="<h3>Recent searches</h3>"
    runs=store.rows('SELECT r.*,d.location,d.industry FROM research_runs r JOIN discovery_config d ON d.run_id=r.id ORDER BY r.id DESC LIMIT 20')
    if not runs:
        body+="<p>No company discovery searches yet.</p>"
    for r in runs:
        body+=f"<div class='card'><a href='/research/run?id={r['id']}'>{esc(r['industry'])} · {esc(r['location'])}</a><p>{esc(r['signal'])} · {esc(r['status'].replace('_',' '))}</p></div>"
    body+="<details class='card'><summary>Already know the company?</summary><p><a href='/monitor'>Research specific websites</a> to investigate or monitor known companies. This is separate from discovering new ones.</p></details>"
    return body


def result_page(store,ident,token,controller=None):
    data=details(store,ident)
    r,c=data['run'],data['config']
    active=r['status'] in ACTIVE
    body=f"<a href='/'>← Find companies</a><h2>Companies found</h2><p>{esc(c['industry'])} · {esc(c['location'])} · {esc(r['signal'])}</p><span class='tag'>{esc(r['status'].replace('_',' ').upper())}</span>"
    if r['note']:
        body+=f"<p class='notice'>{esc(r['note'])}</p>"
    if active:
        body+=f"<form method='post' action='/research/stop'><input type='hidden' name='csrf' value='{token}'><input type='hidden' name='run_id' value='{ident}'><p><button>Stop search</button></p></form><p>Refreshes every three seconds. An in-flight search may finish after you press Stop.</p>"
    body+=f"<div class='grid stats'><div class='card'><strong>{len(data['companies'])}</strong><br>Scored lead candidates</div><div class='card'><strong>{data['classified_count']} / {data['result_count']}</strong><br>Results classified</div><div class='card'><strong>{len(data['attempts'])} / {len(json.loads(c['requests_json']))}</strong><br>Searches attempted</div></div>"
    body+=f"<p class='muted'>A structured LLM identifies the company and signal from each title and snippet. Plain code scores signal strength, source reliability, freshness and field-workforce evidence. Only construction companies scoring at least {PASS_SCORE} appear as lead candidates.</p>"
    if data['pending_classification']:
        body+=f"<p class='notice'>{data['pending_classification']} results still need classification. <a href='/classification'>Open classification review</a>.</p>"
    if not data['companies']:
        body+="<div class='card'>"+('Searching for companies…' if active else 'No company candidates identified from this run. Review the other search results below, broaden the time window or refine your terms. No stored company list has been substituted.')+"</div>"
    for company in data['companies']:
        first=company['evidence'][0]
        body+=f"<article class='card'><span class='tag'>SCORED LEAD · {company['score']['total']}/100 · NEEDS VERIFICATION</span><h3>{esc(company['name'])}</h3><p>{esc(company['classification'].get('evidence_summary') or '')}</p>"
        for e in company['evidence']:
            body+=preview_link(e['url'],e['title'])+alternative_links(e,company['evidence'])
        body+="<div class='lead-actions'>"
        body+=f"<form method='post' action='/discover/flag'><input type='hidden' name='csrf' value='{token}'><input type='hidden' name='result_id' value='{first['id']}'><input type='hidden' name='identity_key' value='{esc(company['identity_key'])}'><p><button>Save for lead review</button></p></form>"
        project_lead=is_project_lead(company['classification'])
        ready=bool(controller and controller.apify_connection.key())
        if project_lead:
            contractor_ready=bool(controller and controller.connection.key() and controller.classifier_connection.key())
            contractor_label='Find and verify general contractor' if contractor_ready else 'Connect contractor verifier'
            body+=f"<form class='contractor-form' data-result-id='{first['id']}' method='post' action='/contractor/verify'><input type='hidden' name='csrf' value='{token}'><input type='hidden' name='result_id' value='{first['id']}'><button>{contractor_label}</button></form>"
            body+=f"<form class='contact-form' data-result-id='{first['id']}' method='post' action='/contacts/start'><input type='hidden' name='csrf' value='{token}'><input type='hidden' name='result_id' value='{first['id']}'><button>{'Find operational contacts' if ready else 'Connect Apify contacts'}</button></form>"
        apify_label='Enrich project evidence with Apify' if ready else 'Connect Apify enrichment'
        body+=f"<form class='apify-form' data-result-id='{first['id']}' data-mode='project' method='post' action='/apify/start'><input type='hidden' name='csrf' value='{token}'><input type='hidden' name='result_id' value='{first['id']}'><input type='hidden' name='mode' value='project'><button>{apify_label}</button></form>"
        if company['classification'].get('source_is_company_owned'):
            body+=f"<form class='apify-form' data-result-id='{first['id']}' data-mode='company' method='post' action='/apify/start'><input type='hidden' name='csrf' value='{token}'><input type='hidden' name='result_id' value='{first['id']}'><input type='hidden' name='mode' value='company'><button>Check company careers and project pages</button></form>"
        body+='</div>'
        body+=apify_status_panel(store,first['id'],'project')+apify_status_panel(store,first['id'],'company')
        if project_lead:
            body+=contractor_panel(store,first['id'])
            body+=contact_panel(store,first['id'])
        runs=store.rows('SELECT * FROM apify_runs WHERE result_id=? ORDER BY id DESC',(first['id'],))
        for run in runs:
            body+=f"<p><small>Apify {esc(run['mode'])}: {esc(run['status'])} · {esc(run['note'] or '')}</small></p>"
            for item in store.rows('SELECT * FROM apify_evidence WHERE run_id=? ORDER BY id',(run['id'],)):
                body+=f"<details><summary>{esc(item['title'])}</summary><p>{esc(item['content'][:1500])}</p><small>{esc(item['url'])}</small></details>"
        body+='</article>'
    body+=f"<details class='card'><summary>Other web results — company or signal unresolved ({len(data['unresolved'])})</summary>"
    for e in data['unresolved']:
        body+=preview_link(e['url'],e['title'])+alternative_links(e)
        body+=f"<p>{esc(e['snippet'][:700])}</p>"
        if e['classification']:
            body+=f"<small>Classifier: {esc(e['classification'].get('company_name') or 'No company')} · {esc(e['classification']['signal_type'])} · score {esc(e['score'] if e['score'] is not None else 0)}/100 · {esc(e['classification'].get('rejection_reason') or 'Below lead threshold')}</small>"
        elif e['classification_status']=='failed':
            body+=f"<small>Classification failed: {esc(e['classification_error'])}</small>"
        else:
            body+="<small>Awaiting classification</small>"
    body+="</details><details class='card' open><summary>Selected queries and search activity</summary>"
    attempts={a['query']:a for a in data['attempts']}
    for planned in json.loads(c['requests_json']):
        a=attempts.get(planned['query'])
        status=a['status'] if a else ('Waiting' if active else 'Not run')
        body+=f"<p><strong>{esc(status)}</strong> · {esc(planned['query'])}<br>{esc(a['note'] or '') if a else ''}</p>"
    body+="<p>Public web index, not full social feeds. Search window is a provider filter, not a verified event date. Repeated reporting does not establish independent corroboration.</p></details>"
    return body,active


def classification_page(store,token,controller):
    data=comparison(store,500)
    ready=bool(controller.classifier_connection.key())
    apify_ready=bool(controller.apify_connection.key())
    search_connection=getattr(controller,'connection',None)
    search_ready=bool(search_connection and search_connection.key())
    runs=store.rows('SELECT * FROM classification_runs ORDER BY id DESC LIMIT 10')
    active=next((r for r in runs if r['status'] in ('queued','running')),None)
    latest=runs[0] if runs else None
    percent=round(100*data['classified']/data['total']) if data['total'] else 100
    body=f"<a href='/'>← Find companies</a><h2>LLM classification review</h2><p>This page compares the old regex output with structured classifications of the stored Tavily results. It sends no new Tavily searches.</p><p><strong>Classifier model:</strong> {esc(DEFAULT_MODEL)} · fixed for consistent evaluation</p>"
    body+=f"<div class='grid stats'><div class='card'><strong>{data['classified']} / {data['total']}</strong><br>Classified · {percent}%</div><div class='card'><strong>{data['old_company_results']}</strong><br>Old regex matches</div><div class='card'><strong>{data['new_company_results']}</strong><br>Clearly named construction companies</div><div class='card'><strong>{data['passing_leads']}</strong><br>Leads scoring {PASS_SCORE}+</div><div class='card'><strong>{data['reviewed_leads']}</strong><br>Passing leads reviewed</div><div class='card'><strong>{data['would_call']}</strong><br>Would call</div></div>"
    body+=f"<progress max='{data['total'] or 1}' value='{data['classified']}' style='width:100%;height:18px' aria-label='Overall classification progress'>{data['classified']} of {data['total']}</progress>"
    if active:
        body+=f"<p class='notice'>Overall: {data['classified']} of {data['total']} classified ({percent}%). Current run #{active['id']}: {active['processed']} of {active['total']} remaining results processed. This page refreshes every three seconds.</p>"
    elif data['classified']<data['total']:
        body+=f"<p class='notice'>{data['total']-data['classified']} results still need classification. Completed results are retained when a retry is needed.</p>"
        if latest and latest['status']=='failed':
            body+=f"<p class='notice'><strong>Previous run stopped:</strong> {esc(latest['note'] or 'Unknown classifier error')}. It is safe to retry the remaining results.</p>"
    body+=f"<details id='search-connection' class='card' {'open' if not search_ready else ''}><summary>Search connection · {'key provided' if search_ready else 'setup needed for contractor lookup'}</summary><p>The contractor lookup checks ranked sources and stops at the first confirmed result. A fully unresolved lookup can use up to five Tavily Basic searches. The key stays in server memory and is cleared on restart.</p><form method='post' action='/discover/connect'><input type='hidden' name='csrf' value='{token}'><input type='hidden' name='return_to' value='classification'><label class='wide'>Tavily API key <input type='password' name='api_key' autocomplete='off' minlength='10' maxlength='512' required></label><button>Use key for this session</button></form></details>"
    body+=f"<details id='classifier-connection' class='card' {'open' if not ready else ''}><summary>Classifier connection · {'key provided' if ready else 'setup needed'}</summary><p>Enter the key here, not in chat. It stays in server memory, is sent only to OpenAI for structured classification, and is cleared on restart.</p><form method='post' action='/classifier/connect'><input type='hidden' name='csrf' value='{token}'><label class='wide'>OpenAI API key <input type='password' name='api_key' autocomplete='off' minlength='20' maxlength='512' required></label><button>Use key for this session</button></form></details>"
    body+=f"<details id='apify-connection' class='card' {'open' if not apify_ready else ''}><summary>Apify enrichment and contact lookup · {'token provided' if apify_ready else 'API token needed'}</summary><p>The website-evidence and operational-contact buttons require an Apify API token. It stays only in this local server session and is sent only to Apify when you run a lookup. Project contact lookup is limited to five profiles and a $0.10 maximum Actor charge; website evidence is limited to five pages and a $0.25 cap.</p><form method='post' action='/apify/connect'><input type='hidden' name='csrf' value='{token}'><label class='wide'>Apify API token <input type='password' name='api_key' autocomplete='off' minlength='20' maxlength='512' required></label><button>Use token for this session</button></form></details>"
    if data['classified']<data['total'] and not active:
        body+=f"<form class='card' method='post' action='/classification/start'><input type='hidden' name='csrf' value='{token}'><input type='hidden' name='limit' value='{min(500,data['total']-data['classified'])}'><h3>Classify stored results</h3><p>Processes up to 10 titles/snippets per model request and stores the structured output beside the original regex result.</p><button {'disabled' if not ready else ''}>Classify {data['total']-data['classified']} remaining results</button></form>"
    body+="<h3>Side-by-side results · highest score first</h3>"
    source_counts={}
    for item in data['rows']:
        key=safe_result_url(item['url']) or f"result:{item['id']}"
        source_counts[key]=source_counts.get(key,0)+1
    shown_sources=set()
    for row in data['rows']:
        source_key=safe_result_url(row['url']) or f"result:{row['id']}"
        if source_key in shown_sources:
            continue
        shown_sources.add(source_key)
        old=', '.join(c.get('name','') for c in row['old_companies']) or 'No company'
        new=row['classification'].get('company_name') if row['classification'] else None
        body+="<article class='card'><div class='classification-title'>"
        body+=preview_link(row['url'],row['title'])
        if source_counts[source_key]>1:
            body+=f"<small>{source_counts[source_key]-1} duplicate search result grouped with this source page. Contractor verification is reused.</small>"
        body+=f"</div><p><strong>Old regex:</strong> {esc(old)}<br><strong>LLM:</strong> {esc(new or ('Not classified' if not row['classification'] else 'No company'))}"
        if row['classification']:
            body+=f" · {esc(row['classification']['signal_type'])} · {esc(row['score'] or 0)}/100</p><p>{esc(row['classification'].get('evidence_summary') or row['classification'].get('rejection_reason') or '')}</p>"
            if row['score_detail'] and row['score_detail'].get('passes'):
                decision={'call':'Would call','no_call':'Would not call','unsure':'Unsure'}.get(row['review_decision'],'Not reviewed')
                body+=f"<p><strong>Screen-printer review:</strong> {esc(decision)}"
                if row['review_note']:
                    body+=f" · {esc(row['review_note'])}"
                body+="</p>"
                body+=f"<form method='post' action='/classification/review'><input type='hidden' name='csrf' value='{token}'><input type='hidden' name='result_id' value='{row['id']}'><label class='wide'>Why would you call or skip this lead? <input name='note' maxlength='500' value='{esc(row['review_note'] or '')}'></label><button name='decision' value='call'>Would call</button> <button class='secondary' name='decision' value='no_call'>Would not call</button> <button class='secondary' name='decision' value='unsure'>Unsure</button></form>"
                apify_label='Enrich project evidence with Apify' if apify_ready else 'Connect Apify enrichment'
                body+="<div class='lead-actions'>"
                project_lead=is_project_lead(row['classification'])
                if project_lead:
                    contractor_label='Find and verify general contractor' if search_ready and ready else 'Connect contractor verifier'
                    body+=f"<form class='contractor-form' data-result-id='{row['id']}' method='post' action='/contractor/verify'><input type='hidden' name='csrf' value='{token}'><input type='hidden' name='result_id' value='{row['id']}'><input type='hidden' name='return_to' value='classification'><button>{contractor_label}</button></form>"
                    body+=f"<form class='contact-form' data-result-id='{row['id']}' method='post' action='/contacts/start'><input type='hidden' name='csrf' value='{token}'><input type='hidden' name='result_id' value='{row['id']}'><button>{'Find operational contacts' if apify_ready else 'Set up Apify contact token'}</button></form>"
                body+=f"<form class='apify-form' data-result-id='{row['id']}' data-mode='project' method='post' action='/apify/start'><input type='hidden' name='csrf' value='{token}'><input type='hidden' name='result_id' value='{row['id']}'><input type='hidden' name='mode' value='project'><input type='hidden' name='return_to' value='classification'><button>{apify_label}</button></form>"
                body+='</div>'
                body+=apify_status_panel(store,row['id'],'project')
                if project_lead:
                    body+=contractor_panel(store,row['id'])
                    body+=contact_panel(store,row['id'])
        else:
            body+="</p>"
        body+=alternative_links(row)+"</article>"
    return body,bool(active)
