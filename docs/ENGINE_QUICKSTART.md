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
- Preview focused Tavily requests and bounded LinkedIn/Instagram Apify inputs without sending requests.

The example companies in the demo are fictional. Their records are marked synthetic and must not
be interpreted as prospects or qualified opportunities. The original six-company registry remains
separate research data; this engine does not automatically promote those firms to qualified leads.

## Requirements and offline demonstration

Run commands from the repository root. Python 3.11+ with SQLite FTS5 is required. No pip install,
external database, AI model or API key is needed for this first slice.

```bash
python -m leadintel --help
python -m leadintel demo
python -m leadintel search awarded --signal award --geography Collin
python -m leadintel coverage
python -m leadintel serve
```

Open `http://127.0.0.1:8765` on the same machine. Search → open evidence → flag a company →
open Lead review → Begin qualification. Flagging alone leaves the enrichment queue empty.
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
association and an admitted Actor. Live adapters, billing reservations and data ingestion remain unbuilt.

The older `tools/search_socials.py` uses a separate registry ledger and can execute with an API key.
It is not wired into this new runtime. Do not run it alongside future metered engine adapters and assume
the ledgers are shared. The new engine never reads or uses that key in this slice.

## Validation and practical limits

```bash
python tools/build_registry.py
python -m unittest discover -s tests -v
```

Tests cover offline crawl-to-search behavior, version changes, robots/redirect failures, private-IP and
mixed-DNS rejection, byte caps, concurrent budget accounting, single-worker leases, qualification
idempotency, database gating, configurable vocabularies, safe search input and dashboard form protection.

The controlled one-page KPost live attempt in the current cloud environment failed at DNS resolution
(`gaierror`). It sent no successful page request and indexed no live page. The job remained deferred
with its frontier intact. Live transport on an accessible network still needs validation.

Next implementation priorities: provider execution with one metered ledger, permitted social-evidence
ingestion, stronger parsing/query filters, PostgreSQL migration, authenticated deployment and the
qualification-only enrichment worker. No paid service, recurring monitoring or outreach was activated.
