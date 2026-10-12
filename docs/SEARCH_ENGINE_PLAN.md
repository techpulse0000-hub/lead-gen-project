# Specialized search engine tool — proposed build plan

Prepared 12 October 2026. Planning only: this document specifies a future tool; it does not activate crawling, paid search, recurring monitoring, an AI agent or outreach.

## 1. Product intent and corrected scope

Build the software that discovers, retrieves, indexes and searches relevant public information. An AI agent may later direct the tool through a bounded interface, but the tool must also function through configuration, an API or a command line without an AI model.

The source registry and six contractor companies are seed data and test cases, not the intended product. Research candidates must remain distinct from verified business facts and qualified apparel opportunities.

First configuration: lead intelligence for a screen-printing/embroidery shop, construction contractors, Dallas/Tarrant/Collin/Denton counties. Initial signals: hiring, contract awards, mobilization and expansion. Later categories use configuration and source adapters within the same engine.

The separate company/contact enrichment scraper is a later module. This milestone may identify a company and candidate official website and emit a handoff; it does not promise decision-maker identification, email discovery or verified apparel demand.

## 2. Architectural decision

Build an owned, focused crawler and searchable index first. Do not make the engine merely a wrapper around a third-party search API.

Support three access modes:

- Local index search: search content previously retrieved by our crawler; requires no external search provider or AI.
- Targeted crawl and refresh: retrieve approved public source sections and follow relevant links within limits, building and refreshing the owned index.
- Optional external discovery: a provider adapter finds URLs outside our existing coverage. These are index hits/candidates until fetched and investigated. The engine remains usable when this adapter is disabled.

External discovery addresses a real limitation: a crawler cannot discover the entire web from a few seeds. A bounded owned index will initially cover selected sources, not all websites or complete social feeds. Broader coverage comes from new seeds, reviewed outbound sources and optional external discovery.

Information retrieval does not require AI. Company/event interpretation can later use deterministic rules, human review or an agent. Unknown facts must remain unknown.

## 3. End-to-end behavior

1. Accept a structured research request or scheduled watch.
2. Search the owned index and report corpus coverage and freshness.
3. If requested, compile a bounded crawl plan for source sections likely to fill gaps.
4. Validate URLs, source policy and budgets before queuing network work.
5. Retrieve permitted content, extract readable text/links/metadata and retain provenance.
6. Index new content, compare versions and group duplicates or syndicated material.
7. Return ranked evidence documents and company/event candidates with reasons and uncertainties.
8. Emit an idempotent enrichment handoff when explicitly requested or when a configured candidate rule is satisfied.

Local index search is synchronous. Crawl/discovery work is asynchronous and returns a job ID. A search must never silently initiate unbounded network activity.

## 4. Specialization through a research profile

A versioned profile defines:

- Shop products and supported decoration methods; unknown shop capabilities stay unset.
- Target company categories and operational roles.
- Geographic boundaries, city aliases and explicit project-location rules.
- Signal vocabulary and synonyms: mobilization, groundbreaking, awarded, expansion, recruiting and equivalents.
- Negative matches: bakery versus BakerTriangle, historical openings, unrelated partners, irrelevant regions and unrelated project roles.
- Source types, permitted routes and authority for particular claims.
- Relevant page sections: company news, projects, careers, government award records and regional reporting.
- Freshness windows, query templates, ranking weights and crawl limits.

Mentioning Dallas is not sufficient for DFW relevance. Preserve company headquarters, project location and job location separately. Ambiguous locality names, remote vacancies and missing locations must be reviewable.

Signals narrow search and organize evidence; they do not establish demand. A contract value or number of advertised jobs cannot become an apparel quantity.

## 5. Tool components

