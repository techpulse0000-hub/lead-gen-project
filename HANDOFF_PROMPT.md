# Prompt for the next LLM

Continue building this lead-generation system for screen-printing shops. Construction companies and
contractors are the first pilot market. Read `docs/CLOUD_HANDOFF.md` first, then read `README.md`,
`docs/COMPANY_DISCOVERY.md`, `docs/CONTRACTOR_LOOKUP_METHODS.md`, `docs/SEARCH_TERM_VALIDATION.md`, and
`docs/ENGINE_QUICKSTART.md` before changing code.

Treat the current files and `data/engine.sqlite` as authoritative. Preserve all existing work. Run the
full offline test suite and inspect the live application before making broad changes. Never copy API
keys into chat, files, logs, commits, or the database; the user can enter keys in the local interface.

The immediate job is to:

1. Start the app with `python -m leadintel serve` and open `http://127.0.0.1:8765/classification`.
2. Confirm the current database state before spending credits. As of 16 October 2026, all 325 stored
   results are classified, none are pending or failed, and 23 score at least 65. Classification uses
   the fixed `gpt-4o-mini` model and sends no new Tavily searches.
3. Compare the completed LLM classifications with the old regex output and check the known false positives in
   the handoff guide.
4. Review 20–30 passing results and judge whether each is strong enough for a screen printer to call.
5. Tune the prompt, query order, and explainable scoring threshold from that evidence.
6. Use Apify only for results that pass the score threshold and only after the user enters an Apify
   token locally.
7. Preserve the second AI stage for general-contractor verification. Show it only on passing
   `project_start` and `contract_award` leads. The fixed `gpt-4o-mini` model—not a hard-coded keyword
   list—must decide `confirmed`, `pending_award`, `likely` or `unresolved` from the supplied evidence.
   Code should validate the structured response and citation provenance. Confirmed output requires a
   named project and cited evidence. Preserve the ranked source ladder, stop-on-confirmation behavior,
   exact-source grouping and versioned completed-verification reuse so duplicate search results and
   retries do not repeat paid methods.

Do not return to seed-company monitoring as the primary workflow. The product must search the public
web and return newly discovered companies with strong signals, especially contract awards, project
starts, expansions, and genuine bulk hiring. A single vacancy is not a strong lead.

Before reporting completion, show the user the current classification counts, the comparison results,
the 20–30 lead judgments, any threshold changes, and the passing tests. The current suite contains
87 tests.
