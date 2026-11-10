# Ranked contractor-lookup methods

Verified 17 October 2026. This document records which proposed sources are suitable for the automated
lookup, which are account-based manual fallbacks, and the order used by the application. A source can
identify a candidate contractor without proving a final award. `gpt-4o-mini` reads the returned
evidence and decides whether the role is `confirmed`, `pending_award`, `likely` or `unresolved`.

## Runtime order

The lookup stops as soon as the AI returns a valid `confirmed` result. Unresolved, likely and pending
results continue down the ladder so a later final decision can supersede an earlier recommendation.
Every paid search method is recorded in `contractor_method_attempts`, including its query, completion
state and reported provider credits. Completed stages are reused on retry.

### Public contract or award lead

| Rank | Method | What counts as strong evidence |
| ---: | --- | --- |
| 0 | Exact-page completed verification | A stored verification for the same normalized source URL |
| 1 | Existing lead and Apify evidence | Original source plus any pages already collected for the lead |
| 2 | Official final award | Award notice, approved/executed contract, notice to proceed, or official award database record |
| 3 | Bid tabulation and meeting decision | Final bid result, successful bidder, approved minutes or recorded vote; an agenda alone may remain pending |
| 4 | Issued permit | An issued permit tying a contractor to the named project or address |
| 5 | First-party or trade report | Owner, developer or reputable trade report that explicitly states the active contractor role |
| 6 | Broad web fallback | The earlier general-contractor web query, used only after stronger methods fail |

### Private project-start lead

| Rank | Method | What counts as strong evidence |
| ---: | --- | --- |
| 0 | Exact-page completed verification | A stored verification for the same normalized source URL |
| 1 | Existing lead and Apify evidence | Original source plus any pages already collected for the lead |
| 2 | Issued permit | Permit record tying the named contractor to the project or address |
| 3 | Owner/developer/architect announcement | A first-party page explicitly naming the contractor, construction manager or design-builder |
| 4 | Planning and agenda record | Site-plan or planning record that explicitly identifies the project role |
| 5 | Trade publication | Reputable construction or commercial-property coverage naming the contractor role |
| 6 | Broad web fallback | The earlier general-contractor web query |

The automated searches use Tavily Basic with documented `include_domains` preferences. They do not
depend on undocumented `site:` or `filetype:` query syntax. A fully unresolved lookup can spend up to
five Tavily Basic credits and make up to six small model evaluations; most should stop sooner. Existing
and duplicate evidence can stop the lookup without a Tavily request.

## Verified sources and disposition

| Source or method | Verification | Current use |
| --- | --- | --- |
| Original lead, related Apify pages, old general-contractor query | Existing system methods | Retained and ranked around the stronger sources |
| Official award notices, bid tabulations, council minutes | Public records can contain recommendations, votes and final awards | Automated targeted-search stages; AI must distinguish proposed from final |
| Granicus/Legistar InSite | Granicus documents a public legislative portal for researching legislation, calendars, agendas and minutes | Preferred official-record domain |
| PrimeGov public portals | Public portals expose text search, agendas and meeting material | Preferred official-record domain |
| Dallas OpenData building permits | The official dataset includes a Contractor field | Preferred permit domain |
| Dallas Accela/DallasNow | Public searches cover building, planning, contractor registration and public works records | Preferred permit domain |
| Texas ESBD and state contract records | Texas publishes solicitation and award/contract information through official systems | Preferred official-record search |
| SAM.gov | Public opportunity and award APIs exist, but require a SAM public API key | Searchable public pages included; direct API adapter deferred until a key is supplied |
| USAspending | Public API has award, recipient and subaward endpoints and currently requires no authorization | Preferred federal award domain; direct API adapter remains a separate enhancement |
| Developer/architect pages and reviewed trade media | Can explicitly identify the project team but may be secondary reporting | Automated after permits/official decisions |
| Shovels | Officially offers permit and contractor data products/API | Domain may appear in permit search; direct API requires a paid account/key and is not enabled |
| BuildZoom/Gryd | Official product provides permit and contractor history; data explorer is a subscriber product | Search evidence/manual fallback; no automated scraping |
| BuildingConnected | Autodesk describes an account/product workflow and quote-based pricing | Manual/account fallback only |
| PlanHub | Free and paid account tiers exist; broader project/lead access is paid | Manual/account fallback only |
| Local AGC or builders-exchange plan rooms | Availability and public access vary by chapter | Manual fallback after checking the specific portal |
| Texas affidavit of commencement/county records | Texas Property Code §53.124 says an owner and original contractor *may* jointly file it | Manual fallback only; it is optional and cannot provide systematic coverage |
| Mechanics liens | Can name a contractor after a payment dispute | Manual corroboration only, not proof of the original prime award by itself |
| Municode/eCode360 | Primarily code and ordinance libraries | Excluded from project-file lookup |

## Source verification links

- Tavily Search API and domain controls: https://docs.tavily.com/documentation/api-reference/endpoint/search
- Dallas OpenData Building Permits: https://www.dallasopendata.com/widgets/e7gq-4sah
- DallasNow public record search: https://aca-prod.accela.com/dallastx/default.aspx
- Dallas official open-data page: https://dallascityhall.com/departments/ciservices/pages/open-data.aspx
- Texas contract transparency and ESBD: https://comptroller.texas.gov/transparency/open-data/contracts.php
- Granicus InSite guide: https://support.granicus.com/articles/en_US/Knowledge/InSite-User-Guide
- SAM Opportunities API: https://open.gsa.gov/api/get-opportunities-public-api/
- SAM Contract Awards API: https://open.gsa.gov/api/contract-awards/
- USAspending API endpoints: https://api.usaspending.gov/docs/endpoints
- Texas Property Code Chapter 53: https://statutes.capitol.texas.gov/GetStatute.aspx?Code=PR&Value=53.124
- Autodesk BuildingConnected: https://construction.autodesk.com/products/buildingconnected/
- BuildZoom/Gryd data explorer: https://www.buildzoomdata.com/try-data-explorer
- Shovels API: https://www.shovels.ai/api

## Keys

The current ranked flow uses the existing Tavily and OpenAI session keys. Apify remains optional and
its already collected evidence is reused when present. No new key is required for this implementation.
A future direct SAM.gov adapter needs a SAM public API key; Shovels needs its own commercial API
credentials. USAspending states that its API endpoints currently require no authorization.
