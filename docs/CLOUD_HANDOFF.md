# Lead gen project — conversation handoff

This is a summary of the local conversation and decisions, not a verbatim transcript. Prepared 12 October 2026 for continuation in the user's private techpulse0000-hub/lead-gen-project repository.

## User's intended product

Build lead intelligence for screen-printing shops. Start by testing construction companies and contractors. The same intelligence engine should later support other categories and signals through configuration, rather than separate engines.

The original brief was a local Word document named `leadgen system project planning.docx`. Its instructions were reference material; the user's chat instructions controlled the work. The original document is not included in this repository.

The user initially requested review, refinement, definitive answers to unresolved planning questions, and a plan before implementation. They subsequently authorized building the verified source registry and social-research foundation. They have now requested cloud continuation using this repository. Do not treat that as authorization for outreach, paid subscriptions or deployment.

## Working direction

- Pilot market: Dallas, Tarrant, Collin and Denton counties, Texas; a sample screen-printing/embroidery shop for testing.
- Construction signals: hiring, contract awards, project mobilization and expansion. A signal is evidence to investigate, not proof of an apparel purchase.
- One shared discovery, monitoring, investigation and deduplication pipeline; evidence and human review before qualifying opportunities.
- Planned application: Python/FastAPI, server-rendered templates with HTMX, PostgreSQL, a bounded worker and a dashboard first.
- Search direction: Tavily Basic; 30 requests/day and 900/month ceiling. Planned variable-spend caps: $1/day and $20/month, with an initial all-in estimate of $20–50/month, not a guaranteed invoice. Revalidate actual provider pricing before activation.
- Preserve source lineage; syndicated/cross-posted material is not independent corroboration. Do not infer new workers from job counts, contract values, or photos. Scores are not purchase probabilities.

## Completed and uploaded

Read README.md, docs/SOURCE_REGISTRY.md and docs/SOURCE_AND_SOCIAL_PLAN.md first. They describe the research and how to reproduce the SQLite database and JSON export.

The registry contains 19 source identities, seven social/job platforms, six real DFW contractor research prospects, 21 official-site-linked profile associations, one corroborated LinkedIn association and six unconfirmed Indeed employer-page candidates. The six companies are KPost, BakerTriangle, Polk Mechanical, Rogers-O'Brien, TDIndustries and Hill & Wilkinson. There was no pre-existing customer database in the local workspace.

Twenty-four initial public-index queries covered LinkedIn, Instagram, X and Indeed. LinkedIn and Indeed returned useful candidates. Instagram and X coverage was incomplete despite official account links. Facebook, YouTube and TikTok were inventoried where available but their feeds were not searched. Twelve source pages were directly retrieved; seven had access restrictions or timeouts and retain those statuses.

All 15 offline tests passed. The source verifier, registry builder and search runner use Python standard-library modules. The runner defaults to preview; execution requires TAVILY_API_KEY in the process environment. No API key was supplied or uploaded. Initial searches used the available web research tool, not Tavily. The live Tavily transport has not been tested. No recurring scheduler or full dashboard exists yet.

## Recommended next work

Run the offline tests and inspect the evidence. The next proposed milestone is a small end-to-end pilot on the six companies: investigate current events, verify company identity, dates, geography and execution stage, assess relevance to a screen-printing shop, and present an evidence-backed opportunity report. This pilot was recommended to the user; their immediate request is to move the context to the cloud. On arrival, acknowledge the handoff and wait for their next instruction before expanding implementation.

Retain evidence and uncertainties. An unrelated partner Facebook account and a bakery-job false match were rejected during research; keep those examples as acceptance cases. Source access and account association do not establish commercial qualification. No contractor outreach has been authorized.
