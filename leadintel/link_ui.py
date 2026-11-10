"""Destination previews and explicitly reviewed alternatives; rendering makes no network calls."""
import json
import secrets
from pathlib import Path
from urllib.parse import urlsplit, urlencode

from .discovery import safe_result_url
from .research_ui import esc

ALTERNATIVES = Path(__file__).resolve().parents[1] / 'data/reviewed_alternative_links.json'


def preview_link(url, title):
    url = safe_result_url(url)
    if not url:
        return '<span>Link unavailable: invalid destination</span>'
    domain = urlsplit(url).hostname
    ident = 'link-preview-' + secrets.token_hex(8)
    title = title or domain
    return (f"<div class='link-block'><a class='destination-link' href='{esc(url)}' "
            f"target='_blank' rel='noopener noreferrer' aria-describedby='{ident}' "
            f"aria-label='Open source: {esc(title)}'><span class='source-icon' aria-hidden='true'>↗</span> {esc(title)}</a>"
            f"<span class='link-domain'>{esc(domain)}</span>"
            f"<div class='link-preview' id='{ident}' role='tooltip'><strong>{esc(title)}</strong>"
            f"<span>{esc(domain)}</span></div></div>")


def alternative_links(result, related=()):
    source = safe_result_url(result['url'])
    reviewed = json.loads(ALTERNATIVES.read_text(encoding='utf-8'))
    matches = [a for a in reviewed if safe_result_url(a['source_url']) == source
               and safe_result_url(a['url']) and safe_result_url(a['url']) != source]
    body = "<details class='alternatives'><summary>Link not accessible? Alternative links</summary>"
    used = {source}
    for item in matches:
        used.add(safe_result_url(item['url']))
        body += "<p><strong>Alternative posting · manually matched</strong></p>"
        body += preview_link(item['url'], item['title'])
        body += f"<p class='muted'>Reviewed {esc(item['reviewed_on'])}. {esc(item['basis'])}</p>"
    # Other evidence may concern a different event. Never label it a copy of this posting.
    others = []
    for item in related:
        url = safe_result_url(item['url'])
        if url and url not in used:
            others.append(item)
            used.add(url)
    if others:
        body += '<p>Other results grouped under this company — may describe different opportunities:</p>'
        for item in others[:3]:
            body += preview_link(item['url'], item['title'])
    if not matches:
        body += '<p>No manually matched replacement posting is saved for this link yet.</p>'
    search = 'https://www.google.com/search?' + urlencode({'q': result['title'] or result['url']})
    body += preview_link(search, 'Search the web for another copy')
    body += '<p class="muted">Opens Google with this page title. Search results are not verified alternatives. No search runs until you open the link.</p></details>'
    return body
