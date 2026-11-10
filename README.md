# Lead intelligence research engine

For a concise project overview, major updates, current limitations and directory guide, see
[notes.txt](notes.txt).

A runnable first slice now lives in `leadintel/`: company discovery through broad web search,
structured LLM classification, explainable lead scoring, bounded public-website crawling,
versioned evidence, SQLite full-text search and a local dashboard.
Company/contact enrichment is initiated manually only after a lead has passed qualification. Tavily discovery has a live adapter and requires
an API key. Structured classification requires an OpenAI API key. Apify website evidence enrichment
is connected as an optional manual step after a result passes the lead score.

## Run the first version

Python 3.11+ with SQLite FTS5 support; no third-party packages required. Tavily is required for
company discovery; the crawler and offline demo need no API key.

```bash
python -m leadintel demo
python -m leadintel search awarded --signal award --geography Collin
python -m leadintel serve
```

Open `http://127.0.0.1:8765` on the machine running the server. **Find companies** is the primary flow:
choose a construction trade and location. The app defaults to a DFW pilot set of 15 ranked
queries led by contract awards, project starts and expansions, with only two explicit bulk-hiring
queries; select 1–10 to run as one batch. The
larger experimental bank remains available for exploration. Connect your Tavily key
in the local app to search. The search stage can run without an OpenAI key; returned results are saved
until the classifier is connected under **Classification review**. Both keys stay in server memory and
must be entered again after a server restart. Previewing queries is free; each selected Basic search
reserves one Tavily credit.
No company names, seed companies or website checklist are required. Results group candidate company
names identified through strict structured output and retain evidence URLs. Plain code scores signal
strength, source reliability, freshness and field-workforce evidence. A single vacancy receives zero
signal points and cannot pass the lead threshold. Unresolved and below-threshold pages remain visible.

The **Classification review** page processes stored results with the fixed `gpt-4o-mini` model in
batches of up to ten without sending new Tavily searches. It shows true overall progress, keeps
completed batches when a retry is needed, and orders completed results from highest score to lowest.
As of 16 October 2026, the local database contains 325 completed classifications, no pending or
failed classifications, and 23 results scoring at least 65. These counts change as searches are added.
The page displays the former regex output beside the LLM classification and score. Every
passing result also has **Would call**, **Would not call**, and **Unsure** controls with an optional
note, so the required 20–30 lead sales review is recorded beside the evidence and can guide threshold
tuning. Each lead heading is the original-source link; its domain appears beneath the heading, and
hover or keyboard focus shows the compact title-and-domain preview. The separate alternative-links
section remains available for inaccessible destinations without duplicating the source heading.

### Classification and scoring

The classifier receives only the stored title, snippet, source URL/host, originating search query and
provider-reported date. It does not read the full destination page during this stage. Strict output
records the named company, construction-business status, signal type, explicit event date and field
roles, evidence strength, source reliability, source ownership, a short summary and any rejection
reason. A mismatched or unsupported company-website claim is discarded instead of failing the whole
ten-result batch.

Plain code then scores the structured result: signal quality contributes up to 35 points, evidence
strength 15, source reliability 25, freshness 15 and explicit field-workforce evidence 10. A result
must clearly name a construction business and reach 65/100 to pass. Contract awards receive 35 signal
points, project starts 32, expansions 28, bulk hiring 20, and a single vacancy receives zero.

Passing leads can be enriched manually through Apify's Website Content Crawler. The database rejects
an Apify run unless the result has a completed classification and score of at least 65. Project-source
runs fetch one page; a company-owned source can inspect up to five careers, jobs, projects or news
pages. Each request also sends a $0.25 maximum-charge cap. This evidence enrichment does not collect
people or contact details and does not bypass the qualification gate for later contact enrichment.

For a verified project contractor, **Find operational contacts** calls the configured Apify
`pipelinelabs/lead-scraper-apollo-zoominfo-lusha-ppe` Actor. Each click is bounded to five candidate profiles and a
$0.10 maximum Actor charge. It begins with focused operations and project-management roles, stores
only the returned professional contact fields, and uses the
fixed `gpt-4o-mini` model to assess role suitability and rank candidates. OpenAI must be connected
before a contact lookup; unsuitable or unclear roles are excluded. The Actor
performs the profile and email lookup; GPT does not run the scraper and does not make an email
deliverable or a person's employment current merely by reviewing it. A project lead must have completed general-contractor verification
before the contact action can run. The request uses the company name and searches project,
operations and construction manager titles, excluding principal titles. It does not restrict
location, so returned people may work outside the project region. An empty dataset is distinguished from records the parser cannot read:
unreadable records fail explicitly instead of reporting zero matches. LinkedIn profile verification
is not email verification; returned emails are labelled provider-found.

