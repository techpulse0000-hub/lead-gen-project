"""Server-rendered research controls; no external scripts or services."""
import html
import secrets

from .profile import load_profile
from .research import ACTIVE, run_details, source_options


def esc(value):
    return html.escape(str(value),quote=True)


def controls(store, token):
    profile=load_profile()
    signal_labels={'hiring':'Bulk hiring','award':'Contract award','mobilization':'Project start / construction','expansion':'Expansion / opening'}
    body="<p class='eyebrow'>CONSTRUCTION INTELLIGENCE · DALLAS–FORT WORTH PILOT</p><h2>Monitor construction sources</h2><p>Collect fresh evidence from project trackers, official records and construction publications, then find pages matching your signals and location.</p>"
    active=store.rows("SELECT * FROM research_runs WHERE status IN ('queued','running','stopping') ORDER BY id DESC")
    if active:
        body+=f"<div class='notice'>Research is {esc(active[0]['status'])}. <a href='/research/run?id={active[0]['id']}'>View progress or stop this run</a>.</div>"
    body+="<form class='card' method='post' action='/research/start'>"
    body+=f"<input type='hidden' name='csrf' value='{token}'><input type='hidden' name='request_key' value='{secrets.token_urlsafe(24)}'>"
    body+="<h3>1. What should we look for?</h3><label class='wide'>Optional keywords <input name='query' maxlength='500' placeholder='e.g. school or sheet metal'></label><p class='muted'>Choose the signal and county below. Keywords narrow results: every word must appear. Leave blank for all matching signals.</p><div class='grid'>"
    for name,label,values in [('signal','Buying signal',profile['signals']),('geography','County mentioned',profile['geography'])]:
        body+=f"<label>{label}<select name='{name}'><option value=''>Any</option>"
        body+=''.join(f"<option value='{esc(v)}'>{esc(signal_labels.get(v,v.title()) if name=='signal' else v.title())}</option>" for v in values)
        body+='</select></label>'
    body+="</div><h3>2. Which exact listings should we monitor?</h3><p>Choose up to six direct project, contractor, permit, bid or award feeds. Every Open listing page link goes straight to the information being collected. Company websites and general homepages are intentionally excluded.</p><div class='grid sources'>"
    for c in source_options(store):
        signals=' · '.join(c['signals'])
        body+=f"<div class='source'><label><input type='checkbox' name='sources' value='{esc(c['key'])}'><span><strong>{esc(c['name'])}</strong><small>{esc(c['coverage'])} · {esc(c['category'])}</small><small>{esc(c['description'])}</small><small><strong>Signals:</strong> {esc(signals)}</small><small class='source-caution'>{esc(c['caution'])}</small></span></label><a class='source-direct' href='{esc(c['url'])}' target='_blank' rel='noopener noreferrer'>Open exact listing page ↗</a></div>"
    body+="</div><p class='muted'>The catalogue was evidence-reviewed on 15 October 2026. Source access, publication frequency and project status can change.</p><label class='wide'>Or add the exact URL of another public listing page <input type='url' name='custom_url' maxlength='2048' placeholder='https://example.com/construction/projects'></label>"
    body+="<h3>3. Set collection limits</h3><div class='grid'><label>Total page limit <input type='number' name='max_pages' min='1' max='20' value='6' required></label><label>Link depth <select name='max_depth'><option value='0'>0 — starting page only</option><option value='1' selected>1 — follow relevant links once</option><option value='2'>2 — two levels</option><option value='3'>3 — three levels</option></select></label></div>"
    body+="<p class='muted'>Page allowance is shared across selected sites. Robots checks and redirects also use the existing HTTP request limits. A run may finish with fewer pages if a source blocks access.</p>"
    body+=("<button disabled>Research already running</button>" if active else "<button type='submit'>Start research</button>")+" <span class='muted'>Starts live website requests · no paid API calls</span></form>"
    body+="<div class='card'><h3>How this differs from Find companies</h3><p><a href='/'>Find companies</a> runs targeted Tavily queries across the public web. This page repeatedly checks a chosen set of high-value construction intelligence sources. A mention is evidence to investigate; filings, bids and planned openings still require milestone and contractor verification.</p><p class='muted'>The source-selection evidence and access limits are recorded in docs/MONITOR_SOURCE_RESEARCH.md.</p></div>"
    body+="<h3>Recent research</h3>"
    runs=store.rows('SELECT * FROM research_runs ORDER BY id DESC LIMIT 20')
    if not runs:
        body+="<p class='muted'>No live research runs yet. Choose a website above to begin.</p>"
    for r in runs:
        body+=f"<div class='card'><a href='/research/run?id={r['id']}'>Research #{r['id']} · {esc(r['query'] or r['signal'] or 'All signals')}</a> <span class='tag'>{esc(r['status'].replace('_',' '))}</span><p class='muted'>{esc(r['created_at'])} · {esc(r['geography'] or 'Any pilot county')}</p></div>"
    return body


