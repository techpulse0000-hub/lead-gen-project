# Research engine — first working slice

Built 13 October 2026. This is runnable software, with an offline demonstration and tests;
it is not a deployed or production-ready application.

## What works now

- Explicitly admit a public website section and crawl relevant same-origin HTML links.
- Check robots rules, reject private addresses, pin validated connection addresses and validate redirects.
- Bound requests, bytes, depth and frontier size. Record failed attempts and retain pending work.
- Store evidence, content versions, reported publication dates and original URLs.
- Search owned evidence using SQLite FTS5, with signal and geography-mention filters.
- Configure signal vocabulary and geography using `profiles/dfw-construction.json`.
- Review evidence, flag a company and explicitly begin qualification in the local dashboard.
- Create exactly one enrichment task when qualification begins; enforce the gate in the database too.
- Discover raw company-signal evidence through broad Tavily searches and classify it with strict
  structured `gpt-4o-mini` output (each service requires its own key); preview bounded social inputs.
  Discovery can run before the classifier is connected; those results remain saved and pending.
- For passing project-start and contract-award leads, run AI contractor verification from the original
  evidence, any available Apify evidence and a ranked public/private source ladder. The AI evaluates
  each stage, stops at the first confirmed result, and returns confirmed,
  pending-award, likely or unresolved status with cited sources.

The example companies in the demo are fictional. Their records are marked synthetic and must not
be interpreted as prospects or qualified opportunities. The original six-company registry remains
separate research data; this engine does not automatically promote those firms to qualified leads.

## Requirements and offline demonstration

Run commands from the repository root. Python 3.11+ with SQLite FTS5 is required. No pip install,
external database or AI model is needed. The offline demo and crawler need no key;
company discovery requires a Tavily key. Structured classification requires an OpenAI key, but it can
be connected later without repeating the Tavily searches.

```bash
python -m leadintel --help
python -m leadintel demo
python -m leadintel search awarded --signal award --geography Collin
python -m leadintel coverage
python -m leadintel serve
```

Open `http://127.0.0.1:8765` on the same machine. The home page is **Find companies**: select the
construction trade, location and query set, connect Tavily, choose 1–10 queries and search. Companies come from search-result
evidence, not a supplied company list. See [company discovery](COMPANY_DISCOVERY.md) for setup,
evidence handling and operating limits. On Classification review, each linked lead heading opens the
original page, shows its host beneath the title and exposes a compact preview on hover or keyboard focus.

On a passing project-start or contract-award card, **Find and verify general contractor** starts a
background lookup and reports progress in the card without blocking scrolling. Hiring and other
non-project results do not show this action. `gpt-4o-mini` distinguishes the developer, owner,
architect and contractor and decides whether the evidence establishes a final contractor, a pending
award, a likely contractor or no resolvable contractor. Application code validates the structured
answer and cited URLs; it does not assign the status from a keyword list.
A confirmed response must contain a named project and cited evidence. Exact duplicate source pages
are grouped on the review page, and a completed verification for that source is reused without another
provider or model request.
If existing evidence is insufficient, the lookup follows the ranked public/private source ladder in
[CONTRACTOR_LOOKUP_METHODS.md](CONTRACTOR_LOOKUP_METHODS.md) and stops on the first confirmed result.
A lookup that reaches every fallback can use five Tavily Basic credits; confirmed results normally
stop earlier.

**Monitor construction sources** (`/monitor`) is the separate workflow for project trackers,
official records and construction publications:

1. Choose a buying signal and county, with optional literal keywords (every keyword must match).
2. Select up to six curated intelligence sources, or enter another public tracker/publication URL.
3. Set a total page allowance (1–20, at least one per selected website) and link depth (0–3).
4. Click **Start research**. A background worker fetches the selected sites and indexes fresh evidence.
5. Follow the automatically refreshing run page for matching evidence, all collected pages,
   per-website status, request activity and failures. **Stop research** prevents the next request;
   a request already in flight must finish or time out. Collected evidence is retained.

Only one dashboard research run is active at a time. Runs are persisted, repeated form submissions
do not duplicate them, and an interrupted server marks unfinished runs for review on restart.
Page allowance is shared across selected websites. Existing HTTP/day/origin/job limits still apply.
Keywords, signal and county filter the pages retrieved during the run; they are not interpreted by
an AI agent. Company websites are excluded from the default monitor list. This mode crawls explicitly
selected sources, not an external search engine's entire index. See
[monitor-source research](MONITOR_SOURCE_RESEARCH.md) for selection evidence and crawler limits.
Broad web discovery is available through Find companies once Tavily is connected. Native social
collection is still not connected.

Use **Search evidence** (`/search`) for the existing local index and fictional demo records.
Research-run results exclude demo records and evidence not visited by that run. Run results currently
show each collected document's latest stored version; they are not immutable historical snapshots.
Open evidence → flag a company → Lead review → Begin qualification.
Flagging alone leaves the enrichment queue empty.
Beginning qualification queues a task, but no contact scraping runs because that worker is not built.

The dashboard is a single-operator, loopback-only standard-library HTTP server. It has form-CSRF
and Host checks and escapes stored evidence. Do not expose it through a public tunnel or bind it
to the internet; production authentication, deployment and tenancy are later milestones.

