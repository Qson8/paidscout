# Methodology — how the big platforms do it, and what PaidScout replicates

*Positioning note: all data comes from Apple's public feeds and remains the
property of its respective owners; app and seller names are used only to
identify the apps themselves. PaidScout outputs factual signals (ranks,
rating counts, prices, versions) for personal research.*

## How Qimai / Sensor Tower actually work

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
   Sensor Tower runs a large opt-in consumer panel (described in its own
   materials as 10M+) plus publisher first-party data to calibrate
   "rank → downloads" curves, then extrapolates. By most public accounts the
   results are decent near the top of the charts, noisy in the long tail, and
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
| Freemium earning coverage | ✔ (estimated amounts) | △ presence only — free apps on the grossing chart are listed with persistence (days on chart); amounts are never estimated |
| Review velocity | ✔ | △ page-1 probe for watchlist apps — Apple's reviews feed intermittently returns empty for some apps/storefronts; failures are stored as NULL (never as zero) and page-1 counts saturate at 50, so treat this as a weak signal |
| Download estimates | model + panel | ✘ — reports velocity proxies instead |
| Revenue estimates | model + panel | ✘ — long-tail revenue estimates can be far off (see field check) |

Field check (2026-11-07, China paid chart, free account): Qimai's top 25
matched PaidScout's legacy-feed chart **position for position**, and its
detail page showed a plausible download estimate for a ¥3 countdown app
(263 downloads yesterday on iPhone, plus 19 on iPad; ≈233/day over 30 days) —
while its revenue estimate for the same app showed **$0 across every
window**. The two figures cannot both be right; on this app, at that moment,
the revenue layer was not usable (a free-tier display scope or data lag
cannot be ruled out from outside). That is exactly why PaidScout treats
third-party estimates as a cross-reference, never as ground truth.

## Reading the signals

- **Rank high + rating count tiny** = a new entry riding external buzz or a
  chart artifact. Tomorrow's rating delta separates the two.
- **Rating delta** is a comparatively honest velocity proxy available
  without a panel: it undercounts (not everyone rates), and its *changes*
  are comparable across days **for the same app**; across apps and
  categories they are indicative only, because rating-prompt intensity
  differs.
- **Keyword position vs chart position** reveals the acquisition model:
  charting high while ranking #43 for your own core keyword means traffic
  comes from outside the store (press, creator IP, ads), not from search.
- **Two official feeds disagree** (on 2026-11-07 the US top-50s from Apple's
  legacy and marketing-tools feeds shared only ~18 apps). Never merge them;
  PaidScout keeps sources in separate rows and flags the disagreement.
- **Free-but-earning** (since 0.2.4): the paid charts are blind to the
  free-download + IAP/subscription/credits model. PaidScout therefore also
  lists free apps (price 0) that sit on the top-grossing chart. Presence
  there proves an app earns; it never proves how much. On 2026-11-08 all
  50 grossing spots in both the US and CN storefronts were free apps —
  upfront-paid has effectively exited the grossing top-50, so the useful
  reading is persistence and the non-big-company rows, not a single day.
- **Time windows**: Apple's free feeds are snapshots — no historical
  backfill exists anywhere in the free data. PaidScout's time dimension is
  a rolling window that starts when the engine starts (2026-11-07 for the
  author's instance) and fills in daily: trends pick the longest supported
  window (7/30/90 days) and always print the real span, and 'days on
  grossing' counts distinct days present within the last 90. A (12d)
  figure is a 12-day figure; nothing is extrapolated into a fake 90-day
  history.
