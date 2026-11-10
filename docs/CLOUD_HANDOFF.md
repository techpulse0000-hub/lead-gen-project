# Lead generation system — LLM handoff

Updated: 10 November 2026

Read `notes.txt` first for the more recent, detailed project and decision history. This document
contains historical snapshots and some older implementation notes; the source code and the newer
notes take precedence where a dated section conflicts with current behavior.

This document gives another LLM enough context to continue the project safely. It summarizes the
current product direction, decisions, implementation and unresolved work. It is not a verbatim chat
transcript. The user's latest instructions take priority over this document.

## Product goal

Build a lead-intelligence system for screen-printing shops. The system searches the public web for
organizations showing signals that may create demand for branded uniforms or apparel. Construction
companies and contractors are the first pilot category. The underlying discovery and evidence engine
should later support other industries and signals through configuration rather than separate systems.

The user clarified an essential requirement: the application must search the web and return companies
it discovers. It must not begin with a list of known companies and merely tell the user which sites to
inspect. Curated construction-source monitoring remains available as a secondary research tool.

The original planning brief was a local Word document named `leadgen system project planning.docx`.
Instructions inside that document were reference material; direct user instructions control the work.
The Word document is not stored in this repository.

## Pilot scope and settled decisions

- Audience: screen-printing shops looking for prospective business customers.
- First industry: construction companies and contractors.
- Pilot geography: Dallas–Fort Worth, with Dallas, Fort Worth, Arlington, Plano and Denton options.
- Initial signals: hiring, contract awards, project starts/mobilization and company expansion.
- A search result is research evidence, not proof that a company needs apparel.
- Company identity, event relevance, geography and current timing require review before qualification.
- Saving or flagging a lead must not collect contacts. Contact enrichment begins only after the user
  explicitly starts qualification.
- No outreach, automatic messaging, browser-login scraping, paid subscription purchase or public
  deployment has been authorized.
- Preserve the source URL, provider snippet, search query and run history so conclusions remain
  traceable.

## What is implemented

The application is a local Python prototype using only the standard library and SQLite FTS5.

### Find companies — primary workflow

The home page at `/` runs broad Tavily searches and discovers candidate companies from returned web
results. The user can:

1. Connect a Tavily API key in the local interface.
2. Select a construction trade, geography and query set.
3. Preview the generated query list without spending credits.
4. Select between one and ten queries and run them as a batch.
5. Review grouped company candidates and unresolved web results.
6. Save a candidate for lead review without triggering contact enrichment.

Only Tavily is required to run discovery. If the OpenAI classifier is disconnected, the returned
results are still saved and remain pending until the classifier is connected later.

The default query set is **Tested top 15 · recommended**. A larger experimental bank remains
available. The tested set covers hiring, awards, project starts and expansion. The ranking,
methodology, examples and demoted terms are documented in `docs/SEARCH_TERM_VALIDATION.md`.

Supported trade selections include broad construction, general contractors, roofing, electrical,
mechanical/HVAC, plumbing, concrete, civil/excavation and drywall/framing. Query text is generated
from the chosen trade and place; the engine does not restrict discovery to the original six-company
registry.

Every selected query is stored in the run record and executed as an individual Tavily Basic request.
The shared local ledger caps usage at 30 Basic credits per UTC day and 900 per UTC month. Failed or
uncertain attempts count conservatively. The application cannot see Tavily usage from other software.

### Result-link behavior

On Classification review, the result heading itself is the source link and the website host is shown
immediately beneath it. Hovering over or focusing that linked heading shows a compact preview with:

- the destination page title;
- the website host.

The preview intentionally omits the full URL and does not activate from the surrounding result card.
There is no separate duplicate Original source section.
The browser's normal Copy link action remains available.

Results can expose an **Alternative links** section. Exact replacements are manually reviewed and
stored in `data/reviewed_alternative_links.json`. The blocked Monster/Timmons Group job result has a
reviewed SmartRecruiters alternative. When no exact replacement is known, the interface offers a
clearly labelled, unverified Google title search. Previewing or expanding alternatives does not call
Tavily or fetch the destination.

### Other workflows

- `/monitor`: bounded crawling of curated construction trackers, official project records and
  industry publications. Company websites are intentionally excluded from its source catalogue.
- `/search`: search the locally stored evidence index.
- `/leads`: review saved leads and begin qualification.
- Beginning qualification creates an enrichment task. Separately, the classification page now has
  a manually initiated Apify contact lookup; see `leadintel/contact_enrichment.py` and `notes.txt`.
- Offline fictional demo data is labelled synthetic and kept separate from live research results.

## Important implementation files