All runtime state defaults to `data/engine.sqlite`, excluded from Git. Use `--db` before the command
for another database. Do not commit customer evidence or secrets.

## A real public website crawl

The following sends ordinary HTTP requests; it does not use a paid provider:

```bash
python -m leadintel add-source --name "KPost public website" --url https://kpostcompany.com/
python -m leadintel crawl --source 1 --max-pages 1 --max-depth 0
python -m leadintel coverage
```

Use the actual source ID returned by add-source; it may not be 1. Choose a narrower admitted section
where possible, for example an explicitly reviewed news landing page. Sources are manually admitted
in this slice; discovered external domains are not automatically fetched.

`--prefix /news/` restricts the admitted path when adding a source within that section. Redirects
outside the origin or path boundary are blocked. Social/job-board domains are not sent to the direct
crawler; those need their separately assessed provider routes.

Resume pending work with `python -m leadintel crawl --job JOB_ID`. Completed jobs are idempotent.
Failed URLs remain marked failed rather than being retried automatically. A new crawl job refreshes
previous evidence; pending jobs can be deferred by request/page/time limits. A crash leaves a
five-minute lease before another worker can resume. This prototype runs only one crawler job at a time.

Current bounds: at most 20 processed page URLs per execution, depth 3, frontier 100 URLs,
200 reserved HTTP requests/UTC day, 30/origin/day and 50/lifetime job. Robots and redirects also consume
requests; failures are conservatively counted. Pending frontier cannot bypass a lifetime job cap.
The crawler spaces host requests by at least two seconds, honors supported robots crawl delays and
defers long delays. HTTP 429 and other errors remain visible; no automatic retries are enabled.

Only uncompressed HTML is currently processed; RSS/sitemaps/PDF/JavaScript support comes later.
Publication dates come only from supported metadata. Event dates remain unknown. Geography tags
are text mentions, not confirmed job/project locations; Frisco is retained under both Collin and Denton.
Search uses literal token matching, not the full future Boolean/date/ranking contract yet.

## Qualification gate from the command line

Use IDs returned by search and flag; do not assume fixed IDs:

```bash
python -m leadintel flag --document DOCUMENT_ID --company "Company name" --reason "Evidence to investigate"
python -m leadintel enrichment-queue
python -m leadintel qualify LEAD_ID
python -m leadintel enrichment-queue
```

State: evidence → flagged candidate → qualification_in_progress + pending enrichment task.
Qualification completion, rejection UI and the actual company/contact scraper are future work.
Repeated qualification requests do not duplicate tasks. A task is actionable only while its lead
is in qualification; flagging does not gather people, emails or business phone numbers.

Company social-post collection is research evidence, distinct from contact enrichment. Its preview
can be prepared during research, while decision-maker/contact collection remains qualification-only.

## Search and social previews

```bash
python -m leadintel plan-search --company "KPost Company" --location Dallas --signal hiring --advanced
python -m leadintel plan-social --platform linkedin --account https://www.linkedin.com/company/polk-mechanical/ --since 2026-10-01T00:00:00Z --max-posts 20
```

These commands send zero requests. They expose proposed parameters, limits and required checks.
They do not confirm account ownership. Instagram/LinkedIn collection requires an assessed company-account
association and an admitted Actor. Live social adapters and their billing remain unbuilt. The dashboard's
new Tavily discovery flow has its own live transport, shared local provider credit ledger and result ingestion.

The older `tools/search_socials.py` is now preview-only; its execution path is disabled to avoid an
independent spending ledger. The new discovery engine uses a session-only key supplied in the app or
TAVILY_API_KEY from the process environment. It does not load `.env` automatically.

## Validation and practical limits

```bash
python tools/build_registry.py
python -m unittest discover -s tests -v
```

Tests cover offline crawl-to-search behavior, version changes, robots/redirect failures, private-IP and
mixed-DNS rejection, byte caps, concurrent budget accounting, single-worker leases, qualification
idempotency, database gating, configurable vocabularies, safe search input and dashboard form protection.

The original one-page KPost attempt in the cloud environment failed at DNS resolution (`gaierror`).
On 13 October 2026, the local browser's **Start research** flow was tested successfully against KPost:
three real pages were fetched and indexed, with remaining links explicitly deferred by the page cap.
An initial sandbox-blocked attempt remains in run history; the local dashboard was then restarted
with approved network access. Tests cover asynchronous starts, cancellation, duplicate submission
handling, run-specific result isolation and shared page limits.

The discovery picker offers a tested top-15 set plus the larger experimental bank, with 1–10 selected
queries per batch. All 87 tests pass. Completed live Tavily calls are recorded locally;
the new multi-query flow was tested using mocked provider responses without paid requests.

As of 16 October 2026, all 325 stored results are classified, none are pending or failed, and 23 pass
the 65-point threshold. Next implementation priorities: review and label those passing leads, inspect
the known false positives, then tune the prompt and score threshold. After that: permitted social-evidence ingestion, stronger
source verification, PostgreSQL migration, authenticated deployment and the qualification-only
enrichment worker. Recurring monitoring and outreach remain inactive.
