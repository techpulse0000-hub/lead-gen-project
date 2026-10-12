# Specialized search engine tool — proposed build plan

Prepared and revised 12 October 2026. Revision adds parameterized web search and targeted Apify social collection. Planning only: this document specifies a future tool; it does not activate crawling, paid search, recurring monitoring, an AI agent or outreach.

## 1. Product intent and corrected scope

Build the software that discovers, retrieves, indexes and searches relevant public information. An AI agent may later direct the tool through a bounded interface, but the tool must also function through configuration, an API or a command line without an AI model.

The source registry and six contractor companies are seed data and test cases, not the intended product. Research candidates must remain distinct from verified business facts and qualified apparel opportunities.

First configuration: lead intelligence for a screen-printing/embroidery shop, construction contractors, Dallas/Tarrant/Collin/Denton counties. Initial signals: hiring, contract awards, mobilization and expansion. Later categories use configuration and source adapters within the same engine.

The separate company/contact enrichment scraper is a later module. This milestone may identify a company and candidate official website and emit a handoff; it does not promise decision-maker identification, email discovery or verified apparel demand.

## 2. Architectural decision

Build an owned, focused crawler and searchable index first. Do not make the engine merely a wrapper around a third-party search API.

Support four access modes:

- Local index search: search content previously retrieved by our crawler; requires no external search provider or AI.
- Targeted crawl and refresh: retrieve approved public source sections and follow relevant links within limits, building and refreshing the owned index.
- Parameterized web discovery: a first-class provider adapter finds URLs outside our existing coverage, using domain, date, topic, language and query controls where supported. These are provider evidence/candidates until investigated. The local crawler/index remains usable without credentials, but full discovery coverage requires an enabled search adapter.
- Targeted social collection: an Apify adapter retrieves bounded recent posts from selected company accounts after account association and Actor capability checks. Normalize those posts into the same evidence index. Provider availability and platform access limitations stay visible.

Web discovery addresses a real limitation: a crawler cannot discover the entire web from a few seeds. A bounded owned index will initially cover selected sources, not all websites or complete social feeds. Broader coverage comes from new seeds, reviewed outbound sources and optional external discovery.

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

The registry's social/job routes are historical observations. This revision proposes adding targeted Apify collection as a separate assessed route for supported public company accounts, alongside indexed search and official APIs. Store Actor identity, runtime, access basis and limitations; do not relabel an Apify Actor as an official platform API. Unsupported, private or inaccessible feeds remain coverage gaps.

## 7. Search interface and output contract

Proposed operations:

- search_index(request): search stored content without network requests.
- plan_research(request): preview sources, queries, maximum requests and budget reservations.
- submit_research(plan_id): enqueue the approved-scope plan and return a job ID.
- get_job(job_id): progress, results, failures, deferred work and usage.
- get_evidence(document_id): document provenance, permitted excerpt, retrieval status and dates.
- request_refresh(scope): bounded refresh using stored source policy.
- request_enrichment(candidate_id): emit a separate, deduplicated enrichment task.
- search_web(request): compile bounded provider-specific searches, return evidence candidates and usage.
- collect_company_posts(company_id, platforms, since, per_account_limit): enqueue only assessed company accounts through approved Actor adapters; return job IDs and coverage.

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

External search retains existing ceilings of 30 calls/UTC day and 900/UTC month across all search providers together. Advanced modes must reserve their higher credit costs; calls and credits are distinct. Apify runs have separate run/item caps and share the metered-spend ledger; internal Actor HTTP traffic is not observable and must not be claimed as covered by our direct HTTP-request counter. Preserve proposed variable spending ceilings of $1/day and $20/month across enabled metered research adapters. Request ceilings and money ceilings both apply; exhaustion of either defers work. Pricing must be configured from revalidated provider terms before activation. This is a ceiling, not a cost estimate or billing guarantee. Hosting, storage and any later AI usage require separate accounting.

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

D. Parameterized discovery, social collection and handoff:
Add the primary web-search adapter, provider capability matrix and source-candidate admission. Add bounded LinkedIn/Instagram Actor adapters and normalized social evidence; assess Facebook and X separately. Discover at least one previously unseeded company in a controlled evaluation, retain uncertainty and produce an enrichment handoff. An approved public crawl of a directory or news source can establish discovery without a paid provider. Test both provider-disabled and provider-enabled contracts.

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

Proposed decisions: combined parameterized web search, owned crawler/index and targeted Apify collection; Tavily first search adapter with selective advanced mode; Brave and Exa evaluated as alternatives/complementary adapters; no AI requirement for our core operation; one configurable engine; PostgreSQL search first; contact enrichment separate; bounded public sources first.