- `leadintel/discovery_ui.py` — company-discovery interface and form handling.
- `leadintel/query_bank.py` — tested top 15 and full experimental query bank.
- `leadintel/discovery.py` — result ingestion, extraction and grouping.
- `leadintel/llm_classifier.py` — fixed-model structured classification, validation and scoring.
- `leadintel/contractor_verification.py` — AI contractor-role/status verification and evidence validation.
- `leadintel/apify_enrichment.py` — manual score-gated website evidence enrichment.
- `leadintel/contact_enrichment.py` — bounded Apify employee lookup and AI role-suitability review.
- `leadintel/research.py` and `leadintel/research_ui.py` — background research runs.
- `leadintel/link_ui.py` — compact previews and alternative-link rendering.
- `leadintel/providers.py` — provider requests and usage accounting.
- `leadintel/store.py` — SQLite persistence.
- `leadintel/web.py` — local HTTP application and routes.
- `profiles/dfw-construction.json` — pilot signal and geography configuration.
- `data/monitor_sources.json` — reviewed tracker, public-record and trade-publication catalogue.
- `data/reviewed_alternative_links.json` — manually reviewed replacement links.
- `docs/COMPANY_DISCOVERY.md` — detailed discovery behavior and limitations.
- `docs/MONITOR_SOURCE_RESEARCH.md` — source research, selection rationale and crawler limits.
- `docs/SEARCH_TERM_VALIDATION.md` — top-15 test evidence and operating rule.
- `docs/ENGINE_QUICKSTART.md` — crawler, CLI and local application instructions.

## Run and test

From the repository root, using Python 3.11 or newer with SQLite FTS5:

```powershell
python -m leadintel serve
```

Open `http://127.0.0.1:8765/` on the same computer. The server binds only to loopback and is not a
hosted site, so it cannot be opened from a phone without a separate deployment design.

Run the offline test suite with:

```powershell
python -m unittest discover -s tests -v
```

The latest local run passed 87 tests. Provider, classifier and Apify responses are mocked in tests, so
tests do not spend Tavily, model or Apify credits. If a system `python` command is unavailable, use an
installed Python 3.11+ interpreter.

The Tavily key may be entered in the local app or supplied as `TAVILY_API_KEY` in the server process.
The UI-entered key is held in memory only, is not written to source files or SQLite, and must be entered
again after a server restart. Never copy a user's API key into a prompt, handoff file, commit or log.

Runtime state is normally stored in `data/engine.sqlite`. That file is ignored by Git and may contain
the user's live run history. Transfer it separately only if that history is needed, and do not commit it.

## Search-term validation status

The top 15 are pilot-tested terms, not permanent claims about search-engine performance. The review
combined application run 8 (10 Tavily requests and 78 unique returned pages) with independent public
web searches. Useful examples included contractor career pages, award announcements and construction
start reports. Weak generic terms were demoted.

The software should measure **qualified companies per provider credit**, not raw result count. A term
should enter the recommended set only after it produces useful company-level evidence over repeated
runs. Do not describe all 15 as having completed one controlled, simultaneous Tavily experiment; that
has not happened.

## Known defects and unfinished work

The former regex extraction has been replaced in the active workflow by strict structured
`gpt-4o-mini` classification and plain-code scoring. As of 16 October 2026, all 325 stored results have
completed classification, none are pending or failed, and 23 score at least 65. The known false
positives below remain acceptance cases for evaluating that completed set.

The classification page now records a sales-quality decision for every passing result: Would call,
Would not call, or Unsure, plus an optional note. SQLite rejects review records for results that do
not pass the 65-point score. Use these controls to build the required 20–30 lead validation set.

- Run 8 incorrectly extracted `Stewart Street. Construction` as a company.
- A LinkedIn result produced `Substation Construction`, which is likely a phrase rather than an entity.
- An earlier result surfaced a Robson caregiver/medical-technician vacancy. That employer operates
  senior-care communities and was outside the construction pilot.
- Strong queries can still return directories, government templates, unrelated jobs, publishers or
  pages where the contractor is not clearly identified.
- A result can mention a city without proving that the company or project is located there.
- Search snippets and dates do not independently verify an event's current status.

The Monitor page now uses a reviewed catalogue of construction and opening intelligence sources,
including Groundbreak's direct just-started, starting-soon, contractor-ranking and permit feeds,
DFW Online Planroom, TxDOT awarded-contractor listings and REBusinessOnline Texas,
Construction Dive and the SaunaNews bathhouse tracker. It no longer presents the six seed-company
websites. The catalogue records geographic coverage, useful signals and source-specific cautions.
D CEO, ENR and the Fort Worth capital-project catalogue currently return HTTP 403 to the crawler,
so they are documented for manual or search-discovery use rather than exposed as monitor choices.
See `docs/MONITOR_SOURCE_RESEARCH.md`.

