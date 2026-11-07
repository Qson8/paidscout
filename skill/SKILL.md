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
(Qimai / Sensor Tower / data.ai) are panel-calibrated models — directional at
the top of the charts, demonstrably wrong in the long tail. Report the
verifiable signals: rank, rank movement, rating count and its daily delta,
price, version cadence, keyword positions.

## Setup (once)

1. Clone https://github.com/Qson8/paidscout (or locate an existing checkout).
2. The engine is `paidscout.py` — Python 3 standard library only, no API key.
3. Personalize `config.json` (copy `config.example.json`): storefronts,
   keywords, and the **watchlist** — candidate apps the user is tracking plus
   the user's own app(s), as `[app_id, country, label]` entries.
4. Agree with the user where the candidate pool lives (a Markdown file) and
   where daily reports go. Learn the user's stack and existing assets — axis 5
   scoring depends on them.

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

Big-company or licence-driven hits are **category-demand evidence only** —
never present them as directions to copy.

Pool rules: candidates scoring **≥6** enter the pool with date first seen,
score, and differentiation angle. Drop a candidate after it leaves the charts
or two consecutive reviews score it down. Highlight rating-delta outliers:
a big delta means real heat; a high rank with a near-zero delta is chart
noise, not demand.

## Report shape

- Header: date, storefronts covered.
- Chart table: app, developer, price, rating / rating count (with delta),
  rank change, offline verdict, store link. Primary storefront first.
- Changes vs yesterday: new / risen / fallen / dropped.
- At most 3 readings: price-band pattern, longevity vs new-entry signal, one
  concrete takeaway for the user's own apps.
- Direction section: candidates ranked by score, each with its
  differentiation angle and main risk; state which enter / stay / leave the
  pool.