Remaining items for implementation: exact shop capabilities; provider pricing/credentials if external discovery is enabled; deployment resources; source-by-source retrieval feasibility; whether scanned PDFs/JavaScript portals materially affect coverage. These do not block designing and testing the owned engine with fixtures and permitted public pages.

## 13. Primary technical references

Reviewed 12 October 2026. Architecture and numeric defaults above are proposals; references establish underlying mechanisms, not product performance.

- PostgreSQL full-text search, parsing, ranking and highlighting: https://www.postgresql.org/docs/current/textsearch.html
- PostgreSQL preferred full-text indexes (GIN): https://www.postgresql.org/docs/current/textsearch-indexes.html
- Robots Exclusion Protocol, RFC 9309: https://www.rfc-editor.org/rfc/rfc9309.html
- Existing repository baseline: docs/CLOUD_HANDOFF.md, docs/SOURCE_REGISTRY.md, docs/SOURCE_AND_SOCIAL_PLAN.md, tools/search_socials.py and tools/verify_sources.py at bddc6f59ebc0d71848989df79fadf02a33f0df05.

The earlier Tavily documentation URL failed. The current endpoint/search and api-credits pages were retrieved successfully during this revision. Pricing below is a documentation observation, not a live account invoice or tested transport result.


## 14. Parameterized web search and Apify refinement

### 14.1 Revised search behavior

The research tool combines web-index discovery, direct website retrieval, targeted social-post collection and search over the accumulated evidence. HTTP is still the transport used by many APIs; the coverage difference comes from access to a provider's web index or specialized collector.

Do not promise that a provider is universally better than Google. The proposed advantage is repeatable specialist queries, complementary coverage, controlled follow-up, original evidence and deduplication. Compare results on the actual DFW task before making quality claims.

Our software compiles a query family rather than sending one overloaded query:
- Company discovery: contractor trade + one local geography + relevant business language.
- Signal discovery: one signal family (award, hiring, mobilization or expansion) + location + time window.
- Company follow-up: exact company/alias + signal + original-domain preference.
- Source follow-up: restrict to an official source or relevant news/project/careers section.
- Social discovery: find candidate company account/post URLs; confirm association before targeted collection.

Example request: construction contractors; Frisco/Collin County; awards and mobilization; recent publication window; exclude irrelevant names/categories; prefer government decisions and original company announcements. The compiler produces separate award, mobilization and identity queries. It verifies project geography and event timing locally; country localization cannot establish county coverage.

Default proposed limit: four web-search requests per research job, with at most two allocated to a secondary provider. Every generated query, retry and fallback consumes the shared daily/monthly ceiling. Stop after the job cap or when adequate evidence is available; never fan out across all providers by default.

### 14.2 Search-provider comparison and proposed selection

| Provider | Useful controls observed in primary documentation | Proposed role | Limitation |
|---|---|---|---|
| Tavily | Domain include/exclude, restrict/prefer mode, date/time controls, general/news topics, selective advanced search and relevant text chunks | Primary adapter, preserving existing code direction; basic discovery and advanced follow-up | Country is a ranking boost for general topic, not a local boundary; advanced costs more |
| Brave Search API | Site/file/title/body operators, Boolean/exact phrase controls, freshness/localization and Goggles ranking rules | Strong comparison candidate for explicitly personalized search ranking | Operators are documented as experimental; durable API-result storage requires a plan granting storage rights |
| Exa Search API | Domain/path filters, publication dates, company/news/people categories, highlights and multiple search modes | Selective comparison/fallback for differently phrased company and event discovery | Company/people categories reject date and exclude-domain filters; semantic modes may use provider models |