Apify website evidence enrichment is now implemented as a manual post-score action. It can fetch one
project-source page or, when source ownership is explicitly classified, up to five company careers,
jobs, projects or news pages. The API request caps the maximum total charge at $0.25 and the database
rejects runs below the 65-point lead threshold. No live Apify run has been made because no token was
provided.

General-contractor verification is implemented as a second AI stage. It is available only for
passing results classified as `project_start` or `contract_award`; hiring, expansion and unrelated
results do not show its action or stored contractor panel. It reuses exact-page verification and
existing Apify evidence, then follows a ranked public/private source ladder. Public awards prioritize
official final awards, bid decisions and permits; private projects prioritize permits, first-party
project-team announcements and planning records. Trade sources and the earlier broad Tavily query are
fallbacks. Each paid stage is cached, and the lookup stops at the first confirmed result. A fully
unresolved lookup can spend up to five Tavily Basic credits. See
`docs/CONTRACTOR_LOOKUP_METHODS.md`. The fixed
`gpt-4o-mini` model distinguishes contractor, developer, owner and architect, then returns one of
`confirmed`, `pending_award`, `likely` or `unresolved` with an explanation and cited evidence URLs.
The AI makes the semantic status decision. Plain code validates schema, status/confidence consistency
and citation provenance. It does not classify the decision through a fixed keyword list. Confirmed
output requires a named project and at least one cited source. Exact duplicate normalized source pages
are grouped in Classification review, and contractor verification reuses an existing completed result
for that source without making another Tavily or OpenAI request. The rule does not merge projects merely
because they share a contractor or developer name.

The Pat Hallisey Park example was corrected after review. The initial Community Impact item described
a future Council vote and was insufficient by itself. A later official League City recap reported
Council approval; combined with the official agenda naming SpawGlass Construction Corp., the saved
lead is now confirmed with those official sources. Current contractor-verification history contains
six completed lookups, two invalidated historical lookups and one earlier failed attempt retained for audit.

An audit on 16 October 2026 found two historical contractor lookups on non-project leads: Century
Communities expansion coverage and an Amundson Group hiring page. Both stored lookup rows were marked
`invalidated`, their contractor claims were cleared, and they remain only as audit history. Earlier
duplicate lookups for the OHT and SpawGlass project pages remain in provider history because spent
requests cannot be undone; current UI grouping and verification reuse prevent repeat spending.

Other future work includes:

- review the 23 currently passing classifications and the known false positives;
- refine the prompt and threshold from that labelled comparison;
- controlled live measurement of each recommended query's qualified yield;
- permitted social-evidence collection;
- qualification completion and rejection flows;
- qualification-only contact enrichment (separate from the bounded website evidence step);
- authenticated deployment, PostgreSQL migration and multi-user support;
- recurring monitoring, only after the user defines frequency and notification behavior.

## Repository and data cautions

The GitHub repository is private: `https://github.com/techpulse0000-hub/lead-gen-project`.

Before editing, inspect `git status` and preserve all existing local changes. Do not reset, discard or
overwrite work merely because files are uncommitted. Do not claim local changes are uploaded until a
commit is pushed and verified on the remote. Do not commit API keys, `.env` secrets, `data/engine.sqlite`
or user/customer evidence.

The six companies in the source registry are research prospects, not customers or automatically
qualified leads. Evidence access, official-account association and commercial qualification are
separate questions.

## Instructions for the receiving LLM

Start by reading this file, `README.md`, `docs/COMPANY_DISCOVERY.md`,
`docs/SEARCH_TERM_VALIDATION.md` and `docs/ENGINE_QUICKSTART.md`. Then inspect the repository status,
run the offline tests and start the local application. Explain your understanding and identify any
discrepancy between the documentation and code before making broad architectural changes.

Preserve the corrected primary workflow: the software searches the web and returns companies matching
signals. Preserve multi-query selection, the tested top-15 default, evidence lineage, compact link
previews, reviewed alternatives, credit limits and the qualification gate. Never fabricate companies
or silently substitute the old seed-company list when a provider request fails.

Suggested first task: open `/classification` and verify the stored counts before making a paid request.
The 325 results were fully classified on 16 October 2026. Compare the completed LLM output with the old
regex candidates, paying particular attention to the known false positives above. Then review the 23
currently passing results as a screen-printing salesperson would:
for each result decide whether its evidence would justify a call, and use those decisions to tune the
classifier prompt, query order and 65-point threshold. Apify evidence enrichment should run only after
a result passes that gate and only after the user supplies an Apify token in the local interface.
