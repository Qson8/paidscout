#!/usr/bin/env python3
"""
PaidScout — App Store paid & offline app research engine for indie developers.

What it does (the chart-monitoring layer of what Qimai / Sensor Tower do,
using only Apple's official free feeds):
  - crawls App Store charts on a schedule (country x chart x genre), from TWO
    official Apple feeds that frequently disagree — and never merges their ranks
  - batch-looks-up metadata (price / rating / rating count / version / dates)
  - stores everything in SQLite, so every run diffs against history:
    rank movement, new entries, rating-count delta (= download-velocity proxy),
    price changes, version updates
  - tracks keyword search positions for a watchlist (ASO signal)
  - probes the recent-reviews feed of watchlist apps (review velocity)
  - applies offline / big-company heuristics as a first-pass filter

What it deliberately does NOT do: fabricate download or revenue estimates.
Those numbers at the big platforms are panel-calibrated models — directional
at the top of the charts, unreliable in the long tail. PaidScout reports the
verifiable signals themselves.

Stdlib only, no API key. Usage:
  python3 paidscout.py [--quick] [--date YYYY-MM-DD] [--config config.json]
Data lands in ./data/monitor.db, reports in ./reports/ (both relative to the
current working directory).
"""
import argparse, json, os, sqlite3, sys, time, traceback, urllib.parse, urllib.request
from datetime import date as date_cls

VERSION = "0.2.3"

DEFAULT_CONFIG = {
    "countries": ["us", "cn"],
    "genres": {"6014": "Games", "6002": "Utilities", "6007": "Productivity",
               "6017": "Education", "6027": "Graphics&Design", "6008": "Photo&Video"},
    "chart_limit": 50,
    "big_companies": ["mojang", "warner", "tencent", "netease", "microsoft",
                      "google", "apple", "meta", "bytedance", "alibaba", "baidu",
                      "electronic arts", "ubisoft", "gameloft", "king", "supercell",
                      "disney", "nickelodeon", "zhejiang royalflush", "travelsky",
                      "samsung", "amazon", "spotify", "x.d. network", "east2west",
                      "bandai namco", "rovio", "rockstar", "sega", "nintendo",
                      "capcom", "square enix", "konami", "505 games", "ustwo",
                      "ironhide", "ninja kiwi", "shanghai hode", "playdigious",
                      "devolver", "annapurna", "raw fury", "xinghan", "xd inc"],
    "offline_positive": ["offline", "no wifi", "no internet", "no wi-fi",
                         "single player", "single-player", "no ads", "no account",
                         "no sign-up", "no signup", "works without internet",
                         "airplane mode", "play anywhere", "pass and play",
                         "无需联网", "离线", "单机", "单人", "本地对战",
                         "无广告", "无需网络", "本地"],
    "offline_negative": ["online multiplayer", "multiplayer online",
                         "requires internet", "internet connection required",
                         "live streaming", "social network", "联网对战", "在线对战",
                         "直播", "服务器", "账号登录", "实时行情"],
    # watchlist entries: [app_id, country, label] — same app may appear per country
    "watchlist": [
        ["6803329435", "us", "Chromagraph Camera"],
        ["373493387", "us", "AnkiMobile Flashcards"],
        ["916366645", "us", "Procreate Pocket"],
        ["625334537", "us", "Geometry Dash"],
        ["479516143", "us", "Minecraft"],
        ["6741474933", "cn", "Berry胶片相机"],
        ["1439723850", "cn", "时间规划局"],
        ["1164801111", "cn", "AutoSleep"],
        ["1578203914", "cn", "电子宠物机"],
        ["6743614900", "cn", "像素蛋糕 PixCake"],
    ],
    "keywords": {
        "us": ["film camera", "meditation", "sleep tracker", "flashcards",
               "countdown timer", "photo editor", "white noise"],
        "cn": ["胶片相机", "冥想", "背单词", "倒计时", "睡眠监测", "白噪音"],
    },
}

FAILURES = []

