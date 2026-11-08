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

## Pain mining (PainScout, v0.3.0): how demand cards are produced

The charts above are supply-side evidence. PainScout adds the demand side:
what users of existing apps repeatedly curse, counted from their own words.

- **Corpus.** 1–3 star reviews from the App Store review RSS (US/CN
  storefronts) for a seed set of apps, plus HN Algolia hits as corroboration
  only. Author fields are never parsed. Reddit, Google Play and any
  login-walled source are never automated — manual reading only.
- **Taxonomy v1 (bilingual keyword grammar).** Eight pain classes: opaque
  subscription/billing, data & trust failures, rigid plan/data editing,
  content gaps, AI aversion, credit walls & expiring balances, unexplained
  generation/review failures, forced onboarding flows. Substring matching is a
  counting instrument, not comprehension — cards must be re-read by a human
  (the Skill layer) before any decision.
- **Signal weighting.** Workaround language ("I went back to a spreadsheet")
  and paid language ("I paid for points that expired") count at full weight —
  they evidence willingness to pay. Pure price rage and pure feature wishes
  are logged as noise and excluded from counts.
- **Cold-start score (6 points).** Frequency (cluster size) 0–2, intensity
  (workaround + paid language inside the cluster) 0–2, unmet need (cross-app
  spread + unresolved markers) 0–2. **≥4 → demand card.** Persistence and
  cross-source resonance are not scored until four weekly snapshots exist.
  Evidence strength (concrete vs. noise share) is printed on the card, not
  scored; asset fit is a human checkbox — the engine never decides strategy.
- **Known limits.** Apple's review RSS intermittently returns empty shells
  for some apps/storefronts; an empty feed is logged as a fetch failure,
  never as zero complaints (a whole category can be unmeasurable in a given
  week — that is reported, not smoothed over). The "most recent" window is a
  snapshot, not the review corpus; low-star reviewers are a self-selected
  sample. A demand card is an interview and paid-test entry point, never a
  build decision by itself.
