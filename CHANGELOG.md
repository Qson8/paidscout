# Changelog

## 0.2.0 — 2026-11-07

Post-review hardening (six-role review scored v0.1.0 at 5.4/10; fixes target
its P0 findings):

- **Completeness gate**: all charts are fetched into memory first; if any
  storefront's primary paid chart returns <80% of the expected rows, the run
  aborts with exit code 2 and writes nothing — a half-fetched day can no
  longer become tomorrow's baseline.
- **Failure visibility**: non-core fetch failures now exit with code 1 after
  writing the report (previously the exit code was always 0).
- **Review probe honesty**: a failed/empty probe is stored as NULL and
  rendered as "probe failed", never as a fake zero.
- **Delta discipline**: negative rating deltas are annotated
  "(version reset?)" instead of rendering as "+-123"; deltas are also shown
  per-day across multi-day intervals, with a 7-day trend column and a noise
  floor (deltas <5/day on apps with <1,000 ratings are marked as noise).
- **Report completeness**: price and version changes vs the previous run are
  now actually reported (they were claimed but missing); an auto-extracted
  Highlights section (new entries, big climbers, top rating gains) added.
  (A paid∩grossing overlap line was tried and dropped: the legacy grossing
  top-50 is entirely free/subscription apps in both storefronts, so the
  overlap is structurally ~0 and the metric misleads. Grossing rows remain
  in the database.)
- **Classifier tuning**: offline detection now reads description + chart
  summary combined and recognises more phrasings; the big-company list grew
  (X.D. Network, East2west, Bandai Namco, Rovio, Rockstar, ustwo, Ironhide,
  Ninja Kiwi, and other publishers previously mislabelled as indie).

## 0.1.0 — 2026-11-07

- First release, extracted from a private daily research workflow.
- Dual-source chart crawling (Apple legacy RSS + MarketingTools RSS), US & CN,
  overall + 6 genre paid charts, top-grossing for coverage.
- SQLite history with per-run diff: rank movement, new entries, rating-count
  delta (download-velocity proxy), price and version fields.
- Keyword search-rank tracking and recent-review probes for a watchlist.
- Offline / big-company heuristics as a first-pass filter (manual review still
  required — the report marks them as heuristics, not facts).
- Sample report from the first production run (2026-11-07) in `examples/`.
