# Lead intelligence research engine

A runnable first slice now lives in `leadintel/`: bounded public-website crawling, versioned evidence,
SQLite full-text search, configurable DFW signal tags and a local review dashboard.
Company/contact enrichment is queued **only when a flagged lead enters qualification**.
The contact scraper itself is not implemented yet. Tavily and Apify integrations are preview-only.

## Run the first version

Python 3.11+ with SQLite FTS5 support; no third-party packages or API keys required.

```bash
python -m leadintel demo
python -m leadintel search awarded --signal award --geography Collin
python -m leadintel serve
```

Open `http://127.0.0.1:8765` on the machine running the server. The demo uses clearly labelled
fictional fixtures and sends no network requests. The server binds only to loopback; it is not a hosted application.

For real public-site crawling and full commands, see [the first-version guide](docs/ENGINE_QUICKSTART.md).
This prototype uses SQLite to validate the engine without infrastructure dependencies.
PostgreSQL/FastAPI remain the production direction. Existing source research is preserved below.

## Construction intelligence source registry

Verified source identities and company social-profile associations for the first DFW contractor pilot. Start with [the readable registry](docs/SOURCE_REGISTRY.md) and [the implementation addition](docs/SOURCE_AND_SOCIAL_PLAN.md).

## Deliverables

- `data/source_registry.sqlite`: portable research database with company, source, platform, profile, coverage, evidence-check and search-history tables.
- `data/source_registry.json`: complete portable export, including rejected associations and unresolved aliases.
- `data/registry_seed.json`: curated companies, source sites and platform definitions.
- `data/research_review.json`: evidence-reviewed associations and actual public-index research records from 12 October 2026.
- `data/source_checks.json`: direct website retrieval checks, timestamps, fingerprints and published outbound links.

The workspace contained no existing client database. The six seed companies are research prospects, not paying clients or qualified apparel opportunities. The SQLite file is a research artifact; PostgreSQL remains the planned application database.

## Rebuild and verify

Use Python 3.11 or newer. No third-party packages are required. These commands assume your Python interpreter is available as `python`.

```powershell
python tools/build_registry.py
python -m unittest discover -s tests -v
python tools/search_socials.py --company kpost --limit 4
```

The last command only previews queries and estimated list-price cost. It sends no requests. Queries use stored company names and verified handles, and cover LinkedIn, Instagram, X/Twitter and Indeed by default. Other catalogued platforms can be selected with `--platform`.

To run searches, set `TAVILY_API_KEY` in the process environment and add `--execute`. `.env.example` documents the variable; this script does not automatically load `.env` files. Results are saved in the database's `search_attempts` table. The runner does not download social pages or send messages.

```powershell
python tools/search_socials.py --company polk --limit 4 --execute
```

The live Tavily transport has not been exercised with an API key. Initial searches in the research records were performed using the available web research tool, not Tavily. No fake results are substituted when a key is absent.

The runner reserves every attempt before network access and caps its shared ledger at 30 requests per UTC day and 900 per UTC month. Failed requests count conservatively. Basic Search is fixed at one credit/request, budgeted at $0.008 list price. The future full pipeline must share one budget ledger across all providers and stages; this runner's cap alone does not account for other applications or API accounts.

## Refresh sources

```powershell
python tools/verify_sources.py --ids kpost polk txdot
```

This performs ordinary public HTTP requests after a robots check and saves compact evidence. It does not fetch social/job-board pages, bypass access restrictions or collect entire sites. A failure remains visible. Newly discovered social links are **candidates** until reviewed in `approved_official_links`; a partner's account in a footer must never be automatically assigned to the company.

Add a company to the curated seed, run source verification, review its actual links, record public-index searches, then rebuild. Rebuilding refreshes generated review tables and preserves live `search_attempts` history; edit the JSON inputs rather than editing generated review tables directly. Preview and live queries read the stored `companies` table, so the application can later supply newly discovered prospects through the same interface.

All current search results are research candidates. Source identity, company-account association, individual claim verification, access permissions and commercial qualification remain separate.