def progress(store, ident, token):
    r=run_details(store,ident)
    active=r['status'] in ACTIVE
    body=f"<p><a href='/'>← Research controls</a></p><h2>Research #{ident}</h2><span class='tag'>{esc(r['status'].replace('_',' ').upper())}</span>"
    body+=f"<p>Keywords: {esc(r['query'] or 'Any')} · Signal: {esc(r['signal'] or 'Any')} · County mentions: {esc(r['geography'] or 'Any')}<br>Page limit: {r['max_pages']} · Link depth: {r['max_depth']}</p>"
    if active:
        body+="<p>Progress refreshes every three seconds. Stop takes effect after any current HTTP request finishes.</p>"
        body+=f"<form method='post' action='/research/stop'><input type='hidden' name='csrf' value='{token}'><input type='hidden' name='run_id' value='{ident}'><button>{'Stopping…' if r['status']=='stopping' else 'Stop research'}</button></form>"
    if r['note']:
        body+=f"<p class='notice'>{esc(r['note'])}</p>"
    body+=f"<div class='grid stats'><div class='card'><strong>{len(r['documents'])}</strong><br>Pages collected</div><div class='card'><strong>{len(r['results'])}</strong><br>Matching pages</div><div class='card'><strong>{len(r['jobs'])} / {len(r['sources'])}</strong><br>Websites started</div></div>"
    body+="<h3>Matching evidence from this run</h3><p class='muted'>Matches are unverified evidence, not qualified leads. Location tags indicate text mentions. Demo records are excluded.</p>"
    if not r['results']:
        body+="<div class='card'>No matching evidence "+("yet. Collection is still in progress." if active else "found within this run’s sources and limits. This does not establish that no opportunity exists.")+"</div>"
    for d in r['results']:
        body+=f"<article class='card'><span class='tag'>UNVERIFIED EVIDENCE</span><h3><a href='/evidence?id={d['id']}'>{esc(d['title'] or d['url'])}</a></h3><p>{esc(d['excerpt'])}</p><small>{esc(d['url'])}</small></article>"
    body+="<details class='card'><summary>All collected pages (including those outside your filters)</summary>"
    for d in r['documents']:
        body+=f"<p><a href='/evidence?id={d['id']}'>{esc(d['title'] or d['url'])}</a></p>"
    body+="</details><h3>Website progress and access gaps</h3>"
    for s in r['sources']:
        jobs=[j for j in r['jobs'] if j['source_id']==s['id']]
        j=jobs[-1] if jobs else None
        body+=f"<div class='card'><strong>{esc(s['name'])}</strong><p>{esc(s['url'])}</p><span class='tag'>{esc(j['status'] if j else ('waiting' if active else 'not started'))}</span>"
        if j and j['note']:
            body+=f"<p>{esc(j['note'])}</p>"
        if j:
            for p in (p for p in r['pages'] if p['job_id']==j['id']):
                body+=f"<p><small>{esc(p['status'])} · {esc(p['url'])}{' — '+esc(p['error']) if p['error'] else ''}</small></p>"
        body+='</div>'
    body+="<details class='card'><summary>HTTP activity (includes robots checks and redirects)</summary>"
    for a in r['attempts']:
        body+=f"<p><small>{esc(a['started_at'])} · {esc(a['status'])} · {esc(a['detail'] or 'Request pending')}<br>{esc(a['url'])}</small></p>"
    body+='</details>'
    return body,active
