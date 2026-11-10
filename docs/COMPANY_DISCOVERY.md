# Company discovery — corrected primary workflow

The user clarified that the engine must find companies matching signals, not ask them to choose
existing companies to crawl. The home page now implements that workflow. Known-company website
research is retained separately under Monitor sources.

## Use it

Start `python -m leadintel serve` and open `http://127.0.0.1:8765/` on this computer.

1. Under Search connection, enter your Tavily API key locally. It stays in server memory and is not
   written into the database, logs, source files or returned HTML. Alternatively set TAVILY_API_KEY
   in the server's process environment. A provided key is validated only by the first real search.
2. Open Classification review and enter an OpenAI API key locally when you are ready to classify.
   Searching does not require this key: results are saved and remain pending until classification.
   The key is held in memory, sent only to OpenAI and never written to the database or source files.
3. Select a construction trade and location. The recommended query set contains 15 ranked terms led
   by awards, project starts and expansions, plus two bulk-hiring searches. General searches exclude
   major job-board and social domains; selected trade-news searches restrict Tavily to reviewed source
   domains. The full experimental
   bank remains selectable. Add optional keywords and choose a provider time window. Click Update query list;
   this is a free preview. Existing selections are retained when their ID and query text still match;
   selections that no longer match are removed and explained in the interface.
4. Select 1–10 query checkboxes, or use Select first 10, then Find companies with selected queries.
   There are 20 targeted query options per trade and signal, or 80 across all four signals. General,
   roofing, electrical, mechanical/HVAC, plumbing, concrete, civil/excavation and drywall/framing
   trades are supported, alongside a broad construction category. DFW expands query geography
   across Dallas, Fort Worth, Arlington, Plano and Denton; a single city focuses all options there.
   The exact displayed queries are submitted in one batch, one provider request at a time. The
   engine does not load the registry's company list or restrict queries to those domains.
5. Review company candidates with evidence excerpts, source links, structured signal details and an
   explainable score. Only construction companies scoring at least 65/100 appear as leads.
   On Classification review, record whether a screen-printing salesperson would call each passing
   result, would not call, or is unsure, with an optional short reason. The page counts reviewed and
   call-worthy results so a 20–30 lead validation set can be completed before changing the threshold.
   Save a candidate for lead review. Saving does not trigger contact enrichment; qualification does.
   On Classification review, the lead heading itself is the original-source link and the website host
   appears directly beneath it. Hover over or focus that heading for a compact title-and-host preview.
   There is no duplicate Original source block. The surrounding card does not trigger the preview.
   Escape dismisses it. Use the browser's
   Copy link action when you need the full URL; it is not displayed in the preview.
   Expand Alternative links when a destination is inaccessible. Manually matched replacements are
   maintained in `data/reviewed_alternative_links.json` with review dates and matching evidence.
   Other results about the same company are labelled separately because they may concern different
   opportunities. A Google title-search fallback is explicitly unverified and opens only on click.
   Previews and alternative sections do not fetch remote pages or spend provider credits, and they
   do not guarantee a destination remains accessible or a vacancy remains open.

Search uses Tavily Basic, explicit parameter selection, ten results per request and no generated
answer. There is no browser login scraping or automatic fetching of returned links. Search results
can include indexed employer, news, government and social pages; this is not complete social-feed access.

The separate Monitor construction sources page uses the reviewed catalogue in
`data/monitor_sources.json`. It contains project trackers, government records and construction
publications rather than contractor company sites. Research and source limitations are documented in
`docs/MONITOR_SOURCE_RESEARCH.md`.

