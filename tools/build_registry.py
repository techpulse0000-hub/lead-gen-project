"""Build a portable SQLite research registry and readable, reproducible exports."""
from __future__ import annotations

import hashlib
import json
import sqlite3
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def profile_identity(url):
    """Return platform and canonical PROFILE URL; reject posts, people and share links."""
    p = urllib.parse.urlsplit(url)
    if p.scheme not in ("http", "https") or p.username or p.password:
        return None
    host = (p.hostname or "").lower()
    parts = [urllib.parse.unquote(s) for s in p.path.split("/") if s]
    def at(domain):
        return host == domain or host.endswith("." + domain)
    if at("linkedin.com") and len(parts) == 2 and parts[0] == "company":
        return "linkedin", "https://www.linkedin.com/company/" + urllib.parse.quote(parts[1].lower(), safe="-&")
    if (at("x.com") or at("twitter.com")) and len(parts) == 1 and parts[0].lower() not in {"intent", "share", "home", "search", "i", "explore", "login"}:
        return "x", "https://x.com/" + parts[0].lower()
    if at("instagram.com") and len(parts) == 1 and parts[0].lower() not in {"p", "reel", "reels", "stories", "accounts", "explore", "share"}:
        return "instagram", "https://www.instagram.com/" + parts[0].lower() + "/"
    if at("facebook.com") and len(parts) == 1:
        if parts[0] == "profile.php":
            ident = urllib.parse.parse_qs(p.query).get("id", [""])[0]
            if ident.isdigit():
                return "facebook", "https://www.facebook.com/profile.php?id=" + ident
        elif parts[0].lower() not in {"share.php", "sharer.php", "sharer", "share", "login", "watch", "groups", "reel", "plugins", "dialog"}:
            return "facebook", "https://www.facebook.com/" + parts[0].lower() + "/"
    if at("youtube.com") and ((len(parts) == 2 and parts[0] in {"channel", "user", "c"}) or (len(parts) == 1 and parts[0].startswith("@"))):
        return "youtube", "https://www.youtube.com/" + "/".join(parts)
    if at("tiktok.com") and len(parts) == 1 and parts[0].startswith("@"):
        return "tiktok", "https://www.tiktok.com/" + parts[0].lower()
    if at("indeed.com") and len(parts) == 2 and parts[0] == "cmp":
        return "indeed", "https://www.indeed.com/cmp/" + urllib.parse.quote(parts[1].lower(), safe="-")
    return None


def approved_profiles(company_id, check, approvals):
    """An outbound link is only approved after company-specific evidence review."""
    approved = {profile_identity(u) for u in approvals.get(company_id, [])}
    output, seen = [], set()
    for url in check.get("social_links", []):
        identity = profile_identity(url)
        if identity and identity in approved and identity not in seen:
            output.append((url, identity))
            seen.add(identity)
    return output


def load(name, root=ROOT):
    return json.loads((root / "data" / name).read_text(encoding="utf-8"))


