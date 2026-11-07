# Changelog

## 0.2.3 — 2026-11-07

Fixes from the second-round review (six reviewers; two findings reproduced
independently by two reviewers each):

- **GitHub Actions template repaired (was broken as shipped).** The commit
  step ran `git add data reports`, but the repo's own `.gitignore` excludes
  both directories, so the step failed outright; and the step was skipped
  entirely whenever the engine exited 1 (any failed review probe), throwing
  away a good day of data in Actions' ephemeral workspace. The template now
  uses `git add -f`, runs the commit step with `if: always()`, and documents
  the exit-code semantics (0 clean / 1 partial, data kept / 2 gate, nothing
  written / 3 crash). Its "private fork" advice was also wrong — forks of a
  public repo cannot be made private — and now describes the private-copy
  route correctly (READMEs updated to match).
- **Wording sweep completed in the two files round 1 missed:** the bundled
  Skill and the engine docstring no longer carry the pre-review phrasing
  ("demonstrably wrong", a defunct third platform's name); the Skill's
  honesty rule now matches the README's case-based wording, its report
  template says "vs previous run" instead of "vs yesterday", and a starter
  prompt plus the App Store URL → app-id recipe were added.
- Engine: 429 back-off is capped at 120s (a hostile `Retry-After` can no
  longer stall an unattended run for hours); crashes exit with code 3,
  distinct from partial-failure 1; Highlights CLIMB entries are sorted by
  ranks gained (they were first-come truncated); a true rating count of 0
  no longer renders as "?"; dead `grossing_ids` bookkeeping removed.
- READMEs: exit codes documented in Quickstart; the Actions workflow gets
  its own section; Configuration notes the app-id recipe and that config
  keys replace defaults wholesale; Features no longer lists grossing as a
  reported chart (it is stored, not reported); Roadmap reordered —
  multi-week validation first, the manual cross-check importer removed,
  the review probe marked maintenance-mode; a one-line note on the daily
  production run added before the license.
- Poster copy aligned with the same wording pass (capability phrasing
  instead of absolutes).

## 0.2.2 — 2026-11-07

Open-source polish (no engine behaviour change):

- Added `examples/github-actions-daily.yml`: a ready-to-copy workflow that
  runs the engine daily in a fork and commits the history back (with a
  private-fork recommendation, since the accumulated series is the asset).
- README badges (MIT / Python 3.9+ / zero dependencies) and a License-section
  note clarifying that the sample report's store data is factual data shown
  for illustration, with rights remaining with its owners.
- Repository About metadata set to the English description plus topics, and
  the raster poster added at `assets/poster.png` (initially as social
  preview; the README headers were then switched to the raster poster the
  same day — the SVG remains in `assets/` for other uses).

## 0.2.1 — 2026-11-07

Compliance pass (four-role review of the product and its promotion copy,
mean score 6.75/10; fixes target its findings):

- **Engine pacing**: keyword Search API calls are now spaced ≥3s apart
  (Apple's published guidance is ~20 calls/minute); HTTP 429 responses honour
  `Retry-After` with a longer backoff instead of the generic retry. The
  User-Agent is now a plain `PaidScout/<version> (+repo URL)` instead of a
  Mozilla-prefixed string.
- **Docs honesty pass**: competitor claims scoped to the single documented
  case (no whole-market generalisations from n=1), time-state wording rolled
  back to what is true on day one, the sample report replaced with a genuine
  v0.2 run (failed probes shown as failures, not zeros), rating-delta
  comparability qualified (same app across days; cross-app indicative only),
  Sensor Tower panel size attributed to its own materials, and assorted
  wording alignments across README (EN/ZH), METHODOLOGY and the launch post.

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

- First release, built for a daily research workflow.
- Dual-source chart crawling (Apple legacy RSS + MarketingTools RSS), US & CN,
  overall + 6 genre paid charts, top-grossing for coverage.
- SQLite history with per-run diff: rank movement, new entries, rating-count
  delta (download-velocity proxy), price and version fields.
- Keyword search-rank tracking and recent-review probes for a watchlist.
- Offline / big-company heuristics as a first-pass filter (manual review still
  required — the report marks them as heuristics, not facts).
- Sample report from the first production run (2026-11-07) in `examples/`.