| Component | Responsibility |
|---|---|
| Research profile and query compiler | Validate structured requests; expand configured synonyms and geography; compile local and provider queries. |
| Source registry and adapters | Retain source identity, supported claims, geography, access route and policy. |
| Crawl frontier | Prioritize and deduplicate URLs, track depth, leases, retries and next refresh time. |
| Policy gateway | Enforce permissions, URL safety and quotas before every network operation. |
| Fetcher | Retrieve bounded public content with identified user agent, timeouts, redirect checks and rate limits. |
| Parser and document store | Extract readable content, title, links and date evidence; retain permitted excerpts and fingerprints. |
| Search index and ranker | Index documents and metadata; apply filters and return explainable ranking. |
| Version and lineage tracker | Detect changes and preserve original versus syndicated evidence relationships. |
| Candidate and handoff interface | Store tentative company/event references; queue enrichment without promoting them to qualified leads. |
| Job and coverage interface | Expose results, failures, blocked sources, deferred work, spending and freshness. |

First source adapters: static HTML news/project/careers pages, RSS/Atom where present, sitemaps and bounded text-readable PDFs. Sitemaps are URL hints, not proof that content is current. A modified date is not automatically an event date.

Scanned PDF OCR, broad JavaScript rendering and authenticated government/social integrations are later additions if demonstrated coverage gaps justify them. Portals with dedicated APIs need explicit adapters; generic HTML fetching is not sufficient for every source.

## 6. Crawling strategy and source admission

Seed the engine from the existing 19-source registry, preserving each recorded access status. Not every source is crawlable.

Prioritize feeds and relevant section landing pages, then same-site links with matching paths, titles and anchor text. Use bounded pagination and sitemap processing. Ignore session URLs, infinite calendars, arbitrary search-result combinations, downloadable executables and irrelevant media.

New external links enter a source-candidate queue. Existing permitted domains/sections can be queued automatically within their policy. A new domain must pass source-admission rules before fetching: identity/route assessment, public URL checks, robots policy, source restrictions and budget allocation. An initial human review gate for new domains is proposed; later carefully defined source classes can have automatic admission. This allows expansion without granting the agent unrestricted browsing.

Treat official employer ATS domains as separately admitted sources; do not follow them merely because they are linked. Corporate social links can be retained for later enrichment, but are not permission to scrape feeds.

Social/job platforms retain indexed-search/manual or explicitly approved API routes from the registry. Access blocks are visible coverage gaps, not a reason to circumvent controls.

## 7. Search interface and output contract

Proposed operations:

- search_index(request): search stored content without network requests.
- plan_research(request): preview sources, queries, maximum requests and budget reservations.
- submit_research(plan_id): enqueue the approved-scope plan and return a job ID.
- get_job(job_id): progress, results, failures, deferred work and usage.
- get_evidence(document_id): document provenance, permitted excerpt, retrieval status and dates.
- request_refresh(scope): bounded refresh using stored source policy.
- request_enrichment(candidate_id): emit a separate, deduplicated enrichment task.

Agents submit structured data, never arbitrary SQL, shell commands, executable parsers or unrestricted fetch instructions.

Request fields: profile ID/version, query terms, exact phrases, exclusions, source/domain filters, signal types, company identifier or aliases, geographic scope, event-date range, publication-date range, unknown-date inclusion, result limit and network mode.

Support AND/OR/exclusion and phrase searches locally. Parse and validate the query rather than exposing raw database expressions. Translate provider queries within that provider's supported capabilities and report any unsupported filters.

Each result includes:
document ID; original/final URL; source ID/type; title; evidence excerpt and locator; retrieved time; separately recorded publication/event/modified dates with evidence and uncertainty; company/project/job geography where available; matched terms; ranking factors; source lineage; content hash/version; access method; verification status; and coverage limitations.

A provider snippet remains provider evidence with its own origin. Do not pretend a failed fetch produced full-page evidence. Missing date/geography remains explicit. Local date filters must distinguish unknown dates; provider time filters never verify event timing.

## 8. Ranking, interpretation and deduplication

Use lexical full-text relevance plus configurable, explainable factors: identity match, target geography, signal vocabulary, source authority for the claim, supported timing and original-source status. Penalize stale or ambiguous results. Hard filters and unknown-field rules take precedence over boosts.