def build_payload(root=ROOT):
    seed, review = load("registry_seed.json", root), load("research_review.json", root)
    checks = {r["id"]: r for r in load("source_checks.json", root)}
    reviews = {r["id"]: r for r in review["source_identity_reviews"]}
    sources = []
    for item in seed["sources"] + [dict(id=c["id"], name=c["name"] + " official website", url=c["website"], category="company", geography=c["location"], authority="company_first_party", signals=["hiring", "project_start", "expansion"], caution="Company self-report; verify each event, its timing and apparel relevance separately.") for c in seed["companies"]]:
        check = checks.get(item["id"], {})
        manual = reviews.get(item["id"], {})
        identity_verified = check.get("access_status") == "retrieved" or manual.get("identity_verified", False)
        sources.append(dict(item, identity_verified=identity_verified,
            verification_url=manual.get("evidence_url", item["url"]),
            verification_note=manual.get("observation", "Curated organization identity and retrieved official/publisher page inspected."),
            checked_at=check.get("checked_at", review["review_date"]),
            direct_access=check.get("access_status", "not_checked"),
            final_url=check.get("final_url", item["url"]),
            access_mode=item.get("preferred_access", "selective_public_fetch" if check.get("access_status") == "retrieved" else "indexed_search_and_manual_review"),
            research_links=check.get("research_links", [])))
    profiles = []
    for company in seed["companies"]:
        check = checks.get(company["id"], {})
        for original, (platform, canonical) in approved_profiles(company["id"], check, review["approved_official_links"]):
            profiles.append(dict(company_id=company["id"], platform=platform, url=canonical, original_url=original,
                verification_status="official_site_linked", evidence_url=check.get("final_url", company["website"]),
                checked_at=check["checked_at"], content_access="not_directly_checked",
                note="Company-specific outbound link inspected and approved. This verifies association, not current feed completeness or platform badge status."))
    for p in review["additional_profiles"]:
        identity = profile_identity(p["url"])
        if identity is None or identity[0] != p["platform"]:
            raise ValueError("Invalid profile identity: " + p["url"])
        profiles.append(dict(p, url=identity[1], original_url=p["url"], checked_at=review["review_date"], content_access="public_index_observed"))
    searches = []
    platform_by_id = {p["id"]: p for p in seed["platforms"]}
    for batch in review["search_batches"]:
        for platform, query in batch["queries"].items():
            matches = batch["results"].get(platform, [])
            searches.append(dict(id=f"{batch['company_id']}:{platform}:{review['review_date']}", company_id=batch["company_id"], platform=platform,
                query=query, domains=platform_by_id[platform]["domains"], checked_at=review["review_date"],
                provider="research_web_search", status="matches_returned" if matches else "no_relevant_results_returned",
                result_urls=matches, coverage="partial_public_index",
                note="Curated relevant results from a multi-query batch. Empty results do not establish absence of an account or activity."))
    surfaces = []
    for c in seed["companies"]:
        for platform in seed["platforms"]:
            ps = [p for p in profiles if p["company_id"] == c["id"] and p["platform"] == platform["id"]]
            qs = [s for s in searches if s["company_id"] == c["id"] and s["platform"] == platform["id"]]
            surfaces.append(dict(company_id=c["id"], platform=platform["id"], profile_count=len(ps),
                ownership_status="verified_association" if any(p["verification_status"] in ("official_site_linked", "corroborated_identity") for p in ps) else "candidate" if ps else "not_established",
                search_status=qs[-1]["status"] if qs else "not_searched", last_searched=qs[-1]["checked_at"] if qs else None,
                monitoring_state="not_scheduled", coverage="partial_public_index"))
    return dict(schema_version=1, as_of=review["review_date"], market=seed["market"], companies=seed["companies"], sources=sources,
        platforms=seed["platforms"], company_profiles=profiles, company_surfaces=surfaces,
        source_checks=list(checks.values()), search_checks=searches, observations=review["observations"],
        rejected_links=review["rejected_links"], profile_aliases=review["profile_aliases"])


SCHEMA = """
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS companies (id TEXT PRIMARY KEY, name TEXT NOT NULL, website TEXT NOT NULL, segment TEXT NOT NULL, location TEXT NOT NULL, relationship TEXT NOT NULL, record_json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS sources (id TEXT PRIMARY KEY, name TEXT NOT NULL, url TEXT NOT NULL, category TEXT NOT NULL, identity_verified INTEGER NOT NULL CHECK(identity_verified IN (0,1)), direct_access TEXT NOT NULL, access_mode TEXT NOT NULL, record_json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS platforms (id TEXT PRIMARY KEY, name TEXT NOT NULL, access_mode TEXT NOT NULL, record_json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS company_profiles (id TEXT PRIMARY KEY, company_id TEXT NOT NULL REFERENCES companies(id), platform TEXT NOT NULL REFERENCES platforms(id), url TEXT NOT NULL, verification_status TEXT NOT NULL CHECK(verification_status IN ('official_site_linked','corroborated_identity','candidate')), evidence_url TEXT NOT NULL, checked_at TEXT NOT NULL, record_json TEXT NOT NULL, UNIQUE(company_id,platform,url));
CREATE TABLE IF NOT EXISTS company_surfaces (company_id TEXT NOT NULL REFERENCES companies(id), platform TEXT NOT NULL REFERENCES platforms(id), ownership_status TEXT NOT NULL, search_status TEXT NOT NULL, record_json TEXT NOT NULL, PRIMARY KEY(company_id,platform));
CREATE TABLE IF NOT EXISTS source_checks (id TEXT PRIMARY KEY REFERENCES sources(id), checked_at TEXT NOT NULL, access_status TEXT NOT NULL, record_json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS search_checks (id TEXT PRIMARY KEY, company_id TEXT NOT NULL REFERENCES companies(id), platform TEXT NOT NULL REFERENCES platforms(id), query TEXT NOT NULL, checked_at TEXT NOT NULL, status TEXT NOT NULL, record_json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS observations (id TEXT PRIMARY KEY, company_id TEXT NOT NULL REFERENCES companies(id), platform TEXT NOT NULL REFERENCES platforms(id), url TEXT NOT NULL, status TEXT NOT NULL, record_json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS search_attempts (id INTEGER PRIMARY KEY, created_at TEXT NOT NULL, company_id TEXT NOT NULL REFERENCES companies(id), platform TEXT NOT NULL REFERENCES platforms(id), query TEXT NOT NULL, status TEXT NOT NULL, estimated_cost_microusd INTEGER NOT NULL, record_json TEXT NOT NULL DEFAULT '{}');
CREATE INDEX IF NOT EXISTS idx_profiles_company ON company_profiles(company_id,platform);
CREATE INDEX IF NOT EXISTS idx_sources_access ON sources(category,direct_access);
CREATE INDEX IF NOT EXISTS idx_search_time ON search_attempts(created_at);
"""