Search connection: [Tavily dashboard](https://app.tavily.com/).
API contract: [Tavily Search](https://docs.tavily.com/documentation/api-reference/endpoint/search).
Credit details: [Tavily credits](https://docs.tavily.com/documentation/api-credits).

## Evidence and limits

Company extraction uses the OpenAI Responses API with strict structured output and the fixed
`gpt-4o-mini` model. Results are sent in batches of up to ten. For every title and
snippet it returns a company name or null, construction-business status, signal type, explicit event
date, field roles, evidence strength, source reliability, summary and rejection reason. Search text is
treated as untrusted data. Names come from returned evidence, not predefined companies. Structured
output controls shape, not truth, so candidates still require original-source and identity review.

Scoring is plain code: contract/project/expansion strength, evidence strength, source reliability,
freshness and explicit field-workforce evidence contribute visible points. Eligibility also requires
a clearly named construction business. Single-person hiring has zero signal points and cannot reach
the 65-point threshold. The old regex output is retained only for side-by-side evaluation of historical
results; new searches do not use it to create company candidates.

After a result passes 65, the operator can manually run bounded Apify evidence enrichment. Project
mode retrieves the evidence page only. Company mode is available only when the classifier establishes
that the result came from the named company's own domain; it checks at most five careers, jobs,
projects or news pages. The API request sets `maxItems=5` and `maxTotalChargeUsd=0.25`, and a SQLite
trigger enforces the score gate. This does not collect contacts or run automatically.

Only passing **project-start** and **contract-award** leads have a **Find and verify general
contractor** action. Hiring, expansion and irrelevant results do not display the action or an old
contractor result. The action first evaluates the original lead and existing Apify evidence, then uses
the ranked source ladder in [CONTRACTOR_LOOKUP_METHODS.md](CONTRACTOR_LOOKUP_METHODS.md). Public award
leads check final award records and decisions before secondary reports; private project starts check
issued permits before first-party, planning and trade sources. The older broad Tavily lookup is the
last fallback. `gpt-4o-mini` evaluates after every stage and stops at the first confirmed result. A
fully unresolved lookup can use up to five Basic searches; completed stages are cached. The system
persists the contractor, developer,
project, address, status, explanation and cited source URLs.

The AI reads the evidence semantically and chooses one contractor status: `confirmed`,
`pending_award`, `likely` or `unresolved`. A pending vote, recommended award or planned decision is
not final merely because a contractor is named. A later official approval, executed contract, notice
to proceed, permit record or explicit active contractor role can support confirmation. The system does
not use a fixed phrase list to make this decision; application code validates the structured output,
status/confidence consistency and that every cited URL came from the supplied evidence. A developer
named in a groundbreaking headline is not automatically promoted to contractor. Unresolved and
pending results can be revisited after richer evidence is collected.

For `confirmed`, validation additionally requires a non-empty project name and at least one cited
evidence URL. Exact duplicate source URLs are grouped into one visible Classification review card.
If the same normalized source page already has a completed contractor verification, another result
reuses that structured verification and its evidence without issuing another Tavily search or OpenAI
request. This exact-source rule is deliberately conservative: similar company names alone do not
prove that two results concern the same project.

Generic publishers, obvious generic company categories, unrelated signal pages and unresolved names
are not silently converted into companies. They remain in Other web results. Negative hiring text is
filtered in the hiring mode, but subtle negation, subcontractor roles, historic references and copied
announcements still require review. The same normalized name is grouped within a run; this does not
prove that similarly named legal entities are the same business. Repeated URLs are deduplicated after
removing common tracking parameters. Repeated publishers are not scored as independent corroboration.

The provider's time filter and reported dates do not verify an event date. Location mentions and query
geography do not confirm the project/job location. Signal text does not establish apparel demand.
Results are saved as provider snippets; they are not described as directly fetched originals.

The shared local provider ledger reserves one credit before every Basic request. Limits are 30 credits
per UTC day and 900 per UTC month. Failed/uncertain requests count. Unexpected reported overage stops
the remainder of the run. Searches elsewhere in a provider account are not included in this ledger.
The picker displays the selected count and expected Basic credits. Batches exceeding the remaining
local budget are rejected before creating a run. The server rejects empty, duplicate, unknown and
over-ten selections independently of browser validation. Each run records all selected queries;
the activity panel distinguishes attempted queries from waiting or unrun ones.
The old standalone social-search script's execution mode is disabled to avoid a second active ledger.

Stop prevents subsequent provider calls, while an in-flight response is retained. Only one dashboard
run is active at a time. Duplicate form submissions reuse the run. Restarts mark unfinished runs
interrupted rather than silently charging for a replay. API errors are visible and never replaced
with fake companies or the existing contractor seed list.

## Validation status

87 tests passed. Tests use fictional, isolated provider, classifier and Apify responses to check new-company
discovery without seeds, duplicate handling, unresolved result separation, qualification gating,
stop behavior, request budgets, missing/invalid keys, secret redaction and the browser form flow.
The tests also cover 20 unique queries for every trade/signal, exact preview-to-execution matching,
ten-query batches, selection validation and whole-batch budget rejection. No fictional provider
responses were added to the user-facing database.

The suite also covers AI contractor-status output, required project evidence, project-only action
visibility, ranked source order, stop-on-confirmation, duplicate-source grouping and cost-free verification reuse, evidence URL validation and
the in-page asynchronous contractor result. The local run history records completed live Tavily requests. The revised query bank, classifier,
scoring and comparison UI were validated with mocked responses and browser controls without spending
search or model credits. As of 16 October 2026, all 325 stored results have completed classification;
23 score at least 65 and none remain pending or failed. The next evaluation step is to review the
passing set for sales usefulness and tune false positives from those decisions. Memory-only keys must
be entered again after a server restart; saved runs, classifications and evidence remain in the database.
