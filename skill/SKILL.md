---
name: paidscout-research
description: Daily App Store paid & offline app research for indie developers. Run the PaidScout engine, interpret its chart/rating-velocity/keyword data, score project directions on 5 axes, and maintain a candidate pool. Use when the user wants App Store paid-chart research, indie app direction scouting, or a recurring paid/offline app report.
---

# PaidScout Research — agent workflow

You are running a daily research workflow for an indie developer: watch the
App Store **paid** charts, filter for **offline / single-device** apps, and
turn the movement into *project directions worth building*. The point is not
chart trivia; it is finding validated, replicable directions — overseas-first
by default (US storefront = primary signal), other storefronts as reference.

**Honesty rule (non-negotiable):** never state download or revenue numbers.
The free official feeds do not contain them, and third-party "estimates"
(Qimai / Sensor Tower) are panel-calibrated models — directional at the top
of the charts, unreliable in the long tail (in one check on 2026-11-07, a
major platform showed $0 revenue for an app with ~280 estimated downloads
that day). Report the verifiable signals: rank, rank movement, rating count
and its daily delta, price, version cadence, keyword positions.

## Setup (once)

1. Clone https://github.com/Qson8/paidscout (or locate an existing checkout).
2. The engine is `paidscout.py` — Python 3 standard library only, no API key.
3. Personalize `config.json` (copy `config.example.json`): storefronts,
   keywords, and the **watchlist** — candidate apps the user is tracking plus
   the user's own app(s), as `[app_id, country, label]` entries.
4. Agree with the user where the candidate pool lives (a Markdown file) and
   where daily reports go. Learn the user's stack and existing assets — axis 5
   scoring depends on them.

An app's id is the number in its App Store URL
(`apps.apple.com/app/id123456789` → `123456789`).

**Starter prompt** (the user can paste this to begin): "Run PaidScout for
today: execute the engine, then write my daily brief from its report —
highlights first, candidate directions scored on the 5 axes, pool changes
proposed. Never state download or revenue numbers."

## Daily run

1. Run the engine: `cd <checkout> && python3 paidscout.py`
   (~2 minutes; it retries flaky feeds itself. If the whole run fails, retry
   once; if it still fails, fall back to reading the feeds manually per
   "Data sources" below and say so in the report.)
2. Read `reports/report-YYYY-MM-DD.md`. It already contains: dual-source
   charts (legacy RSS is authoritative; the marketing-tools feed disagrees
   often and is **never** merged into legacy ranks), rating-count deltas vs
   the previous run, rank changes, watchlist keyword ranks, review probes.
3. Add the judgment layer (below) and deliver the report in the shape at the
   end of this file. Archive it where the user wants reports kept.

## Data sources (all keyless, official — for manual fallback)

1. **Charts (primary)**: legacy iTunes RSS —
   `https://itunes.apple.com/{cc}/rss/toppaidapplications/limit={N}/json`,
   add `/genre={id}` before `/json` for genre charts (Games 6014, Utilities
   6002, Productivity 6007, Education 6017, Graphics & Design 6027,
   Photo & Video 6008).
2. **Metadata (batch)**: iTunes Lookup —
   `https://itunes.apple.com/lookup?id={ids}&country={cc}`.
3. **New-app discovery (secondary only)**: Marketing Tools RSS —
   `https://rss.marketingtools.apple.com/api/v2/{cc}/apps/top-paid/{N}/apps.json`.
   Its ordering differs from the legacy chart and omits long-running leaders;
   use it only to spot new releases, then verify rank in the legacy feed.

## Offline / single-device filter (manual review of engine output)

The engine's offline/indie labels are keyword heuristics — always review:

- **Include**: offline tools (drawing, flashcards, local editors, cameras),
  single-player games, local party games.
- **Label hybrid**: core single-player offline but optional multiplayer /
  sharing / sync (e.g. Minecraft, Geometry Dash).
- **Exclude**: proxies/VPN, SaaS clients, social/streaming/content-feed apps,
  anything whose core needs an account or a server — even at the top of the
  paid chart (e.g. Shadowrocket-type utilities).
- Judge from store copy; when ambiguous, mark "to verify" instead of guessing.

## Direction scoring (5 axes, 0–2 each, 10 total)

Score shortlisted apps as *direction candidates*, never as clone targets:

1. **Indie replicability** — individual/small-team shippable; no licence,
   content library, server fleet or network effect required.
2. **Offline purity** — core works offline, near-zero running cost.
3. **Overseas fit** — universal need, little language/local-service
   dependence, matches US/EU willingness to pay.