def fetch_json(url, retries=3, timeout=25):
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "PaidScout/" + VERSION + " (+https://github.com/Qson8/paidscout)"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8", "replace"))
        except urllib.error.HTTPError as e:
            if attempt == retries - 1:
                FAILURES.append(f"{url[:110]} -> {e}")
                return None
            if e.code == 429:
                # Rate-limited: honour Retry-After, back off much longer.
                wait = e.headers.get("Retry-After") if e.headers else None
                wait_s = min(float(wait), 120) if wait and str(wait).isdigit() else 20 * (attempt + 1)
                time.sleep(wait_s)
            else:
                time.sleep(2 * (attempt + 1) + 1)
        except Exception as e:
            if attempt == retries - 1:
                FAILURES.append(f"{url[:110]} -> {e}")
                return None
            time.sleep(2 * (attempt + 1) + 1)
    return None

def db_connect(db_path):
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS chart_rank(
      run_date TEXT, source TEXT, country TEXT, chart TEXT, genre INTEGER,
      app_id TEXT, rank INTEGER, PRIMARY KEY(run_date,source,country,chart,genre,app_id));
    CREATE TABLE IF NOT EXISTS app_meta(
      run_date TEXT, country TEXT, app_id TEXT, name TEXT, seller TEXT,
      price REAL, currency TEXT, rating REAL, rating_count INTEGER,
      version TEXT, release_date TEXT, version_date TEXT, genre TEXT,
      offline_class TEXT, PRIMARY KEY(run_date,country,app_id));
    CREATE TABLE IF NOT EXISTS keyword_rank(
      run_date TEXT, country TEXT, keyword TEXT, app_id TEXT, rank INTEGER,
      PRIMARY KEY(run_date,country,keyword,app_id));
    CREATE TABLE IF NOT EXISTS review_probe(
      run_date TEXT, country TEXT, app_id TEXT, page1_reviews INTEGER, latest_review_date TEXT,
      PRIMARY KEY(run_date,country,app_id));
    """)
    return conn

def legacy_chart(cc, collection, limit, genre=None):
    g = f"/genre={genre}" if genre else ""
    url = f"https://itunes.apple.com/{cc}/rss/{collection}/limit={limit}{g}/json"
    data = fetch_json(url)
    out = []
    if data and data.get("feed", {}).get("entry"):
        for i, e in enumerate(data["feed"]["entry"], 1):
            try:
                out.append((e["id"]["attributes"]["im:id"], i,
                            float(e["im:price"]["attributes"]["amount"]),
                            e["im:name"]["label"],
                            e["category"]["attributes"]["label"],
                            e.get("summary", {}).get("label", "")))
            except Exception:
                continue
    return out

def marketing_chart(cc, chart, limit):
    url = f"https://rss.marketingtools.apple.com/api/v2/{cc}/apps/{chart}/{limit}/apps.json"
    data = fetch_json(url)
    out = []
    if data and data.get("feed", {}).get("results"):
        for i, r in enumerate(data["feed"]["results"], 1):
            out.append((str(r["id"]), i))
    return out

def lookup_batch(cc, ids):
    out = {}
    ids = list(ids)
    for k in range(0, len(ids), 80):
        chunk = ids[k:k + 80]
        url = "https://itunes.apple.com/lookup?id=" + ",".join(chunk) + f"&country={cc}"
        data = fetch_json(url)
        if data:
            for r in data.get("results", []):
                out[str(r["trackId"])] = r
        time.sleep(0.5)
    return out

def classify_offline(text, pos_words, neg_words):
    t = (text or "").lower()
    pos = sum(1 for w in pos_words if w in t)
    neg = sum(1 for w in neg_words if w in t)
    if neg >= 2 and pos == 0:
        return "online-leaning"
    if pos >= 2 and neg == 0:
        return "offline"
    if pos >= 1:
        return "offline-leaning"
    return "unknown"

def is_big(seller, big_list):
    s = (seller or "").lower()
    return any(b in s for b in big_list)

def fmt_delta(delta):
    """Format a rating-count delta. Negative deltas normally mean the count
    reset when a new version shipped — never render them as '+-123'."""
    if delta is None:
        return "—"
    if delta < 0:
        return f"{delta} (version reset?)"
    return f"+{delta}"

def previous_run_date(conn, today):
    row = conn.execute("SELECT MAX(run_date) FROM chart_rank WHERE run_date < ?", (today,)).fetchone()
    return row[0] if row else None

def main():
    ap = argparse.ArgumentParser(description="PaidScout — App Store paid/offline research engine")
    ap.add_argument("--quick", action="store_true", help="overall charts only; skip genres, keywords, reviews")
    ap.add_argument("--date", default=date_cls.today().isoformat())
    ap.add_argument("--config", default=None, help="path to config JSON (defaults: built-in)")
    ap.add_argument("--data-dir", default="data")
    ap.add_argument("--report-dir", default="reports")
    ap.add_argument("--version", action="version", version=f"PaidScout {VERSION}")
    args = ap.parse_args()

    cfg = dict(DEFAULT_CONFIG)
    if args.config:
        with open(args.config, encoding="utf-8") as f:
            cfg.update(json.load(f))
    countries = cfg["countries"]
    genres = {int(k): v for k, v in cfg["genres"].items()}
    limit = int(cfg["chart_limit"])
    watchlist = [tuple(w) for w in cfg["watchlist"]]
    keywords = cfg["keywords"]
    today = args.date

    conn = db_connect(os.path.join(args.data_dir, "monitor.db"))
    prev = previous_run_date(conn, today)
    all_ids = {cc: set() for cc in countries}
    legacy_paid, disagreements = {}, {}
    chart_rows = []

    # Phase 1: fetch everything into memory first. Nothing is written to the
    # database until the completeness gate below passes — a half-fetched day
    # must never become tomorrow's baseline.
    for cc in countries:
        lp = legacy_chart(cc, "toppaidapplications", limit)
        legacy_paid[cc] = lp
        for app_id, rank, *_rest in lp:
            chart_rows.append((today, "legacy", cc, "toppaid", 0, app_id, rank))
            all_ids[cc].add(app_id)
        for app_id, rank, *_rest in legacy_chart(cc, "topgrossingapplications", limit):
            chart_rows.append((today, "legacy", cc, "topgrossing", 0, app_id, rank))
        mp = dict(marketing_chart(cc, "top-paid", limit))
        for app_id, rank in mp.items():
            chart_rows.append((today, "marketing", cc, "toppaid", 0, app_id, rank))
            all_ids[cc].add(app_id)
        if lp and mp:
            legacy_ids = {a for a, *_ in lp}
            disagreements[cc] = (
                f"{cc}: marketing-only in top{limit}: {len(set(mp) - legacy_ids)} apps; "
                f"legacy-only: {len(legacy_ids - set(mp))} apps (two official feeds disagree — ranks never merged)")
        if not args.quick:
            for gid in genres:
                for app_id, rank, *_rest in legacy_chart(cc, "toppaidapplications", limit, gid):
                    chart_rows.append((today, "legacy", cc, "toppaid", gid, app_id, rank))
                    all_ids[cc].add(app_id)

    # Completeness gate: each storefront's primary paid chart must be
    # substantially complete, otherwise abort the whole run (exit 2) and
    # write nothing.
    gate_min = max(20, int(limit * 0.8))
    bad = [f"{cc}: legacy top-paid returned {len(legacy_paid[cc])} rows (< {gate_min})"
           for cc in countries if len(legacy_paid[cc]) < gate_min]
    if bad:
        print(json.dumps({"date": today, "error": "completeness gate failed", "detail": bad,
                          "failures": FAILURES}, ensure_ascii=False, indent=1))
        sys.exit(2)
    conn.executemany("INSERT OR REPLACE INTO chart_rank VALUES (?,?,?,?,?,?,?)", chart_rows)
    conn.commit()

    meta = {}
    for cc in countries:
        summaries = {a: s for a, r, p, n, g, s in legacy_paid[cc]}
        got = lookup_batch(cc, all_ids[cc])
        meta[cc] = got
        for app_id, r in got.items():
            off = classify_offline((r.get("description", "") or "") + " " + summaries.get(app_id, ""),
                                   cfg["offline_positive"], cfg["offline_negative"])
            conn.execute("INSERT OR REPLACE INTO app_meta VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                         (today, cc, app_id, r.get("trackName"), r.get("sellerName"),
                          r.get("price"), r.get("currency"), r.get("averageUserRating"),
                          r.get("userRatingCount"), r.get("version"), r.get("releaseDate"),
                          r.get("currentVersionReleaseDate"), r.get("primaryGenreName"), off))
        conn.commit()

    kw_hits = []
    if not args.quick:
        watch_pairs = {(a, c) for a, c, _l in watchlist}
        for cc, kws in keywords.items():
            if cc not in countries:
                continue
            for kw in kws:
                url = "https://itunes.apple.com/search?term=" + urllib.parse.quote(kw) + \
                      f"&country={cc}&entity=software&limit=50"
                data = fetch_json(url)
                if not data:
                    continue
                for i, r in enumerate(data.get("results", []), 1):
                    aid = str(r["trackId"])
                    if (aid, cc) in watch_pairs or i <= 3:
                        conn.execute("INSERT OR REPLACE INTO keyword_rank VALUES (?,?,?,?,?)",
                                     (today, cc, kw, aid, i))
                        if (aid, cc) in watch_pairs:
                            kw_hits.append(f"{cc} '{kw}': {r.get('trackName')} at #{i}")
                # Apple's published guidance for the Search API is ~20
                # calls/minute — stay safely under it.
                time.sleep(3.2)
        for app_id, cc, label in watchlist:
            url = f"https://itunes.apple.com/{cc}/rss/customerreviews/id={app_id}/sortBy=mostRecent/json"
            data = fetch_json(url, retries=3)
            # NULL means "probe failed / feed returned nothing" — it must stay
            # distinguishable from a true zero, or the time series is poisoned.
            n, latest = None, ""
            if data and data.get("feed", {}).get("entry"):
                entries = [e for e in data["feed"]["entry"] if "im:rating" in e]
                if entries:
                    n = len(entries)
                    dates = [e.get("updated", {}).get("label", "") for e in entries]
                    latest = max(dates) if dates else ""
            if n is None:
                FAILURES.append(f"review probe empty: {label} ({cc}) id={app_id}")
            conn.execute("INSERT OR REPLACE INTO review_probe VALUES (?,?,?,?,?)",
                         (today, cc, app_id, n, latest))
            time.sleep(0.4)
        conn.commit()

    def prev_meta(cc, app_id):
        if not prev:
            return None
        return conn.execute("SELECT rating_count, price, version FROM app_meta WHERE run_date=? AND country=? AND app_id=?",
                            (prev, cc, app_id)).fetchone()

    def prev_rank(cc, app_id):
        if not prev:
            return None
        row = conn.execute("SELECT rank FROM chart_rank WHERE run_date=? AND source='legacy' AND country=? AND chart='toppaid' AND genre=0 AND app_id=?",
                           (prev, cc, app_id)).fetchone()
        return row[0] if row else None

    from datetime import datetime as _dt
    interval_days = None
    if prev:
        interval_days = max(1, (_dt.fromisoformat(today) - _dt.fromisoformat(prev)).days)

    def per_day(delta):
        if delta is None or not interval_days:
            return "—"
        v = delta / interval_days
        s = f"{v:+.1f}/d"
        return s

    def is_noise(rcount, delta):
        # Small-base apps: tiny deltas are rating-prompt noise, not signal.
        return rcount is not None and delta is not None and rcount < 1000 and abs(delta) / (interval_days or 1) < 5

    def trend7(cc, app_id):
        rows = conn.execute(
            "SELECT run_date, rating_count FROM app_meta WHERE country=? AND app_id=? AND run_date<? "
            "AND rating_count IS NOT NULL ORDER BY run_date DESC LIMIT 8", (cc, app_id, today)).fetchall()
        if len(rows) < 2:
            return "—"
        (d_new, rc_new), (d_old, rc_old) = rows[0], rows[-1]
        span = (_dt.fromisoformat(d_new) - _dt.fromisoformat(d_old)).days
        if span < 2:
            return "—"
        return f"{(rc_new - rc_old) / span:+.1f}/d"

    os.makedirs(args.report_dir, exist_ok=True)
    lines = [f"# PaidScout Report — {today}",
             f"Previous run baseline: {prev or 'none (first run)'}"
             + (f" (interval: {interval_days} day(s); deltas also shown per-day)" if interval_days and interval_days > 1 else ""),
             "Sources: Apple legacy RSS charts + MarketingTools RSS + Lookup + Search + Reviews feeds (all official, free).",
             ""]
    for note in disagreements.values():
        lines.append(f"- CROSS-SOURCE: {note}")
    if FAILURES:
        lines.append(f"- FETCH FAILURES ({len(FAILURES)}): " + " | ".join(FAILURES[:6]))
    lines.append("")
    counts = {}
    highlights = {"new": [], "climb": [], "gain": []}
    for cc in countries:
        lines.append(f"## {cc.upper()} — Top Paid (legacy chart)")
        lines.append("| # | App | Seller | Price | Rating (count) | Δratings | Δ/day | 7d trend | Rank Δ | Price/Ver Δ | Offline | Indie? |")
        lines.append("|---|---|---|---|---|---|---|---|---|---|---|---|")
        counts[cc] = len(legacy_paid[cc])
        for app_id, rank, price, name, genre_name, summary in legacy_paid[cc][:limit]:
            m = meta[cc].get(app_id, {})
            off = classify_offline((m.get("description", "") or "") + " " + summary,
                                   cfg["offline_positive"], cfg["offline_negative"])
            seller = m.get("sellerName", "")
            rcount = m.get("userRatingCount")
            app_name = m.get("trackName", name)
            pm = prev_meta(cc, app_id)
            delta = (rcount - pm[0]) if pm and rcount is not None and pm[0] is not None else None
            dr = fmt_delta(delta)
            pd = per_day(delta)
            if is_noise(rcount, delta):
                pd += " (noise)"
            pr = prev_rank(cc, app_id)
            drank = f"{pr - rank:+d}" if pr else ("NEW" if prev else "—")
            pv = "—"
            if pm:
                bits = []
                if pm[1] is not None and m.get("price") is not None and pm[1] != m.get("price"):
                    bits.append(f"price {pm[1]}→{m.get('price')}")
                if pm[2] and m.get("version") and pm[2] != m.get("version"):
                    bits.append(f"v{pm[2]}→{m.get('version')}")
                pv = "; ".join(bits) if bits else "—"
            if prev:
                if not pr:
                    highlights["new"].append(f"{cc.upper()} #{rank} {app_name}")
                elif pr - rank >= 8:
                    highlights["climb"].append((pr - rank, f"{cc.upper()} {app_name}: #{pr}→#{rank}"))
                if delta is not None and delta > 0 and not is_noise(rcount, delta):
                    highlights["gain"].append((delta / (interval_days or 1), f"{cc.upper()} {app_name}: {fmt_delta(delta)} ratings ({pd})"))
            lines.append(f"| {rank} | {app_name} | {seller or '?'} | {m.get('price', price)} | "
                         f"{m.get('averageUserRating') or '?'} ({rcount if rcount is not None else '?'}) | {dr} | {pd} | {trend7(cc, app_id)} | {drank} | {pv} | {off} | "
                         f"{'big-co' if is_big(seller, cfg['big_companies']) else 'indie?'} |")
        lines.append("")
    if prev and (highlights["new"] or highlights["climb"] or highlights["gain"]):
        lines.append("## Highlights (auto-extracted)")
        for h in highlights["new"][:8]:
            lines.append(f"- NEW: {h}")
        for _v, h in sorted(highlights["climb"], reverse=True)[:5]:
            lines.append(f"- CLIMB: {h}")
        for _v, h in sorted(highlights["gain"], reverse=True)[:5]:
            lines.append(f"- RATING GAIN: {h}")
        lines.append("")
    if kw_hits:
        lines.append("## Watchlist keyword ranks (iTunes Search API, approximate)")
        lines += [f"- {h}" for h in kw_hits]
        lines.append("")
    lines.append("## Watchlist review probe (page-1 recent reviews)")
    for app_id, cc, label in watchlist:
        row = conn.execute("SELECT page1_reviews, latest_review_date FROM review_probe WHERE run_date=? AND country=? AND app_id=?",
                           (today, cc, app_id)).fetchone()
        if row:
            if row[0] is None:
                lines.append(f"- {label} ({cc}): probe failed (feed returned nothing — not a zero)")
            else:
                lines.append(f"- {label} ({cc}): {row[0]} reviews on page 1, latest {row[1] or 'n/a'}")
    lines.append("")
    lines.append("Notes: rating-count delta and rank movement are velocity proxies, not download/revenue numbers. "
                 "Negative delta usually means the rating count reset with a new version, not negative sales. "
                 "Deltas under ~5/day on apps with <1,000 ratings are marked (noise) — do not read into them. "
                 "Cross-app delta comparison is indicative only (rating-prompt intensity differs by category). "
                 "No panel data = no fabricated estimates.")
    report_path = os.path.join(args.report_dir, f"report-{today}.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(json.dumps({"date": today, "prev": prev, "counts": counts,
                      "failures": FAILURES, "report": report_path}, ensure_ascii=False, indent=1))
    if FAILURES:
        sys.exit(1)

if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        # Crash path gets its own exit code (3), distinct from 1 (partial
        # failures, report still written) and 2 (integrity gate).
        traceback.print_exc()
        sys.exit(3)
