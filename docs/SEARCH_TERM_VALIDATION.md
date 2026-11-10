# Construction search-term validation — DFW pilot

Test date: 14 October 2026  
Scope: construction contractors and construction-related companies in Dallas–Fort Worth  
Objective: find identifiable companies with evidence of hiring, contract awards, project starts or expansion.

## What was tested

The review combined two evidence sets:

1. The application's completed run 8: 10 Tavily Basic requests and 78 unique result pages.
2. Independent public-web searches covering contract awards, employer careers, project starts,
   construction news sources and company expansion phrases.

Terms were judged on whether the returned result identified a company, contained an explicit signal,
matched construction activity, matched DFW, and avoided directories, generic advice, unrelated jobs
and documents that only described contract language. This is a pilot ranking rather than a permanent
SEO fact: indexes, dates, locations and providers change.

## Recommended top 15 — revised for commercial value

The software substitutes the selected construction trade and geography into these patterns.

| Rank | Signal | Search pattern | Why it survived |
|---:|---|---|---|
| 1 | Award | `{trade} "awarded contract" construction {place}` | Explicit new work and a named contractor. |
| 2 | Award | `"selected as general contractor" {specialty} {place}` | High precision for the contractor/project relationship. |
| 3 | Award | `{trade} "notice of award" construction {place}` | Useful public-award wording; templates still require filtering. |
| 4 | Award | `{trade} "contract award" project {place}` | Alternate wording used by company announcements and public records. |
| 5 | Award | `{trade} "secured" "construction contract" {place}` | Captures company language about newly won work. |
| 6 | Start | `{trade} "breaks ground" construction project {place}` | Evidence of an execution milestone. |
| 7 | Start | `{trade} "starts work" new facility {place}` | Stronger than generic mobilization language. |
| 8 | Start | `"construction underway" {trade} {place}` | Indicates active work; contractor identity still needs verification. |
| 9 | Start | `{trade} "notice to proceed" construction {place}` | Strong official start-stage language. |
| 10 | Start | `{trade} contractor project start {place}` | Restricted to Construction Dive and ENR by the API request. |
| 11 | Start | `{trade} "begins construction" contractor {place}` | Restricted to Community Impact and REBusinessOnline. |
| 12 | Expansion | `{trade} "expanding operations" new facility {place}` | Targets contractor capacity growth. |
| 13 | Expansion | `{trade} "opens new" branch headquarters {place}` | Looks for physical company expansion. |
| 14 | Hiring | `{trade} "hiring multiple positions" field crews {place}` | Requires explicit multi-role or crew-scale hiring. |
| 15 | Hiring | `{trade} "job fair" "field" hiring {place}` | A hiring event is stronger than a single vacancy. |

The revised ordering responds to pilot economics: contract wins, active project starts and operational
expansion are stronger apparel opportunities than one job opening. Recommended general searches send
Tavily an `exclude_domains` list covering Facebook, LinkedIn, Indeed, Instagram, ZipRecruiter,
HiringCafe, Glassdoor, Monster and CareerBuilder. The two source-focused searches use
`include_domains` restrictions instead. Hiring evidence can pass scoring only when it explicitly
supports multiple positions, crews or a hiring event; a single vacancy receives zero signal points.

## Observed examples

The hiring patterns surfaced contractor-controlled pages for Monarch Development, JMEG Electrical
Contractors, Power Design, Walker Engineering, MFB Roofing and Tempo Mechanical. Award phrasing
surfaced a Fort Worth airport award naming Archer Western and a municipal recommendation naming
Pogue Construction. Project-start phrasing surfaced Adolfson & Peterson, Hillwood, Moss Construction
and Cerris Builders. Expansion phrasing surfaced Westwood Contractors' headquarters move.

Useful reference results:

- https://monarchdevelopmentdfw.com/careers/
- https://www.jmeg.us/careers
- https://www.powerdesigninc.us/dallascareers
- https://www.a-p.com/news-and-insights/ap-breaks-ground-on-kdfw-fox-4-broadcast-studio-and-office-facility/
- https://communityimpact.com/allen/development/plano-apartments-allen-hospital-updates-check-out-5-of-the-latest-construction-projects-around-dfw
- https://rebusinessonline.com/category/texas/

## Terms demoted after testing

Run 8 showed why result volume alone is misleading:

| Search | Unique pages | Pages producing an extracted candidate | Decision |
|---|---:|---:|---|
| `construction project mobilization Arlington Texas` | 9 | 0 | Too much generic language. |
| `construction contractor opens new warehouse Denton Texas` | 9 | 0 | Often describes the client facility rather than a contractor. |
| `construction contractor awarded school project Plano Texas` | 9 | 0 | Too broad without an award phrase or source constraint. |
| `construction contractor hiring apprentices Denton Texas` | 10 | 0 | Job and training noise; use careers plus trade-specific roles. |
| `construction contractor recruiting field crews Plano Texas` | 8 | 2 | Some value, but it produced the blocked Monster/Timmons result and needs employer-page preference. |

The candidate extractor also produced false identities such as “Stewart Street. Construction” and
“Substation Construction.” That is a separate qualification defect: even a strong query does not make
every extracted name a valid company.

## Operating rule

Use the tested set first and select up to 10 terms per run. Compare unique qualified companies per
credit, not raw page count. Keep the full experimental bank available for exploration, but promote a
new term into the tested set only after it produces useful company-level evidence across multiple runs.
