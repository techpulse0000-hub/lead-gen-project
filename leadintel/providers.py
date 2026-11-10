"""Reviewable provider plans only. This module never sends paid API requests."""
from datetime import date, datetime, timezone
from urllib.parse import urlsplit

from .crawler import SIGNALS


def clean(value, limit=200):
    if not isinstance(value,str) or not value.strip() or len(value)>limit:
        raise ValueError("Nonempty bounded text required")
    return value.strip().replace('"',' ').replace('\n',' ').replace('\r',' ')


def search_plan(company=None, location="Dallas", signal="award", domains=(), since=None,
                advanced=False):
    if signal not in SIGNALS:
        raise ValueError("Unknown signal")
    location=clean(location)
    identity='"'+clean(company)+'"' if company else "construction contractor"
    if since:
        date.fromisoformat(since)
    included=[]
    for d in domains:
        p=urlsplit("https://"+d)
        if not p.hostname or p.netloc!=d or p.path or p.username or p.password:
            raise ValueError("Domain filter must be a bare hostname")
        included.append(d)
    if len(included)>10:
        raise ValueError("At most ten domains in preview")
    queries=[identity+' "'+location+'" "'+word+'"' for word in SIGNALS[signal][:2]]
    requests=[]
    for query in queries:
        body={"query":query,"search_depth":"advanced" if advanced else "basic",
              "auto_parameters":False,"include_answer":False,"max_results":5,
              "include_usage":True,"include_raw_content":False}
        if included:
            body["include_domains"]=included
        if since:
            body["start_date"]=since
        requests.append(body)
    credits=len(requests)*(2 if advanced else 1)
    return {"mode":"preview","requests_sent":0,"provider":"tavily",
            "requests":requests,"estimated_credits":credits,
            "estimated_list_price_usd":round(credits*.008,6),
            "price_as_of":"2026-10-12","coverage":"partial_provider_web_index",
            "requires_local_verification":["company_identity","project_or_job_geography","event_date","commercial_relevance"],
            "notice":"This command previews requests. Use the dashboard's Find companies flow for live discovery with its provider ledger."}


def social_plan(account_url, platform, since, max_posts=20):
    if platform not in ("linkedin","instagram") or not 1<=max_posts<=20:
        raise ValueError("Supported platform required; post limit 1–20")
    stamp=datetime.fromisoformat(since.replace("Z","+00:00"))
    if stamp.tzinfo is None:
        raise ValueError("UTC or timezone-aware cutoff required")
    cutoff=stamp.astimezone(timezone.utc).isoformat()
    p=urlsplit(account_url)
    if p.scheme!="https" or p.username or p.password or p.query or p.fragment or p.port:
        raise ValueError("Use a plain HTTPS account URL")
    host=(p.hostname or "").lower()
    if platform=="linkedin":
        if host not in ("linkedin.com","www.linkedin.com") or not p.path.startswith("/company/") or len(p.path.strip("/").split("/"))!=2:
            raise ValueError("Company LinkedIn account required, not a person")
        actor="harvestapi/linkedin-company-posts"
        inputs={"targetUrls":[account_url],"maxPosts":max_posts,"postedLimitDate":cutoff,
                "scrapeComments":False,"scrapeReactions":False,
                "includeReposts":False,"includeQuotePosts":False}
    else:
        parts=p.path.strip("/").split("/")
        if host not in ("instagram.com","www.instagram.com") or len(parts)!=1 or not parts[0] or parts[0] in ("p","reel","explore","stories"):
            raise ValueError("Company Instagram profile URL required")
        actor="apify/instagram-scraper"
        inputs={"directUrls":[account_url],"resultsType":"posts","resultsLimit":max_posts,
                "onlyPostsNewerThan":cutoff}
    return {"mode":"preview","requests_sent":0,"actor":actor,"input":inputs,
            "requires":["company_account_association","actor_access_assessment","run_charge_reservation"],
            "notice":"Preview only; company social-post evidence is separate from qualification-only contact enrichment."}