Contact regression tests use mocked responses. They do not establish that live searches return
contacts. An unfiltered OHT run returned three contacts, but the manager-filtered integration has
not yet been verified with a live run. Provider emails and company matches require independent checking.
The contact workflow checks Apify run status before reading results, including a free-user limit
reported on a nominally successful run. Failures display a reason where available and an Apify run
ID for investigation. An empty dataset alone cannot establish why no records were returned.

Passing **project-start and contract-award** leads expose **Find and verify general contractor**;
new confirmed findings receive a separate AI review against the cited records, requiring explicit
evidence tying the named contractor to the same project. This review reduces false positives but is
not independent proof. Earlier confirmations were not automatically re-audited. The unsupported
Trademark Dunham Pointe finding was corrected to unresolved, preserving the prior finding in its record.
hiring and other non-project leads do not show that action. One click reuses the original lead, any
completed exact-page verification and any Apify pages already collected. It then follows a ranked,
bounded source ladder and uses the fixed `gpt-4o-mini` classifier after each stage. Public awards
prioritize final award records, bid results and meeting decisions; private project starts prioritize
issued permits, first-party announcements and planning records. The earlier broad web method is the
last fallback. A fully unresolved lookup can spend up to five Tavily Basic credits, while confirmed
results stop immediately. The classifier separates the developer,
owner and architect from the prime/general contractor. A contractor is confirmed only when a returned
source establishes a final award, approval, executed contract, permit, notice to proceed or an explicit
active general-contractor role. Proposed awards and pending votes are labelled **decision pending**
until a later source confirms the outcome. This distinction is made by the structured AI review of the
complete supplied evidence rather than by a fixed keyword list. Ordinary code validates the returned
status and required evidence. A confirmed result must include a named project and at least one cited
source. Exact duplicate source pages are grouped in Classification review; an existing completed
project verification is reused without another Tavily or OpenAI request. The result, status,
explanation and evidence URLs are stored
beside the lead with all supporting evidence.

The complete ranking, verification findings, access limits and API-key requirements are in
[ranked contractor-lookup methods](docs/CONTRACTOR_LOOKUP_METHODS.md).

The two AI stages have different inputs. Initial classification reads the stored search-result title,
snippet, source, reported date and originating query. Contractor verification runs only on qualifying
project-start and contract-award leads and reads the original lead plus bounded targeted-search and
available Apify evidence. The AI makes the semantic contractor-status decision; application code
validates its structured response, evidence URLs and status/confidence consistency.

**Monitor construction sources** is the secondary workflow for repeatedly checking curated project
trackers, official records and construction publications. Contractor company websites are excluded
from its default catalogue; they belong in post-qualification enrichment. See the
[monitor-source research](docs/MONITOR_SOURCE_RESEARCH.md) for the reviewed DFW, Texas, national and
niche sources and their access limitations.
Both flows run in the background with progress, history and a stop control. See the
[company-discovery guide](docs/COMPANY_DISCOVERY.md) for setup and limitations.

The optional CLI demo uses clearly labelled fictional fixtures and sends no network requests;
find those records under **Search evidence**. Live research results exclude demo records.
The server binds only to loopback; it is not a hosted application.

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

The current suite contains 89 tests. Provider, classifier and Apify transports are mocked in
tests, so the suite spends no external credits.

The last command only previews queries and estimated list-price cost. It sends no requests. Queries use stored company names and verified handles, and cover LinkedIn, Instagram, X/Twitter and Indeed by default. Other catalogued platforms can be selected with `--platform`.

The older social-search runner is now preview-only. Its `--execute` path is disabled to prevent
spending through a separate legacy ledger. Use the dashboard for live web discovery. Initial research
records were produced using the available research tool, not the app's Tavily connection.

The new engine reserves every attempt before network access, using a shared provider ledger capped
at 30 Basic credits per UTC day and 900 per UTC month. Failed attempts count conservatively. This
local cap does not include usage by other applications or elsewhere in your provider account.
The local history records completed live Tavily requests. The new multi-query selection flow is
covered by offline provider tests and has produced live results; controlled repeated measurement of
qualified leads per query and provider credit is still required.
The ranking method, observed examples and demoted terms are documented in
[the search-term validation report](docs/SEARCH_TERM_VALIDATION.md).

## Refresh sources

```powershell
python tools/verify_sources.py --ids kpost polk txdot
```

This performs ordinary public HTTP requests after a robots check and saves compact evidence. It does not fetch social/job-board pages, bypass access restrictions or collect entire sites. A failure remains visible. Newly discovered social links are **candidates** until reviewed in `approved_official_links`; a partner's account in a footer must never be automatically assigned to the company.

Add a company to the curated seed, run source verification, review its actual links, record public-index searches, then rebuild. Rebuilding refreshes generated review tables and preserves live `search_attempts` history; edit the JSON inputs rather than editing generated review tables directly. Preview and live queries read the stored `companies` table, so the application can later supply newly discovered prospects through the same interface.

All current search results are research candidates. Source identity, company-account association, individual claim verification, access permissions and commercial qualification remain separate.