Sources: [Tavily API](https://docs.tavily.com/documentation/api-reference/endpoint/search), [Tavily search guidance](https://help.tavily.com/articles/7879881576-optimizing-your-query-parameters), [Brave operators](https://api-dashboard.search.brave.com/documentation/resources/search-operators), [Brave Goggles](https://api-dashboard.search.brave.com/documentation/resources/goggles), [Exa search](https://exa.ai/docs/reference/search).

Proposed first implementation: Tavily basic for discovery, advanced for evidence gaps. Set auto_parameters=false and include_answer=false; explicitly select depth, response size and usage reporting. This keeps our controller in charge of escalation. Advanced provider retrieval is not equivalent to our own autonomous agent.

Brave Goggles can boost selected official company/government and regional source domains and downrank low-value aggregators. Ranking rules only affect available indexed results; they cannot surface inaccessible or unindexed content. Evaluate Brave storage terms before persisting any response-derived fields; do not assume URLs/snippets are exempt.

For Exa company-category searches, omit unsupported filters; use news/general searches for dated announcements and verify dates locally. Do not silently discard a requested filter. Return applied_filters, unsupported_filters and local_postfilters. Avoid provider-generated answers, summaries and deep agent modes in the initial search contract.

Primary-source website evidence and provider-returned snippets/highlights have separate origins and retention policies. No adapter automatically grants rights to retain publisher content.

### 14.3 Targeted company social collection

Collect recent posts from specific company accounts, not entire platforms, follower networks or all employees. Initial LinkedIn/Instagram focus; Facebook next; X only after selecting an Actor compatible with low-volume monitoring.

| Platform | Candidate Actor | Capability observed | Planned status |
|---|---|---|---|
| Instagram | apify/instagram-scraper | Direct URLs, posts mode, per-URL result cap, newer-than filter | Initial targeted adapter |
| LinkedIn | harvestapi/linkedin-company-posts | Company URLs, per-account maxPosts, time filters; comments/reactions can be disabled | Initial targeted adapter; partner-maintained |
| Facebook | apify/facebook-posts-scraper | Page-post retrieval and time/count controls | Next adapter after input/price validation |
| X | Actor not selected | apidojo/tweet-scraper has minimum-volume and no-monitoring restrictions | Reject that Actor for this watch workflow; assess an alternative or official API |

Sources: [Instagram Actor](https://apify.com/apify/instagram-scraper), [Instagram input](https://apify.com/apify/instagram-scraper/input-schema), [LinkedIn Actor](https://apify.com/harvestapi/linkedin-company-posts), [LinkedIn input](https://apify.com/harvestapi/linkedin-company-posts/input-schema), [Facebook Actor](https://apify.com/apify/facebook-posts-scraper), [X Actor restrictions](https://apify.com/apidojo/tweet-scraper).

These are documented capabilities and author claims, not successful device/account tests. No-cookies claims do not prove permission or complete access. Check Actor access methods, platform restrictions, input schema, failure behavior and pricing before enabling each route. No private-account access or user credential/cookie collection is planned.

Proposed per-account collection: initial 30-day window, maximum 20 posts; subsequent runs from last successful watermark with a 48-hour overlap, retaining the 20-post cap. Begin with a weekly rotation of prioritized accounts and bounded investigation-triggered refreshes. If the cap is reached before the window is covered, mark truncated and queue a separately budgeted continuation where supported. No result does not mean no activity.

Instagram mapping: directUrls=[assessed account URL], resultsType=posts, resultsLimit=20, onlyPostsNewerThan=UTC cutoff. LinkedIn mapping: targetUrls=[assessed company URL], maxPosts=20, scrapeComments=false, scrapeReactions=false. Test date semantics and pinned/reposted content; descriptions and schemas can differ. The adapter must reject zero/unlimited limits. Advanced native social-search Actors can be assessed later, rather than promising arbitrary keyword search over every account.

Store platform/post ID, account ID and association status, original post URL, caption/text, reported publication time, retrieval time, Actor/run/build IDs and outgoing links. Preserve edits/version changes and distinguish repost lineage. Deduplicate repeated posts and website cross-posts. Apply the same company/geography/signal checks before treating content as useful evidence.

Comments, reactions, follower scraping, media downloads, Stories, private profiles and employee harvesting are excluded from the initial collection configuration. Keep media links only when appropriate; visual-only signals require a later separately assessed extraction step. Social job/event posts can be candidates; headcount or apparel quantity is never inferred from engagement/photos.

### 14.4 Apify integration contract and enforceable costs

Add a server-side Apify adapter, not unrestricted agent access to the Actor catalog.

1. Resolve stored company account; an unconfirmed account uses a bounded identity-assessment job, not automatic commercial association.
2. Select an allowlisted Actor/build with recorded input/output schemas, capabilities, access assessment and billing model.
3. Validate URLs and requested date/item limits. Do not allow arbitrary custom JavaScript, Actor IDs or additional resource settings from an agent.
4. Reserve maximum supported run charges from the shared ledger before starting.
5. Start asynchronously with an explicit timeout, item bounds and supported charge limit; save external run ID immediately.
6. Poll or process authenticated completion notifications; reconcile provider status before ingesting a bounded dataset.
7. Normalize records into evidence, record actual charges, release unused reservations and update coverage/watermark only to the extent justified by returned records.

On an ambiguous start timeout, mark start_unknown and reconcile rather than blindly restarting and paying twice. Abort requests and duplicate callbacks must be idempotent; abortion does not refund accrued charges.

Apify documents maximum charge controls for pay-per-event runs, but some Actors bill platform resources separately. maxTotalChargeUsd is not assumed to cap every ancillary charge for every billing model. Only enable unattended Actors whose total exposure can be bounded under the product budget; otherwise use a controlled evaluation before admission. Our own source rate limits cannot govern an Actor's internal network traffic; admission must assess that Actor's behavior.

References: [Actor billing models and run charge limits](https://docs.apify.com/actors/running/actors-in-store), [run options](https://docs.apify.com/api/client/js/reference/interface/ActorRunOptions), [run lifecycle](https://docs.apify.com/api/v2/actor-runs).

Data model additions: provider_capabilities, provider_retention_policies, actor_registry, external_runs, social_posts, account_watermarks and collection_coverage. Keep provider raw payloads only within applicable retention settings; parser/schema failures quarantine results rather than silently changing identity/verification.

### 14.5 Pricing observations and illustrative pilot budget

Prices reviewed 12 October 2026; eligibility and actual charges require account verification.

| Item | Public pricing observed |
|---|---|
| Tavily | 1,000 free credits/month; basic search 1 credit, advanced 2; PAYGO $0.008/credit |
| Brave Search | $5/1,000 requests and $5 monthly credits advertised; storage-rights plan eligibility requires separate confirmation |
| Exa Search | Instant $4/1,000, Fast/Auto $7/1,000 for up to 10 results; extra results/content options can add charges; $10 monthly starter credits advertised |
| Apify platform | Free plan includes $5 spend; Starter $19/month includes $19 spend plus PAYGO |
| Instagram Actor | Free-plan rate $2.70/1,000 results; lower “from” rates belong to discounted paid tiers |
| LinkedIn Actor | Free/Starter $2/1,000 posts; additional zero-result and start events are listed; platform usage included on its current pricing table |

Sources: [Tavily credits](https://docs.tavily.com/documentation/api-credits), [Brave pricing and storage FAQ](https://brave.com/search/api/), [Exa pricing](https://exa.ai/pricing), [Apify pricing](https://apify.com/pricing), [Instagram pricing description](https://apify.com/apify/instagram-scraper), [LinkedIn event pricing](https://apify.com/harvestapi/linkedin-company-posts/pricing).

Example before free-credit offsets:
- 720 Tavily basic + 180 advanced requests = 1,080 credits, $8.64 at PAYGO list price. This stays within 900 requests but exceeds 1,000 credits.
- Six companies × two platforms × 20 posts × four refresh cycles = at most 960 returned post items under those inputs: 480 Instagram items at $1.296 and 480 LinkedIn posts at $0.96, or $2.256 in post-result charges. Count Actor start/zero-result events, any additional costs, duplicates and retries separately.
- These components total about $10.90 before other charges and free-credit offsets. They exclude hosting/database/storage, AI, enrichment and optional secondary search.
- Re-fetching a duplicate can still be billed; database deduplication does not undo provider charges.

Proposed allocation of the existing $20/month metered ceiling: $10 search, $8 social collection, $2 reserve, with the existing $1/day ceiling. All providers and retries share that ceiling; it is not a separate $20 allowance for each provider. Prefer eligible free plans for the six-company validation; no paid subscription is needed merely to design the adapters. A future Apify Starter subscription creates a $19 fixed commitment and needs a revised all-in budget; do not add it silently to the variable cap.

### 14.6 Additional acceptance gates

Before selecting the final provider/Actor set:
- Run the same labelled query families against candidates under equal spending/request allowances; measure useful unique documents, false entity matches, freshness, retained provenance and latency.
- Compare focused searches with a small simple-query Google baseline using accessible results, without promising complete Google ground truth or starting bulk SERP scraping.
- Measure marginal value of a second provider rather than querying both every time.
- Test one assessed company account per initial platform with small item caps; verify actual owner, dates, post URLs, repeated-run overlap, truncated windows and charges.
- Demonstrate that a social post not returned by web-index search can enter the unified index through targeted collection, if the selected Actor actually retrieves one. Report failure honestly if it cannot.
- Test zero results, unavailable/deleted/private accounts, pinned posts, reposts, schema drift, timeouts, duplicate completion callbacks and ledger reconciliation.
- Preserve the original plan's identity, provenance, SSRF and budget tests; add unsupported-parameter and provider-storage-policy checks.

All provider quality, real social coverage and invoice behavior remain untested. This revision changes the design and scope; it does not run live collection or create accounts.