def write_database(payload, path):
    db = sqlite3.connect(path)
    db.executescript(SCHEMA)
    j = lambda r: json.dumps(r, ensure_ascii=False, sort_keys=True)
    with db:
        db.execute("INSERT OR REPLACE INTO metadata VALUES (?,?)", ("as_of", payload["as_of"]))
        for r in payload["companies"]:
            db.execute("INSERT INTO companies VALUES (?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET name=excluded.name,website=excluded.website,segment=excluded.segment,location=excluded.location,relationship=excluded.relationship,record_json=excluded.record_json", (*[r[k] for k in ("id","name","website","segment","location","relationship")], j(r)))
        for r in payload["sources"]:
            db.execute("INSERT INTO sources VALUES (?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET name=excluded.name,url=excluded.url,category=excluded.category,identity_verified=excluded.identity_verified,direct_access=excluded.direct_access,access_mode=excluded.access_mode,record_json=excluded.record_json", (r["id"],r["name"],r["url"],r["category"],int(r["identity_verified"]),r["direct_access"],r["access_mode"],j(r)))
        for r in payload["platforms"]:
            db.execute("INSERT INTO platforms VALUES (?,?,?,?) ON CONFLICT(id) DO UPDATE SET name=excluded.name,access_mode=excluded.access_mode,record_json=excluded.record_json", (r["id"],r["name"],r["access_mode"],j(r)))
        # Refresh generated review tables; never delete companies, sources or live search history.
        for table in ("company_profiles","company_surfaces","source_checks","search_checks","observations"):
            db.execute("DELETE FROM " + table)
        for r in payload["company_profiles"]:
            ident = hashlib.sha256((r["company_id"]+":"+r["url"]).encode()).hexdigest()[:24]
            db.execute("INSERT INTO company_profiles VALUES (?,?,?,?,?,?,?,?)", (ident,*[r[k] for k in ("company_id","platform","url","verification_status","evidence_url","checked_at")],j(r)))
        for r in payload["company_surfaces"]:
            db.execute("INSERT INTO company_surfaces VALUES (?,?,?,?,?)", (r["company_id"],r["platform"],r["ownership_status"],r["search_status"],j(r)))
        for r in payload["source_checks"]:
            db.execute("INSERT INTO source_checks VALUES (?,?,?,?)", (r["id"],r["checked_at"],r["access_status"],j(r)))
        for r in payload["search_checks"]:
            db.execute("INSERT INTO search_checks VALUES (?,?,?,?,?,?,?)", (*[r[k] for k in ("id","company_id","platform","query","checked_at","status")],j(r)))
        for r in payload["observations"]:
            db.execute("INSERT INTO observations VALUES (?,?,?,?,?,?)", (*[r[k] for k in ("id","company_id","platform","url","status")],j(r)))
    if db.execute("PRAGMA foreign_key_check").fetchall():
        raise ValueError("Foreign-key audit failed")
    db.close()