Keep lexical search score, source/identity confidence, event verification and commercial qualification separate. None is a purchase probability. Do not add an AI-based ranker or vector database to the first build unless evaluation identifies a need.

Deterministic extraction can identify company-name mentions, project references and candidate dates, always tied to supporting text. It cannot reliably establish all real-world relationships automatically. Ambiguous entities and conflicting claims remain unresolved.

Normalize URLs conservatively; tracking parameters can be removed, meaningful document/job identifiers cannot. Use exact hashes for identical content and near-duplicate detection as a grouping hint. Canonical tags and textual similarity alone must not erase conflicting evidence. Cross-posted releases share lineage and count once for corroboration.

Handoff states:
document discovered → company/event candidate → enrichment queued → enriched candidate → separately reviewed opportunity.
Indexing or enrichment never automatically means qualified.

## 9. Software-enforced boundaries

These policies apply equally to agents, scheduled jobs, CLI users and retries:

- Allow only public HTTP(S) fetches; reject credentials in URLs, local/private/link-local addresses and metadata endpoints.
- Validate every redirect and connect only to validated public addresses; use network egress restrictions to prevent DNS rebinding and validation/connect gaps.
- Respect source policy and robots rules; record robots retrieval and decisions. For this product, robots network failures defer crawling; no assumption that allowed robots access grants every other permission.
- No login, CAPTCHA or paywall bypass; no arbitrary form submissions or platform actions.
- Bound pages, depth, bytes, execution time, concurrent requests and retries. Enforce decompressed-size and parser resource limits.
- Honor retry delays and use backoff; retries consume shared quotas.
- Enforce quotas transactionally before requests, including concurrent workers. Kill switch and per-source pause are required.
- Separate downloaded text from executable instructions. Documents cannot change tools, policy, secrets or agent instructions.
- Store keys server-side; redact logs and do not upload credentials.
- Use authenticated tool endpoints, per-shop profile boundaries and isolation of private findings if more than one customer is supported.
- Persist job checkpoints, leases and idempotency keys. Restarting a worker must not lose accounting or duplicate records.

Proposed initial engineering defaults, subject to pilot measurement:
crawl depth 3; 20 content pages per job; 30 HTTP requests per domain/day; 200 total outbound crawler HTTP requests/day; four concurrent fetches globally and one per host; at least two seconds between host requests; 20-second fetch timeout; two retries; 3 MB decompressed HTML and 10 MB PDF limits. Robots, feeds, sitemaps, redirects and retries count toward request allowances. Crawl depth is not a complete limit: sitemap and pagination fan-out also have explicit caps.

External search retains existing ceilings of 30 calls/UTC day and 900/UTC month. Preserve proposed variable spending ceilings of $1/day and $20/month across enabled metered research adapters. Request ceilings and money ceilings both apply; exhaustion of either defers work. Pricing must be configured from revalidated provider terms before activation. This is a ceiling, not a cost estimate or billing guarantee. Hosting, storage and any later AI usage require separate accounting.

## 10. Data model and technology

Preserve the previously proposed Python/FastAPI and PostgreSQL direction. Use PostgreSQL full-text search and a GIN index initially, with ordinary indexed metadata filters. A durable PostgreSQL job table and bounded worker avoid requiring a separate queue service at pilot scale.

Proposed entities:
research_profiles; sources/source_policies; source_candidates; crawl_jobs; crawl_frontier; fetch_attempts; documents/document_versions; extracted_links; evidence_fragments; entity_mentions; company_candidates; event_candidates; source_lineage; search_runs; watch_rules; budget_reservations/usage; enrichment_handoffs.

Retain raw or extracted content only as permitted by source policy; use limited evidence excerpts and hashes where full retention is inappropriate. Make retention configurable and preserve provenance/tombstones when removing content. Store last checked, changed and next due timestamps independently.

The existing SQLite registry is a seed/migration artifact, not the new production search index. Import source IDs, associations, access history and search provenance without upgrading verification labels.

