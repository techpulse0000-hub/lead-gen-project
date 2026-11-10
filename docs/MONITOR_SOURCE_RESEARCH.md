# Construction-monitoring source research

Reviewed 15 October 2026 for the Dallas-Fort Worth construction pilot.

## Decision

The Monitor sources page must not default to contractor company websites. Its job is to watch
sources that repeatedly publish project registrations, permits, contract awards, groundbreakings,
construction progress and openings. The curated catalogue therefore combines official records,
regional project trackers, construction publications and a small number of sector-specific opening
trackers. The operator can select up to six sources for one bounded crawl.

Every selectable URL must open the actual list the operator wants to monitor. General homepages,
tool directories and pages that merely link to an interactive tracker are excluded. When one website
has several useful feeds, each feed is listed separately so the crawler begins with the intended data.

No source alone establishes a qualified lead. A permit can precede construction by months, an
apparent low bidder is not always the final award, and an opening announcement may omit the general
contractor. Every useful item must retain its original URL and be checked for company role, milestone,
date and geography.

## Recommended first DFW set

1. [Groundbreak DFW — just-started projects](https://pro.groundbreak.city/dfw/projects?stage=started)
   — the exact listing of projects whose construction began within the last 60 days.
2. [Groundbreak DFW — starting-soon projects](https://pro.groundbreak.city/dfw/projects?stage=starting)
   — the exact listing of projects expected to start within 90 days.
3. [Groundbreak DFW — most active general contractors](https://pro.groundbreak.city/dfw/stats/most-active-contractors)
   — the exact ranking of contractors named on the most permits during the last 90 days.
4. [DFW Online Planroom — Public Projects](https://www.dfwplanroom.com/projects/public) — actual
   construction listings with project names, locations, bid status, bid deadlines and associated
   companies. Company role and final award status still require verification.
5. [TxDOT facilities awards](https://www.txdot.gov/business/suppliers-vendors/facilities-projects-letting.html)
   — official building, renovation and repair listings with project descriptions, awarded contractors
   and bid amounts. Rows marked Awarded are especially useful for contractor leads.
6. [REBusinessOnline Texas](https://rebusinessonline.com/category/texas/) — high-volume Texas
   commercial development reporting that often states the project team, groundbreaking, completion
   target and property type.

For a permit-heavy run, substitute [Groundbreak's largest permits this month](https://pro.groundbreak.city/dfw/stats/largest-permits-this-month).
For more local reporting, use [DFW Daily Brief — Development & Openings](https://dfwdailybrief.com/topics/development/)
or [Bisnow DFW](https://www.bisnow.com/top-stories/dallas-ft-worth).

## Other useful trackers

| Source | Coverage and value | Important limit |
|---|---|---|
| [Zabalist construction bids](https://www.zabalist.com/bids) | Direct Texas construction bid and RFP listing | A bid opportunity does not identify the eventual winner |
| [Construction Dive](https://www.constructiondive.com/topic/commercial-building/) | National awards, starts and major contractor activity | Selective national coverage rather than a complete DFW list |
| [SaunaNews bathhouse briefing](https://www.saunanews.com/bathhouses/briefing) | U.S. and European bathhouse projects classified as announced, site preparation, under construction or opening soon | Narrow sector and low general-contractor volume |

The SaunaNews source stays in the catalogue because its evidence-led milestone model is a useful
example of how a niche tracker should behave. It is not expected to produce enough volume by itself.

## Useful manual sources excluded from automated monitoring

- [City of Fort Worth capital projects](https://www.fortworthtexas.gov/projects) is a strong official
  construction listing, but currently returns HTTP 403 to the monitor. Use it manually or through
  search discovery until a supported data connector is available.
- [D CEO commercial real estate](https://www.dmagazine.com/section/commercial-real-estate/) provides
  valuable DFW development reporting but currently returns HTTP 403 to the monitor.
- [ENR Texas & Southeast](https://www.enr.com/texas-southeast) covers regional project starts,
  awards and contractors, but currently returns HTTP 403 and some content requires a subscription.

## Sources intentionally excluded from the default list

- Individual contractor websites: useful only after a company is already identified, so they belong
  in lead enrichment rather than market monitoring.
- Generic job boards: dominated earlier results and rarely prove bulk field hiring or a project event.
- Texas TDLR Architectural Barriers registrations: useful for discovering a project, scope, owner,
  design firm and estimated dates, but the database exists for accessibility compliance and normally
  does not identify the awarded general contractor. It is therefore excluded from the main monitor
  catalogue and may be used only as supplemental evidence during project research.
- Paywalled lead databases such as Dodge or ConstructConnect: potentially valuable later, but they
  require a commercial agreement and a purpose-built integration rather than ordinary crawling.
- DFW Airport Project Tracker: the public page confirms the tracker exists, but the operational portal
  is account-oriented; the catalogue uses sources with more public evidence first.
- General press-release wires: useful as corroboration but too noisy for a six-source default run.

## Technical limits

The current monitor is a bounded same-origin HTML crawler. It does not submit search forms, execute
JavaScript applications, parse PDFs or bypass subscriptions. Interactive maps and search-only tools
need structured connectors before they can become monitor choices. A blocked source remains an
access gap; the software must never replace it with fabricated evidence.