def markdown(payload):
    profiles = payload["company_profiles"]
    verified = [p for p in profiles if p["verification_status"] != "candidate"]
    lines = ["# Verified source registry and contractor social profiles", "", f"Reviewed {payload['as_of']}. Initial market: {payload['market']}.", "",
        f"The registry contains {len(payload['sources'])} company, public-record and industry sources, {len(payload['platforms'])} social/job platforms, {len(payload['companies'])} research prospects, {len(verified)} verified or corroborated profile associations, and {len(profiles)-len(verified)} unconfirmed employer-page candidates.", "",
        "A verified source identity is not a blanket guarantee that every claim is true or that automated access is available. Profile association, content access, claim verification and commercial qualification are separate. These companies are research prospects, not customers or qualified apparel leads.", "",
        "## Company profiles", "", "Official site linked means a company-specific link was found on its website and manually reviewed. Corroborated identity means the indexed profile matches the business, geography and official domain. Candidate means ownership is unresolved. Neither label asserts a platform verification badge.", ""]
    for c in payload["companies"]:
        lines += [f"### {c['name']}", "", f"[{c['website']}]({c['website']}) · {c['segment']} · {c['location']}", "", "| Surface | Profile | Verification | Evidence |", "|---|---|---|---|"]
        for p in [p for p in profiles if p["company_id"] == c["id"]]:
            lines.append(f"| {p['platform']} | [Open profile]({p['url']}) | {p['verification_status'].replace('_',' ')} | [Verification source]({p['evidence_url']}) |")
        missing = [s["platform"] for s in payload["company_surfaces"] if s["company_id"] == c["id"] and not s["profile_count"]]
        lines += ["", "No company profile established in this pass: " + ", ".join(missing) + ". This does not mean the company has no account.", ""]
    lines += ["## Source websites", "", "| Source | Category | Identity checked | Direct access observed | Intended route |", "|---|---|---|---|---|"]
    for s in payload["sources"]:
        lines.append(f"| [{s['name']}]({s['url']}) | {s['category']} | {'Yes' if s['identity_verified'] else 'Pending'} | {s['direct_access']} | {s['access_mode']} |")
    lines += ["", "## How each source should be used", ""]
    for s in payload["sources"]:
        lines += [f"- **{s['name']}:** {s['caution']} Verification: [source]({s['verification_url']})."]
    lines += ["", "## Social and job platform access", "", "| Platform | Initial access | Limits and verification |", "|---|---|---|"]
    for p in payload["platforms"]:
        lines.append(f"| {p['name']} | {p['access_mode']} | {p['notes']} [Documentation]({p['api_url']}); [policy]({p['policy_url']}). |")
    lines += ["", "## Search coverage", "", "All six companies were included in four domain-filtered searches: LinkedIn, Instagram, X/Twitter and Indeed (24 submitted queries). The web index returned useful LinkedIn and Indeed matches; it returned no relevant Instagram or X results in these batches, despite official websites linking to several accounts. This is a real coverage gap, not evidence of inactivity. Facebook, YouTube and TikTok accounts were inventoried where linked; their feeds were not searched in this pass.", "",
        "Live background monitoring is not running. The reusable search runner defaults to a preview and requires a Tavily API key for execution. All returned items remain research candidates until source, date, company, geography and commercial relevance are checked.", "", "## Initial research observations", ""]
    for o in payload["observations"]:
        lines += [f"- **{o['company_id']} — {o['status'].replace('_',' ')}:** {o['summary']} [Evidence]({o['url']}). Next: {o['next_action']}"]
    lines += ["", "## Rejected associations", ""]
    for r in payload["rejected_links"]:
        lines += [f"- [{r['url']}]({r['url']}): {r['reason']}"]
    lines += ["", "## Data files", "", "The JSON export retains exact provenance, source-access checks, search coverage, rejected links and unresolved aliases. SQLite adds indexed relational tables and a usage ledger. It is a portable research deliverable; PostgreSQL remains the application database selected in the main plan.", ""]
    return "\n".join(lines)


def main():
    payload = build_payload()
    write_database(payload, ROOT / "data/source_registry.sqlite")
    (ROOT / "data/source_registry.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False)+"\n", encoding="utf-8")
    (ROOT / "docs").mkdir(exist_ok=True)
    (ROOT / "docs/SOURCE_REGISTRY.md").write_text(markdown(payload), encoding="utf-8")
    print(json.dumps({k: len(v) for k,v in payload.items() if isinstance(v,list)}))


if __name__ == "__main__":
    main()
