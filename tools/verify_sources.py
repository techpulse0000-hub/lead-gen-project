"""Read the curated public sites and retain compact source-link evidence.

Does not fetch social feeds, use credentials, or bypass robots/access blocks.
The source JSON is the curated authority list, not a web instruction source.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import ipaddress
import json
import socket
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
USER_AGENT = "LeadGenSourceReview/0.1"
SOCIAL_DOMAINS = {"linkedin.com", "instagram.com", "facebook.com", "twitter.com", "x.com", "youtube.com", "youtu.be", "tiktok.com", "indeed.com"}


def validate_url(url: str, resolve: bool = True) -> str:
    p = urllib.parse.urlsplit(url)
    if p.scheme not in ("http", "https") or not p.hostname or p.username or p.password or p.port not in (None, 80, 443):
        raise ValueError("Only credential-free public HTTP(S) URLs are supported")
    if p.hostname.lower() in ("localhost",) or p.hostname.lower().endswith((".local", ".internal")):
        raise ValueError("Private hostname rejected")
    try:
        ip = ipaddress.ip_address(p.hostname)
    except ValueError:
        ip = None
    if ip is not None and not ip.is_global:
        raise ValueError("Private address rejected")
    if resolve:
        addresses = socket.getaddrinfo(p.hostname, p.port or (443 if p.scheme == "https" else 80))
        if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):
            raise ValueError("Non-public resolved address rejected")
    return url


class SafeRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        validate_url(newurl)
        if is_social(newurl):
            raise ValueError("Redirect to a social/job-board page is disabled")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class PageParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links = []
        self.title = []
        self.in_title = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "a" and attrs.get("href"):
            self.links.append(attrs["href"])
        if tag == "title":
            self.in_title = True

    def handle_endtag(self, tag):
        if tag == "title":
            self.in_title = False

    def handle_data(self, data):
        if self.in_title:
            self.title.append(data)


def host_matches(host, domain):
    return host == domain or host.endswith("." + domain)


def is_social(url):
    host = (urllib.parse.urlsplit(url).hostname or "").lower()
    return any(host_matches(host, d) for d in SOCIAL_DOMAINS)


def fetch(url):
    validate_url(url)
    opener = urllib.request.build_opener(SafeRedirect())
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,text/plain;q=0.9"})
    with opener.open(request, timeout=20) as response:
        body = response.read(3_000_001)
        if len(body) > 3_000_000:
            raise ValueError("Page exceeds 3 MB limit")
        return response.status, response.url, body, response.headers.get("Content-Type", "")


def check(item):
    checked_at = datetime.now(timezone.utc).isoformat()
    result = {"id": item["id"], "url": item["url"], "checked_at": checked_at, "social_links": [], "research_links": []}
    try:
        if is_social(item["url"]):
            raise ValueError("Direct social/job-board fetching is disabled; use indexed search or approved APIs")
        p = urllib.parse.urlsplit(item["url"])
        robots_url = urllib.parse.urlunsplit((p.scheme, p.netloc, "/robots.txt", "", ""))
        result["robots_url"] = robots_url
        try:
            status, final, body, _ = fetch(robots_url)
            rp = urllib.robotparser.RobotFileParser()
            rp.parse(body.decode("utf-8", "replace").splitlines())
            allowed = rp.can_fetch(USER_AGENT, item["url"])
            result["robots_status"] = "allowed" if allowed else "disallowed"
            if not allowed:
                result["access_status"] = "robots_disallowed"
                return result
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                result["robots_status"] = "not_found"
            else:
                result["robots_status"] = "unavailable"
                result["access_status"] = "robots_check_failed"
                result["error"] = str(exc)
                return result
        status, final, body, content_type = fetch(item["url"])
        page = PageParser()
        page.feed(body.decode("utf-8", "replace"))
        result.update(http_status=status, final_url=final, content_type=content_type, title=" ".join(page.title).strip(), content_sha256=hashlib.sha256(body).hexdigest(), access_status="retrieved")
        for href in dict.fromkeys(page.links):
            link = urllib.parse.urljoin(final, href)
            if urllib.parse.urlsplit(link).scheme not in ("http", "https"):
                continue
            if is_social(link):
                result["social_links"].append(link)
            elif any(s in link.lower() for s in ("career", "jobs", "news", "blog", "project", "portfolio", "contact", "location")):
                result["research_links"].append(link)
        result["social_links"] = sorted(set(result["social_links"]))
        result["research_links"] = sorted(set(result["research_links"]))[:35]
    except Exception as exc:
        result["access_status"] = "unavailable"
        result["error"] = str(exc)[:300]
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ids", nargs="*", help="Check only these curated company/source IDs")
    args = parser.parse_args()
    seed = json.loads((ROOT / "data/registry_seed.json").read_text(encoding="utf-8"))
    items = [{"id": c["id"], "url": c["website"]} for c in seed["companies"]] + seed["sources"]
    if args.ids:
        items = [x for x in items if x["id"] in args.ids]
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        for result in pool.map(check, items):
            results.append(result)
            print(json.dumps({k: result.get(k) for k in ("id", "access_status", "title", "social_links", "research_links", "error")}, ensure_ascii=False), flush=True)
    path = ROOT / "data/source_checks.json"
    existing = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
    combined = {r["id"]: r for r in existing}
    combined.update({r["id"]: r for r in results})
    path.write_text(json.dumps(list(combined.values()), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
