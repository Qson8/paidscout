# Changelog

## 0.1.0 — 2026-11-07

- First public release, extracted from a private daily research workflow.
- Dual-source chart crawling (Apple legacy RSS + MarketingTools RSS), US & CN,
  overall + 6 genre paid charts, top-grossing for coverage.
- SQLite history with per-run diff: rank movement, new entries, rating-count
  delta (download-velocity proxy), price and version fields.
- Keyword search-rank tracking and recent-review probes for a watchlist.
- Offline / big-company heuristics as a first-pass filter (manual review still
  required — the report marks them as heuristics, not facts).
- Sample report from the first production run (2026-11-07) in `examples/`.
