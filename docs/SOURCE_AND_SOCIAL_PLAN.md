# Source and social research addition to the pilot plan

The intelligence engine will use a maintained source registry and enrich each stored prospect with official social accounts and employer pages. Construction contractors in the four DFW pilot counties remain the first category. This addition expands where the engine looks, while retaining the evidence and cost requirements of the approved direction.

## What is established now

The initial source catalog, company-profile associations, public-index search records and access checks are saved in SQLite and JSON. The readable registry links to the original evidence. The six company seeds were found during this research; there was no pre-existing client database in the workspace. These seeds favour visible regional firms and are not a representative sample of all contractor sizes.

The listed source organization can be verified even when automated access is blocked. A company can publish an official social link even when its feed is unavailable to the research tools. These are separate fields. A profile verified here means an evidence-backed association, not a platform verification badge or a guarantee that it remains active forever.

## Source priority

1. Official employer careers/ATS pages for active vacancies; official company news and project pages for operational developments.
2. Government award decisions and project records for named contractors, scope, dates and execution status.
3. Verified company social posts for announcements that have not yet reached a newsroom or trade publication.
4. Trade/regional reporting and economic-development announcements for discovery and corroboration.
5. Job aggregators for discovery, followed by employer-side verification.

Sources are authoritative only for the claims they can support. A council agenda is not proof of a final award; a press-release distributor is not independent corroboration of its client's release. Social posts, website announcements and syndicated copies of one release share a source lineage.

## Prospect enrichment

When a company enters the main database, visit its verified website selectively and extract company-specific social, newsroom and careers links. Save the original URL, canonical platform identity, verification source, check time, access method and review status. Ignore sharing widgets, employee profiles, partner accounts and individual videos when identifying corporate accounts.

If no direct link exists, search the company name, official domain and location on the platform's public web index. Matching names alone are insufficient. A profile that matches the official domain and business/geography can be corroborated; unresolved matches remain candidates. Indeed pages may be unclaimed and must not be labelled company-controlled without evidence. Missing results are recorded as unknown rather than no account.

Use the same company ID for website evidence, social profiles, events and signals. Keep aliases, regional/divisional accounts and parent-company relationships explicit. The registry's JSON export can seed PostgreSQL without changing the selected production architecture.

## Searching the requested surfaces

- **LinkedIn:** search indexed company, post and job pages. Use original company posts when accessible. General page-management API access is an approved, authenticated product and is not assumed to provide unrestricted prospect-feed access. [Official documentation](https://learn.microsoft.com/en-us/linkedin/marketing/community-management/community-management-overview).
- **Instagram:** keep verified company accounts and search indexed public posts. Coverage was incomplete in this pass. Native API eligibility, permissions and pricing must be verified against the account before activation; the Meta documentation endpoint was not retrievable during this review. [Official API documentation](https://developers.facebook.com/docs/instagram-platform/).
- **X:** normalize Twitter/X account identities, retain the original official link and use indexed posts initially. An official search adapter can be activated with developer credentials and a separate spending cap. No free unlimited feed access is assumed. [Search API](https://docs.x.com/x-api/posts/search/introduction), [pricing](https://docs.x.com/x-api/getting-started/pricing).
- **Indeed:** search indexed employer and job pages, then confirm relevant jobs on the official employer careers/ATS site. No direct bulk scraper is included. [Indeed terms](https://www.indeed.com/legal).
- **Facebook, YouTube and TikTok:** retain company-linked profiles as additional surfaces. They are secondary to the four requested platforms in the pilot. Their feeds have not been comprehensively searched.

Search snippets are discovery evidence, not verified event facts. Date, geography, company role, source authenticity and purchasing relevance still require investigation. A photo of workers wearing branded shirts does not prove a new apparel order or a worker count. Reposts do not establish new events.

## Scheduling and cost

Keep the existing ceiling of 30 search calls per day and 900 per month. Reserve four daily slots for social/job research, within that total: ten broad discovery, eight company monitoring, eight investigation follow-ups, and four social/job searches. These are scheduler allocations; unused slots can be reassigned without exceeding the shared cap.

Prioritize high-potential companies and rotate platforms. At six seed companies, four daily queries can cover the four requested platforms in roughly six days. At 100 companies, the same budget cannot promise weekly checks of every account. Display last search, next due time, deferred jobs and coverage gaps rather than implying continuous complete monitoring.

Recheck source identity and access monthly, and company-account association every 90 days or immediately after a broken link, redirect or identity conflict. Preserve previous evidence and downgrade a stale association for review; do not erase its history. Respect permissions and source-specific retention requirements when integrating native APIs.

The source-verification helper is on demand. The search runner is on demand. No recurring jobs, external accounts, paid subscriptions or contractor outreach have been activated.

## Changes to the first implementation milestone

Add Sources and Company Profiles views to the planned dashboard. Each source shows authority, supported signal types, geography, access route, last verification and limitations. Each company shows verified accounts, candidates, missing-platform checks, careers links and search coverage.

The shared worker will read these records when selecting evidence sources. Alerts must show the original post/job/document link, distinguish reported facts from inference, and combine cross-posted evidence into one event. A social post can strengthen an opportunity; merely finding a social account cannot.

Acceptance requires that an existing company can be enriched, unrelated accounts are rejected, missing coverage is visible, repeated profile URLs deduplicate, job searches do not imply hiring quantities, and search budgets include retries. Validate the construction use case before expanding categories.
