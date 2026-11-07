#!/usr/bin/env python3
"""
PaidScout — App Store paid & offline app research engine for indie developers.

What it does (the replicable core of what Qimai / Sensor Tower / data.ai do):
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
import argparse, json, os, sqlite3, sys, time, urllib.parse, urllib.request
from datetime import date as date_cls

VERSION = "0.1.0"

DEFAULT_CONFIG = {
    "countries": ["us", "cn"],
    "genres": {"6014": "Games", "6002": "Utilities", "6007": "Productivity",
               "6017": "Education", "6027": "Graphics&Design", "6008": "Photo&Video"},
    "chart_limit": 50,
    "big_companies": ["mojang", "warner", "tencent", "netease", "microsoft",
                      "google", "apple", "meta", "bytedance", "alibaba", "baidu",
                      "electronic arts", "ubisoft", "gameloft", "king", "supercell",
                      "disney", "nickelodeon", "zhejiang royalflush", "travelsky",
                      "samsung", "amazon", "spotify"],
    "offline_positive": ["offline", "no wifi", "no internet", "no wi-fi",
                         "single player", "single-player", "no ads", "no account",
                         "no sign-up", "no signup", "无需联网", "离线", "单机",
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
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (PaidScout/" + VERSION + ")"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8", "replace"))
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
    legacy_paid, disagreements = {}, []

    for cc in countries:
        lp = legacy_chart(cc, "toppaidapplications", limit)
        legacy_paid[cc] = lp
        for app_id, rank, *_rest in lp:
            conn.execute("INSERT OR REPLACE INTO chart_rank VALUES (?,?,?,?,?,?,?)",
                         (today, "legacy", cc, "toppaid", 0, app_id, rank))
            all_ids[cc].add(app_id)
        for app_id, rank, *_rest in legacy_chart(cc, "topgrossingapplications", limit):
            conn.execute("INSERT OR REPLACE INTO chart_rank VALUES (?,?,?,?,?,?,?)",
                         (today, "legacy", cc, "topgrossing", 0, app_id, rank))
        mp = dict(marketing_chart(cc, "top-paid", limit))
        for app_id, rank in mp.items():
            conn.execute("INSERT OR REPLACE INTO chart_rank VALUES (?,?,?,?,?,?,?)",
                         (today, "marketing", cc, "toppaid", 0, app_id, rank))
            all_ids[cc].add(app_id)
        if lp and mp:
            legacy_ids = {a for a, *_ in lp}
            disagreements.append(
                f"{cc}: marketing-only in top{limit}: {len(set(mp) - legacy_ids)} apps; "
                f"legacy-only: {len(legacy_ids - set(mp))} apps (two official feeds disagree — ranks never merged)")
        if not args.quick:
            for gid in genres:
                for app_id, rank, *_rest in legacy_chart(cc, "toppaidapplications", limit, gid):
                    conn.execute("INSERT OR REPLACE INTO chart_rank VALUES (?,?,?,?,?,?,?)",
                                 (today, "legacy", cc, "toppaid", gid, app_id, rank))
                    all_ids[cc].add(app_id)
        conn.commit()

    meta = {}
    for cc in countries:
        summaries = {a: s for a, r, p, n, g, s in legacy_paid[cc]}
        got = lookup_batch(cc, all_ids[cc])
        meta[cc] = got
        for app_id, r in got.items():
            off = classify_offline(r.get("description", "") or summaries.get(app_id, ""),
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
                time.sleep(0.4)
        for app_id, cc, label in watchlist:
            url = f"https://itunes.apple.com/{cc}/rss/customerreviews/id={app_id}/sortBy=mostRecent/json"
            data = fetch_json(url, retries=3)
            n, latest = 0, ""
            if data and data.get("feed", {}).get("entry"):
                entries = [e for e in data["feed"]["entry"] if "im:rating" in e]
                n = len(entries)
                dates = [e.get("updated", {}).get("label", "") for e in entries]
                latest = max(dates) if dates else ""
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

    os.makedirs(args.report_dir, exist_ok=True)
    lines = [f"# PaidScout Report — {today}",
             f"Previous run baseline: {prev or 'none (first run)'}",
             "Sources: Apple legacy RSS charts + MarketingTools RSS + Lookup + Search + Reviews feeds (all official, free).",
             ""]
    for note in disagreements:
        lines.append(f"- CROSS-SOURCE: {note}")
    if FAILURES:
        lines.append(f"- FETCH FAILURES ({len(FAILURES)}): " + " | ".join(FAILURES[:6]))
    lines.append("")
    counts = {}
    for cc in countries:
        lines.append(f"## {cc.upper()} — Top Paid (legacy chart)")
        lines.append("| # | App | Seller | Price | Rating (count) | Δratings vs prev | Rank Δ | Offline | Indie? |")
        lines.append("|---|---|---|---|---|---|---|---|---|")
        counts[cc] = len(legacy_paid[cc])
        for app_id, rank, price, name, genre_name, summary in legacy_paid[cc][:limit]:
            m = meta[cc].get(app_id, {})
            off = classify_offline(m.get("description", "") or summary,
                                   cfg["offline_positive"], cfg["offline_negative"])
            seller = m.get("sellerName", "")
            rcount = m.get("userRatingCount")
            pm = prev_meta(cc, app_id)
            dr = f"+{rcount - pm[0]}" if pm and rcount is not None and pm[0] is not None else "—"
            pr = prev_rank(cc, app_id)
            drank = f"{pr - rank:+d}" if pr else ("NEW" if prev else "—")
            lines.append(f"| {rank} | {m.get('trackName', name)} | {seller or '?'} | {m.get('price', price)} | "
                         f"{m.get('averageUserRating') or '?'} ({rcount or '?'}) | {dr} | {drank} | {off} | "
                         f"{'big-co' if is_big(seller, cfg['big_companies']) else 'indie?'} |")
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
            lines.append(f"- {label} ({cc}): {row[0]} reviews on page 1, latest {row[1] or 'n/a'}")
    lines.append("")
    lines.append("Note: rating-count delta and rank movement are velocity proxies, not download/revenue numbers. "
                 "No panel data = no fabricated estimates.")
    report_path = os.path.join(args.report_dir, f"report-{today}.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(json.dumps({"date": today, "prev": prev, "counts": counts,
                      "failures": FAILURES, "report": report_path}, ensure_ascii=False, indent=1))

if __name__ == "__main__":
    main()
