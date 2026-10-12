"""Preview or run bounded public-index searches for stored company social activity.

This is not an authenticated social-feed reader. Results are unverified candidates.
Only --execute sends requests. No messages, job applications or social actions.
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PLATFORMS = ("linkedin", "instagram", "x", "indeed")


def make_queries(db, company_ids=None, platforms=DEFAULT_PLATFORMS):
    companies = db.execute("SELECT id,name FROM companies ORDER BY id").fetchall()
    output = []
    for cid, name in companies:
        if company_ids and cid not in company_ids:
            continue
        for platform in platforms:
            row = db.execute("SELECT record_json FROM platforms WHERE id=?", (platform,)).fetchone()
            if not row:
                raise ValueError("Unknown platform: " + platform)
            domains = json.loads(row[0])["domains"]
            clean_name = name.replace('"', " ").replace("\n", " ")
            identity = f'"{clean_name}"'
            profile = db.execute("SELECT url FROM company_profiles WHERE company_id=? AND platform=? AND verification_status IN ('official_site_linked','corroborated_identity') ORDER BY verification_status LIMIT 1", (cid,platform)).fetchone()
            if profile:
                handle = urllib.parse.unquote(urllib.parse.urlsplit(profile[0]).path.rstrip('/').split('/')[-1]).lstrip('@')
                if handle and not handle.isdigit() and handle != 'profile.php':
                    identity = f'("{clean_name}" OR "{handle}")'
            keywords = '(jobs OR hiring) (Dallas OR "Fort Worth" OR "Grand Prairie" OR Richardson)' if platform == "indeed" else '(hiring OR "new project" OR awarded OR expansion) (Dallas OR "Fort Worth" OR Frisco OR Richardson OR "Grand Prairie")'
            query = f'{identity} {keywords}'
            output.append(dict(company_id=cid, platform=platform, query=query, domains=domains, coverage="partial_public_index"))
    return output


def reserve(db, item, now=None):
    """Reserve a request before network access, serializing concurrent runners."""
    now = now or datetime.now(timezone.utc).isoformat()
    db.execute("BEGIN IMMEDIATE")
    try:
        daily = db.execute("SELECT COUNT(*) FROM search_attempts WHERE substr(created_at,1,10)=?", (now[:10],)).fetchone()[0]
        monthly = db.execute("SELECT COUNT(*) FROM search_attempts WHERE substr(created_at,1,7)=?", (now[:7],)).fetchone()[0]
        if daily >= 30 or monthly >= 900:
            raise ValueError("Request budget exhausted: maximum 30/day and 900/month in this UTC usage ledger")
        cursor = db.execute("INSERT INTO search_attempts(created_at,company_id,platform,query,status,estimated_cost_microusd) VALUES (?,?,?,?,?,?)", (now,item["company_id"],item["platform"],item["query"],"reserved",8000))
        db.commit()
        return cursor.lastrowid
    except Exception:
        db.rollback()
        raise


def request_search(item, key):
    body = json.dumps(dict(query=item["query"], include_domains=item["domains"], search_depth="basic",
        auto_parameters=False, max_results=5, include_answer=False, include_raw_content=False, include_usage=True,
        time_range="month")).encode()
    req = urllib.request.Request("https://api.tavily.com/search", data=body,
        headers={"Authorization":"Bearer " + key, "Content-Type":"application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=45) as response:
        return json.load(response)


def filter_results(response, item):
    """Keep only expected public domains; never promote index hits to verified facts."""
    output = []
    seen = set()
    for result in response.get("results", []):
        url = result.get("url", "")
        p = urllib.parse.urlsplit(url)
        host = (p.hostname or "").lower()
        if p.scheme not in ("http", "https") or p.username or p.password:
            continue
        if not any(host == d or host.endswith("." + d) for d in item["domains"]):
            continue
        if item["platform"] == "linkedin" and p.path.startswith("/in/"):
            continue
        if url in seen:
            continue
        seen.add(url)
        output.append(dict(url=url, title=result.get("title", ""), snippet=result.get("content", "")[:1200],
            provider_date=result.get("published_date"), event_date=None, worker_quantity=None,
            status="unverified_index_candidate", requires=["company_identity","original_source","event_date","location","apparel_relevance"]))
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--company", action="append", help="Stored company ID; repeat for more than one")
    parser.add_argument("--platform", action="append", choices=(*DEFAULT_PLATFORMS,"facebook","youtube","tiktok"))
    parser.add_argument("--limit", type=int, default=4)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    if not 1 <= args.limit <= 30:
        parser.error("--limit must be between 1 and 30")
    path = ROOT / "data/source_registry.sqlite"
    if not path.exists():
        parser.error("Run tools/build_registry.py first")
    db = sqlite3.connect(path)
    db.execute("PRAGMA foreign_keys=ON")
    if args.company:
        existing = {r[0] for r in db.execute("SELECT id FROM companies")}
        unknown = set(args.company) - existing
        if unknown:
            parser.error("Unknown company ID: " + ", ".join(sorted(unknown)))
    queries = make_queries(db, args.company, args.platform or DEFAULT_PLATFORMS)
    # Least recently searched first; retries/errors count as attempts and remain visible.
    last = {(cid,p):t for cid,p,t in db.execute("SELECT company_id,platform,MAX(created_at) FROM search_attempts GROUP BY company_id,platform")}
    queries.sort(key=lambda q:(last.get((q["company_id"],q["platform"]),""),q["company_id"],q["platform"]))
    queries = queries[:args.limit]
    if not args.execute:
        print(json.dumps(dict(mode="preview", requests_sent=0, estimated_list_price_usd=.008*len(queries),queries=queries),indent=2))
        return
    key = os.environ.get("TAVILY_API_KEY")
    if not key:
        parser.error("TAVILY_API_KEY is not configured. No requests were sent.")
    results = []
    for item in queries:
        ident = reserve(db, item)
        try:
            response = request_search(item, key)
            result = dict(item, results=filter_results(response,item), provider_usage=response.get("usage"),
                status="completed", searched_at=datetime.now(timezone.utc).isoformat())
        except urllib.error.HTTPError as exc:
            result = dict(item,status="failed",error=f"HTTP {exc.code}")
        except Exception as exc:
            result = dict(item,status="failed",error=type(exc).__name__)
        with db:
            db.execute("UPDATE search_attempts SET status=?,record_json=? WHERE id=?", (result["status"],json.dumps(result),ident))
        results.append(result)
    print(json.dumps(dict(mode="executed",attempts=len(results),results=results),indent=2,ensure_ascii=False))


if __name__ == "__main__":
    main()