Existing code is reusable in parts but requires hardening:
- search_socials.py supplies bounded query-preview and request-accounting concepts, not an owned search engine.
- verify_sources.py supplies source checks and link discovery, not a complete crawler. It needs connection-time URL protections, robots handling across redirects, robust parsing and durable history before production reuse.

Minimal operator UI: research request, indexed results/evidence, crawl queue/coverage and budgets. A larger lead dashboard comes later.

## 11. Validation and build milestones

A. Contracts and corpus:
Freeze profile format, result schema, state transitions and enforced policies. Prepare saved HTML/feed/PDF fixtures and hand-labelled examples from the existing evidence. Keep the six seed firms as test cases and add unseen contractor names/documents to avoid hard-coding identities. No new manual lead list is the deliverable.

B. Owned crawler and storage:
Implement queue, policy gateway, fetcher, parsing, versioned evidence and recovery. Pass URL safety, redirect, robots, crawl-trap, byte-limit and concurrency-budget tests. No external search key or AI required.

C. Owned search:
Implement full-text index, structured filters, ranking explanations, unknown-date rules and coverage reporting. Demonstrate that a retrieved page is searchable with original provenance and that refresh updates its version without duplicate companies/events.

D. Discovery and handoff:
Add optional external-search adapter and source-candidate admission. Discover at least one previously unseeded company in a controlled evaluation, retain uncertainty and produce an enrichment handoff. An approved public crawl of a directory or news source can establish discovery without a paid provider. Test both provider-disabled and provider-enabled contracts.

E. Refresh and operator interface:
Implement watch rules, prioritization, staleness display and pause/resume. Do not activate unattended recurring work until the bounded tool is validated and operation is requested.

Release gates:
- Core crawl/index/search demonstrated without an AI model or external search provider.
- Every result has a source reference, access status and retrieval time; unknown dates are explicit.
- Existing false-match, historical-announcement and partner-account examples remain correctly rejected or flagged.
- At least 90% precision for candidate entity association on the agreed labelled evaluation set, with recall and top-result retrieval measured separately. This is a proposed acceptance target, not an achieved result.
- Unknown identity must remain unknown rather than be forced to meet a precision metric.
- Zero budget overruns in concurrency/retry/restart tests; all prohibited fetch fixtures blocked.
- Repeating a job is idempotent; interrupted jobs resume without duplicate evidence or lost usage.
- A controlled live test establishes real crawl/index behavior and reports blocked sources rather than substituting fabricated results.
- No automatic qualification, contact collection or outreach in this milestone.

Coverage on the accessible corpus can be measured; recall across the entire web cannot be promised. Establish latency and operating-cost targets from benchmark measurements rather than inventing guarantees.

## 12. Decisions and remaining uncertainties

Proposed decisions: own crawler/index; external discovery optional; no AI requirement for core operation; one configurable engine; PostgreSQL search first; contact enrichment separate; bounded public sources first.

Remaining items for implementation: exact shop capabilities; provider pricing/credentials if external discovery is enabled; deployment resources; source-by-source retrieval feasibility; whether scanned PDFs/JavaScript portals materially affect coverage. These do not block designing and testing the owned engine with fixtures and permitted public pages.

## 13. Primary technical references

Reviewed 12 October 2026. Architecture and numeric defaults above are proposals; references establish underlying mechanisms, not product performance.

- PostgreSQL full-text search, parsing, ranking and highlighting: https://www.postgresql.org/docs/current/textsearch.html
- PostgreSQL preferred full-text indexes (GIN): https://www.postgresql.org/docs/current/textsearch-indexes.html
- Robots Exclusion Protocol, RFC 9309: https://www.rfc-editor.org/rfc/rfc9309.html
- Existing repository baseline: docs/CLOUD_HANDOFF.md, docs/SOURCE_REGISTRY.md, docs/SOURCE_AND_SOCIAL_PLAN.md, tools/search_socials.py and tools/verify_sources.py at bddc6f59ebc0d71848989df79fadf02a33f0df05.

The Tavily documentation endpoint was not retrievable during this planning pass. No new Tavily pricing or live-transport behavior is claimed here.