4. **Paid validation strength** — price × rating volume; for new apps, a high
   rank with a low rating count is an early signal — flag it as unproven and
   let the next days' rating delta confirm or kill it.
5. **Fit with the user's stack & assets** — buildable by this user with their
   tools; leverage from products/content they already have.


**Reserved cross-signal — web-wide heat (placeholder only, not scored).** A future signal slot is reserved for whether the same direction is simultaneously heating up in general web hot-search trends (source would be the hot-keywords board at blog.hanfucn.com/hot-keywords). User decision (2026-11-07): the two pipelines are deliberately NOT merged — different data domains, different purposes — but a direction rising on the paid chart *and* in web-wide attention is a doubly-validated signal. Until activation this slot is unscored: it does not affect the 5-axis total or the ≥6 pool threshold. Revisit only after ≥2 weeks of daily engine data; if activated, score it 0–2 as a separate line shown next to — never inside — the 5-axis total, and record the activation in this file and the changelog.

Big-company or licence-driven hits are **category-demand evidence only** —
never present them as directions to copy.

Pool rules: candidates scoring **≥6** enter the pool with date first seen,
score, and differentiation angle. Drop a candidate after it leaves the charts
or two consecutive reviews score it down. Highlight rating-delta outliers:
a big delta means real heat; a high rank with a near-zero delta is chart
noise, not demand.

Reading the deltas (engine ≥0.2.0 already annotates these — respect them):
a **negative** delta usually means the rating count reset with a new app
version, not negative sales; deltas are normalised **per day** when runs are
more than a day apart, and a windowed trend column (7/30/90 days, always
labelled with its real span) smooths Apple's batched rating updates;
deltas under ~5/day on apps with fewer than 1,000 ratings are
marked **(noise)** — never build an argument on them. Deltas are comparable
across days for the *same* app; across apps and categories they are only
indicative, because rating-prompt intensity differs.

## Report shape

- Header: date, storefronts covered.
- Chart table: app, developer, price, rating / rating count (with delta),
  rank change, offline verdict, store link. Primary storefront first.
- Free-but-earning section (engine ≥0.2.4): free apps on the grossing
  chart, with days-on-chart persistence. Read it as category-demand
  evidence for the free + IAP/subscription/credits model — never as
  paid-download candidates, never scored on the 5 axes, and never a source
  of revenue figures. Non-big-company rows that persist for weeks may join
  the watchlist for a closer look.
- Changes vs previous run (name its date and the interval): new / risen / fallen / dropped.
- At most 3 readings: price-band pattern, longevity vs new-entry signal, one
  concrete takeaway for the user's own apps.
- Direction section: candidates ranked by score, each with its
  differentiation angle and main risk; state which enter / stay / leave the
  pool.

## PainScout (demand-side weekly, painscout.py)

PaidScout reads charts (*what sells*); PainScout reads 1–3 star App Store
reviews (*what users curse*) and turns recurring complaints into demand cards
that enter the same candidate pool.

- **When to run:** weekly (Mondays). `python3 painscout.py` with the seed (or
  your own) `painscout.config.json`. It writes a weekly report, appends to the
  cumulative card pool (`reports/painscout-cards.md`), and saves a JSON
  snapshot under `data/`.
- **Automated sources — only these two:** App Store review RSS (US/CN
  storefronts) and the official HN Algolia API. Reddit, Google Play and
  anything needing a login are **never** automated: reading them is T3 manual
  work, never fed into the engine, never sent to an LLM in bulk. V2EX has no
  login-free keyword search endpoint and is likewise T3 manual.
- **Reading the scores:** cold-start 6-point scale — frequency / intensity
  (workaround & paid-language inside the cluster) / unmet (cross-app spread +
  unresolved markers), each 0–2; **≥4 generates a card**. Evidence strength
  (concrete vs. noise) is printed on the card but not scored; asset fit is a
  human checkbox, not a score. Persistence and cross-source resonance stay
  **off** until 4 weekly snapshots exist. The engine systematically scores
  lower than a human deep-read — treat it as a weekly monitor and tripwire,
  not a replacement for interviews or paid tests.
- **Noise rule:** pure price rage and pure feature wishes are downweighted as
  noise; workaround language ("I use a spreadsheet instead") and paid language
  count at full weight — willingness-to-pay evidence outranks anger volume.
- **Honesty rules:** an empty review feed is a fetch failure (NULL ≠ zero
  reviews) and is reported as such, never as "no complaints". Quotes on cards
  are de-identified (authors are never parsed; links/emails scrubbed) and the
  public edition strips quotes entirely. Never describe the pipeline as
  "fully automated multi-source" — the automated sources are exactly the two
  above.
