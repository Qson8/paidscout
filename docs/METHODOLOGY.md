# Methodology — how the big platforms do it, and what PaidScout replicates

## How Qimai / Sensor Tower / data.ai actually work

Every app-intelligence platform is built on the same public foundation. The
differences are in the estimation layer on top:

1. **Crawl the stores, completely.** Charts by country × chart type × genre,
   plus metadata (price, version, screenshots, description, IAP items),
   ratings and reviews — all public. Qimai states it covers 175 storefronts,
   13M+ apps and 20M+ keywords.
2. **Charts have hard limits; beyond them it's estimation.** Qimai itself
   discloses that Apple only provides the top 500 chart positions and that
   ranks 501–1500 on its site are model estimates. Its "downloads yesterday"
   and revenue figures are model outputs, not Apple data.
3. **Download/revenue estimation = rank curves × calibration panels.**
   Sensor Tower runs a 10M+ opt-in consumer panel plus publisher first-party
   data to calibrate "rank → downloads" curves, then extrapolates. Industry
   consensus: decent near the top of the charts, noisy in the long tail, and
   two platforms routinely print different numbers for the same app.
4. **Keyword intelligence** comes from repeatedly querying store search and
   recording positions/coverage (the ASO business).
5. **Ad intelligence** comes from crawling ad networks and Apple Ads auctions.

## What PaidScout replicates — and what it refuses to fake

| Layer | Big platforms | PaidScout |
|---|---|---|
| Chart/metadata crawling | ✔ | ✔ (two official feeds, cross-checked) |
| Rank history & diffs | ✔ | ✔ (SQLite, per-run) |
| Rating-count velocity | internal signal | ✔ reported as the raw delta |
| Keyword positions | ✔ | ✔ for a watchlist (Search API, approximate) |
| Review velocity | ✔ | ✔ page-1 probe for watchlist apps |
| Download estimates | model + panel | ✘ — reports velocity proxies instead |
| Revenue estimates | model + panel | ✘ — long-tail revenue models are demonstrably broken (see below) |

Field check (2026-11-07, China paid chart): Qimai's top 25 matched PaidScout's
legacy-feed chart **position for position**, and its detail page showed a
plausible download estimate for a ¥3 countdown app (263 downloads yesterday,
≈233/day over 30 days) — while its revenue estimate for the same app showed
**$0 across every window**, which is arithmetically impossible for a paid app
selling ~260 copies a day. That is exactly why PaidScout treats third-party
estimates as a cross-reference, never as ground truth.

## Reading the signals

- **Rank high + rating count tiny** = a new entry riding external buzz or a
  chart artifact. Tomorrow's rating delta separates the two.
- **Rating delta** is the honest velocity proxy available without a panel:
  it undercounts (not everyone rates), but its *changes* are comparable
  across days and apps.
- **Keyword position vs chart position** reveals the acquisition model:
  charting high while ranking #43 for your own core keyword means traffic
  comes from outside the store (press, creator IP, ads), not from search.
- **Two official feeds disagree** (on 2026-11-07 the US top-50s from Apple's
  legacy and marketing-tools feeds shared only ~18 apps). Never merge them;
  PaidScout keeps sources in separate rows and flags the disagreement.
