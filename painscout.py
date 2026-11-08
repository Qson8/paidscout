#!/usr/bin/env python3
"""
PainScout — the demand-side module of PaidScout: weekly mining of app-store
complaints and public community posts into countable, scored need-cards.

PaidScout watches the charts (what is selling); PainScout reads the 1-3 star
reviews and community complaints (what users are suffering, and what they
already pay or hack around). The two share a candidate pool and the same
honesty rules.

What it does:
  - fetches recent App Store reviews (RSS, 1-3 stars) for a seed list of
    apps per category, plus Hacker News complaints via the official
    Algolia API — these are the ONLY automated sources
  - classifies complaint text with a bilingual (EN/ZH) pain taxonomy v1 and
    signal lexicon (workarounds / payment language weighted as heavily as
    frequency; pure price rage and pure feature-wishing are marked noise)
  - clusters by (category x pain class), scores on the cold-start 6-point
    scale (frequency / intensity / unmet, each 0-2) and emits need-cards
    for clusters scoring >= 4, in the internal-card format proven by the
    manual section-0 run
  - writes a weekly report (reports/painscout-YYYY-MM-DD.md), appends the
    cards to a cumulative pool file, and stores a JSON snapshot (data/)

What it deliberately does NOT do:
  - Reddit and Google Play are NEVER automated (their terms make this
    commercial research; section-0 review ruling). V2EX has no public
    keyword-search API, so it is manual-only (T3) too.
  - No MediaCrawler or anything needing a login session. No download or
    revenue numbers. Review quotes in cards are de-identified (no author
    fields are ever fetched into output) and stripped from public editions.

Stdlib only, no API key. Usage:
  python3 painscout.py [--config painscout.json] [--date YYYY-MM-DD]
                       [--dry-run] [--pages 2]
"""
import argparse, json, os, re, sys, time, traceback, urllib.parse, urllib.request
from datetime import date as date_cls

VERSION = "0.3.0"

# ---------------------------------------------------------------------------
# Pain taxonomy v1 (seeded from the manual section-0 run, 2026-11-08).
# Each class: bilingual substring lexicon. Substring matching is crude by
# design: it is a counting instrument, not an understanding instrument —
# the Skill layer re-reads the cards before anything is decided.
# ---------------------------------------------------------------------------
TAXONOMY = {
    "sub_opaque": {
        "name_en": "Opaque subscription / surprise charges",
        "name_zh": "订阅与扣费不透明",
        "en": ["charged me", "charged without", "charged for a free trial",
               "trial converted", "unauthorized charge", "didn't know i was charged",
               "do not know i subscribed", "cancel subscription is", "hard to cancel",
               "impossible to cancel", "no refund", "refused to refund",
               "won't refund", "wouldn't refund", "couldn't get a refund",
               "refuse to help", "auto-renew", "auto renew", "renewed without",
               "sneaky charge", "charged after i cancelled",
               # harvested from real first-run reviews (2026-11-08):
               "auto-deduct", "auto deduct", "automatically charged",
               "immediately charged", "difficult to cancel", "keep billing",
               "charged my card", "charged during the free trial",
               "not a real free trial", "everything requires a subscription",
               "have to pay for everything", "do anything without paying",
               "billing practices", "awful billing", "stole my money",
               "charging us", "charging me", "charged our bank",
               "price increase", "price hike", "without paying",
               "without a subscription", "still billed",
               "even after i cancelled", "after i cancelled they"],
        "zh": ["自动扣费", "自动扣款", "免密", "试用就扣", "莫名其妙扣", "偷偷扣", "扣了198",
               "扣费", "退不了款", "不给退", "取消不了订阅", "一进就扣"],
        "falsify": "后续快照中该主题量级回落至个位数且竞品已公开改价/改试用规则，视为已缓解。",
    },
    "trust_data": {
        "name_en": "Data & trust (wrong math, export lock-in, data loss)",
        "name_zh": "数据与信任（计算不可信、导出锁定、数据丢失）",
        "en": ["numbers just don't add up", "numbers don't add up", "math is wrong",
               "calculation is wrong", "calculations are wrong", "not accurate",
               "isn't accurate", "don't trust this app", "do not trust",
               "pay to export", "export is behind", "export requires a subscription",
               "charging for export", "lost my data", "lost all my data",
               "data disappeared", "deleted my data", "lost my records",
               "can't get my data out", "wrong balance", "wrong total"],
        "zh": ["算得不对", "计算不准", "数字对不上", "账算错", "导出还要",
               "导出收费", "导出要开会员", "数据丢", "记录没了", "数据没了",
               "记录丢", "不敢信", "算的不准", "记录都没了"],
        "falsify": "竞品发布可复算明细/免费导出并在后续评论中被证实，空位消失则降级。",
    },
    "plan_rigid": {
        "name_en": "Plan & editing rigidity (plans can't follow real life)",
        "name_zh": "计划与编辑僵化",
        "en": ["can't edit", "cannot edit", "no way to edit", "won't let me edit",
               "edit payments", "extra payment", "additional payment",
               "one-time payment", "lump sum", "resetting your data",
               "reset my data", "reset all", "start over from scratch",
               "have to do that manually", "manually every month",
               "manually enter every", "can't change the payment",
               "cannot change the amount", "pay more than the minimum",
               "pay extra towards"],
        "zh": ["不能改", "改不了", "没法改", "不能编辑", "编辑不了", "要重置",
               "重置数据", "重新开始", "每个月都要手动", "手动登记", "手动记",
               "额外还款", "想多还", "多还一笔", "计划改不了"],
        "falsify": "访谈/后续评论显示多数用户从不调整计划、按固定金额还，则降级为普通功能请求。",
    },
    "content_lack": {
        "name_en": "Content insufficiency (thin, repetitive, removed)",
        "name_zh": "内容不足（少、重复、被删减转付费）",
        "en": ["not enough content", "limited content", "limited meditations",
               "same content", "same session", "same meditations",
               "repeats the same", "repetitive", "ran out of",
               "nothing new", "they removed", "took away", "used to be free",
               "used to have", "fewer sounds", "content is lacking",
               "lacking meditations", "only a few meditations",
               "very few meditations", "all so short"],
        "zh": ["内容太少", "内容少", "翻来覆去", "就这几个", "就这几首",
               "老是重复", "一直重复", "没更新", "内容被删", "以前免费的"],
        "falsify": "竞品持续上新且评论转向夸内容量，本簇视为版本期波动。",
    },
    "ai_aversion": {
        "name_en": "AI aversion (AI coach / AI voice / AI content / data mining)",
        "name_zh": "AI 化反感",
        "en": ["ai voice", "ai coach", "ai-generated", "ai generated content",
               "ai content", "ai narration", "robot voice", "sounds like a robot",
               "data mining", "hate the ai", "ai slop", "ai meditations",
               "ai voices",
               # harvested from real first-run reviews (2026-11-08):
               "ai chatbot", "ai chat bot", "ai-created", "ai created",
               "pushing ai", "ai meditation", "ai therapist", " ai ",
               "artificial intelligence"],
        "zh": ["AI配音", "AI 配音", "AI生成", "AI 生成", "机器音", "电子音",
               "像机器人", "数据挖掘", "人工智能配音", "AI教练", "AI 教练"],
        "falsify": "后续快照中该主题量级不涨反消，视为版本期情绪，不作定位依据。",
    },
    "credits_wall": {
        "name_en": "Credits & paywall mechanics (caps, expiring credits, zero trial)",
        "name_zh": "点数与付费墙（限量、过期清零、零试用）",
        "en": ["credits expire", "points expire", "expired and lost",
               "lose my credits", "lost my credits", "no free trial",
               "no trial at all", "not even a trial", "paywall before",
               "pay before you can", "one video per month", "per picture",
               "charge per", "runs out of credits", "out of credits",
               "bought credits", "purchased credits"],
        "zh": ["过期清零", "过期就清零", "清零", "按张买", "按张收费", "限时",
               "点数过期", "点数没了", "没试用", "不能试用", "没有试用",
               "先付费才能", "次数用完", "买的张数",
               # 首跑真实评论句式（2026-11-08）：
               "张数直接过期", "过期不给用", "限定使用时间", "限使用时间",
               "限制时间", "限制张数", "双重限制", "霸王条款", "只能用三张",
               "按张数购买"],
        "falsify": "访谈中目标人群对点数过期无感、只在意效果质量，则本簇降级。",
    },
    "gen_fail": {
        "name_en": "Generation failure without explanation",
        "name_zh": "生成失败无解释",
        "en": ["failed at 95", "keeps failing", "generation failed",
               "failed to generate", "no reason given", "doesn't tell me why",
               "don't tell you why", "rejected without", "won't save",
               "can't save my", "tried 7 times", "tried several times",
               "never works", "always fails"],
        "zh": ["不符合范围", "不给原因", "没说原因", "不告诉原因", "审核不通过",
               "生成失败", "转不了", "保存不了", "试了好几次", "试了7遍",
               "一直失败", "老是失败", "进度95", "生成不了", "无法生成",
               "生成不出来"],
        "falsify": "失败集中在个别输入类型且厂商已补原因提示，后续量级回落则关闭。",
    },
    "forced_flow": {
        "name_en": "Forced flow interruptions (onboarding walls, sign-up, pop-ups)",
        "name_zh": "强制流程打断",
        "en": ["forces me to", "forced to answer", "million questions",
               "answer questions before", "have to answer", "must create an account",
               "required to sign up", "sign-up wall", "can't skip", "unskippable",
               "before i can even", "set my goals", "onboarding flow",
               "full-screen pop", "commitment pop",
               "bombarded with", "forced to sign", "have to sign up",
               "must sign up", "requires an account"],
        "zh": ["强制", "一打开就", "必须注册", "必须登录", "先填问卷",
               "不能跳过", "目标设定", "先答题", "开屏就要", "弹窗让我"],
        "falsify": "竞品改版去掉开屏流程后该簇量级归零，视为已解决。",
    },
}

# Signal lexica: the section-0 lesson is that a workaround or payment
# language hit validates a need far more than raw frequency does.
WORKAROUND_EN = ["excel", "spreadsheet", "google sheets", "pen and paper",
                 "paper notebook", "notes app", "my workaround", "i just use",
                 "just use the timer", "timer on my phone", "phone's timer",
                 "manually track", "using chatgpt", "use youtube for",
                 "free ones on youtube", "calculator app"]
WORKAROUND_ZH = ["表格", "备忘录", "纸笔", "手算", "自己算", "计算器",
                 "记在本子", "手机计时器", "手动记", "自己建了个表", "多维表格"]
PAYMENT_EN = ["i'd pay", "i would pay", "willing to pay", "happy to pay",
              "pay once", "one-time purchase", "lifetime deal", "lifetime membership",
              "take my money", "worth paying for", "give me my money back",
              "my hard-earned", "refund my", "paid for a year"]
PAYMENT_ZH = ["愿意付", "愿意花钱", "买断", "退钱", "还给我", "真金白银",
              "充了钱", "花了钱买", "买了年卡", "终身会员"]
PRICE_RAGE_EN = ["too expensive", "rip-off", "ripoff", "greedy", "cash grab",
                 "money grab", "overpriced", "price is insane", "not worth the money"]
PRICE_RAGE_ZH = ["太贵了", "吃相", "割韭菜", "抢钱", "坑钱", "死贵", "价格离谱"]
WISH_EN = ["i wish there", "wish there was", "please add", "would be nice if",
           "feature request", "should add a", "needs an option to"]
WISH_ZH = ["希望能加", "求加一个", "要是有就好了", "希望增加", "建议加上"]
UNRESOLVED_EN = ["still not", "still doesn't", "still can't", "still broken",
                 "never fixed", "broke after the update", "after the update it",
                 "no response from support", "developer never responded",
                 "worse with every update"]
UNRESOLVED_ZH = ["还是不行", "一直没修", "更新后就", "更新完就", "没人理",
                 "客服不理", "越来越差", "越更新越难用", "越来越难用"]

FAILURES = []

def fetch_json(url, retries=3, timeout=25):
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "PainScout/" + VERSION + " (+https://github.com/Qson8/paidscout)"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8", "replace"))
        except urllib.error.HTTPError as e:
            if attempt == retries - 1:
                FAILURES.append(f"{url[:110]} -> {e}")
                return None
            if e.code == 429:
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

def _hits(text_lower, words):
    return [w for w in words if w.lower() in text_lower]

def classify_text(text):
    """Return (pain classes hit, signal flags) for one complaint text.
    Bilingual substring matching over the lexica above."""
    t = (text or "").lower()
    cats = set()
    for key, spec in TAXONOMY.items():
        if _hits(t, spec["en"]) or _hits(t, spec["zh"]):
            cats.add(key)
    signals = {
        "workaround": bool(_hits(t, WORKAROUND_EN) or _hits(t, WORKAROUND_ZH)),
        "payment": bool(_hits(t, PAYMENT_EN) or _hits(t, PAYMENT_ZH)),
        "price_rage": bool(_hits(t, PRICE_RAGE_EN) or _hits(t, PRICE_RAGE_ZH)),
        "wish": bool(_hits(t, WISH_EN) or _hits(t, WISH_ZH)),
        "unresolved": bool(_hits(t, UNRESOLVED_EN) or _hits(t, UNRESOLVED_ZH)),
    }
    return cats, signals

def is_noise_only(text, cats, signals):
    """Pure price rage or a bare feature wish, with no workaround/payment
    signal and too little detail to act on — marked noise, per section-0."""
    if signals["workaround"] or signals["payment"]:
        return False
    if not (signals["price_rage"] or signals["wish"]):
        return False
    return len((text or "").strip()) < 60

def score_cluster(count, workaround_hits, payment_hits, apps_hit,
                  unresolved_hits, noise_hits):
    """Cold-start 6-point score: frequency / intensity / unmet, each 0-2.
    Cross-app resonance feeds the unmet judgement; evidence strength is
    reported on the card, and asset fit is a manual slot — together these
    are the six dimensions of the productisation spec, mapped onto the
    section-0 three-part scale so engine scores compare 1:1 with the
    manual cards."""
    if count >= 10:
        freq = 2
    elif count >= 3:
        freq = 1
    else:
        freq = 0
    strong = workaround_hits + payment_hits
    if strong >= 4:
        intensity = 2
    elif strong >= 1:
        intensity = 1
    else:
        intensity = 0
    if (apps_hit >= 2 and unresolved_hits >= 1) or unresolved_hits >= 3:
        unmet = 2
    elif unresolved_hits >= 1 or apps_hit >= 2:
        unmet = 1
    else:
        unmet = 0
    total = freq + intensity + unmet
    return {"freq": freq, "intensity": intensity, "unmet": unmet, "total": total}

_URL_RE = re.compile(r"https?://\S+|www\.\S+")
_MAIL_RE = re.compile(r"\S+@\S+")

def deidentify(text, limit=140):
    """Strip anything that could identify a reviewer from a quote.
    Author fields are never read from the feed in the first place; this
    additionally removes URLs / addresses pasted into review bodies."""
    t = _URL_RE.sub("[链接]", text or "")
    t = _MAIL_RE.sub("[邮箱]", t)
    t = " ".join(t.split())
    return t[:limit]

def fetch_reviews(app_id, cc, pages=2):
    """Recent reviews for one app from Apple's public reviews RSS.
    Returns list of dicts {rating, title, body, date} — author is dropped
    at parse time. Empty list + FAILURES entry means the feed failed,
    which is distinguishable from a true zero."""
    out = []
    for p in range(1, pages + 1):
        url = (f"https://itunes.apple.com/{cc}/rss/customerreviews/id={app_id}"
               f"/sortBy=mostRecent/page={p}/json")
        data = fetch_json(url)
        if data and p == 1 and not any("im:rating" in e for e in
                                       ((data.get("feed") or {}).get("entry") or [])):
            # Apple's reviews RSS intermittently returns an entry-less shell
            # for some app/storefront pairs — retry spaced before recording
            # the probe as failed (it stays a failure, never a fake zero).
            for wait in (4, 8):
                time.sleep(wait)
                data = fetch_json(url) or data
                if any("im:rating" in e for e in
                       ((data.get("feed") or {}).get("entry") or [])):
                    break
        if not data:
            continue
        entries = (data.get("feed") or {}).get("entry") or []
        got = 0
        for e in entries:
            if "im:rating" not in e:
                continue  # first entry is the app itself, not a review
            try:
                rating = int(e["im:rating"]["label"])
            except Exception:
                continue
            out.append({
                "rating": rating,
                "title": ((e.get("title") or {}).get("label") or "").strip(),
                "body": ((e.get("content") or {}).get("label") or "").strip(),
                "date": ((e.get("updated") or {}).get("label") or "")[:10],
            })
            got += 1
        if got == 0 and p == 1:
            FAILURES.append(f"reviews empty: {cc} id={app_id} page1")
        time.sleep(0.4)
    return out

def fetch_hn(query, hits=50):
    """HN Algolia official API (keyless). Stories + comments matching a
    category query; only title/text is used, authors are dropped."""
    url = ("https://hn.algolia.com/api/v1/search?query=" + urllib.parse.quote(query)
           + "&tags=(story,comment)&hitsPerPage=" + str(hits))
    data = fetch_json(url)
    out = []
    if data:
        for h in data.get("hits", []):
            text = " ".join(x for x in [h.get("title") or "", h.get("story_text") or "",
                                        h.get("comment_text") or ""] if x)
            text = re.sub(r"<[^>]+>", " ", text)
            if text.strip():
                out.append({"text": text.strip(), "date": (h.get("created_at") or "")[:10]})
    return out

DEFAULT_CONFIG = {
    # Seed categories = the manual section-0 run (2026-11-08). App lists are
    # copied from the section-0 need-card file; ids resolved via iTunes
    # Search and verified against trackName/seller before first run.
    "pages_per_app": 2,
    "categories": [
        {
            "key": "meditation", "name_zh": "冥想", "name_en": "Meditation",
            "prefix": "M",
            "apps": [
                ["571800810", "us", "Calm"],
                ["493145008", "us", "Headspace"],
                ["337472899", "us", "Insight Timer"],
                ["1077776987", "cn", "潮汐 Tide"],
            ],
            "hn_queries": ["meditation app subscription", "calm app", "headspace ai"],
            "audience": "一念禅现有用户与小红书/TikTok 冥想人群（人工触达）",
            "asset_hint": "自家产品一念禅所在品类：命中簇默认按「参考应用增强（一念禅）」方向判读，待 Skill 复核",
        },
        {
            "key": "debt", "name_zh": "负债记账", "name_en": "Debt payoff",
            "prefix": "D",
            "apps": [
                ["491258643", "us", "Debt Payoff Planner"],
                ["6504497332", "us", "Debt Snowball Calculator"],
                ["1236155003", "cn", "鲨鱼记账"],
            ],
            "hn_queries": ["debt payoff app", "debt snowball spreadsheet"],
            "audience": "小红书负债人群与小安账访谈招募池（人工触达）",
            "asset_hint": "自家在研产品小安账/债见所在品类：命中簇默认按「参考应用增强（小安账）」方向判读，待 Skill 复核",
        },
        {
            "key": "kidsdraw", "name_zh": "儿童画", "name_en": "Kids drawing animation",
            "prefix": "C",
            "apps": [
                ["6476923108", "us", "Drawings Alive"],
                ["6743614900", "cn", "像素蛋糕 PixCake"],
            ],
            "hn_queries": ["kids drawing app animation"],
            "audience": "抖音/小红书儿童画家长人群（人工触达）",
            "asset_hint": "方向候选池在审方向（儿童画离线版）：命中簇默认按「全新应用」方向判读，待 Skill 复核",
        },
    ],
}

def analyse_category(cat, pages):
    """Fetch + classify one seed category. Returns (stats, reviews_index)
    where stats[cat][app_label] counts and stats['classes'][cls] aggregates
    everything score_cluster / card rendering needs."""
    per_app = {}
    classes = {k: {"count": 0, "apps": set(), "workaround": 0, "payment": 0,
                   "unresolved": 0, "noise": 0, "concrete": 0, "quotes": [],
                   "low_star": 0}
               for k in TAXONOMY}
    total_fetched, total_kept = 0, 0
    for app_id, cc, label in cat["apps"]:
        reviews = fetch_reviews(app_id, cc, pages)
        kept = [r for r in reviews if r["rating"] <= 3]
        per_app[label] = {"fetched": len(reviews), "kept_1_3_star": len(kept),
                          "id": app_id, "cc": cc}
        total_fetched += len(reviews)
        total_kept += len(kept)
        for r in kept:
            text = (r["title"] + " " + r["body"]).strip()
            cats, signals = classify_text(text)
            noise = is_noise_only(text, cats, signals)
            for cls in cats:
                s = classes[cls]
                if noise:
                    s["noise"] += 1
                    continue
                s["count"] += 1
                s["apps"].add(label)
                if signals["workaround"]:
                    s["workaround"] += 1
                if signals["payment"]:
                    s["payment"] += 1
                if signals["unresolved"]:
                    s["unresolved"] += 1
                if len(text) >= 80:
                    s["concrete"] += 1
                if len(s["quotes"]) < 12:
                    s["quotes"].append({
                        "text": deidentify(r["title"] + " — " + r["body"]),
                        "app": label, "strong": signals["workaround"] or signals["payment"],
                        "rating": r["rating"]})
    hn_counts = {}
    for q in cat.get("hn_queries", []):
        hits = fetch_hn(q)
        matched = 0
        for h in hits:
            cats, _sig = classify_text(h["text"])
            for cls in cats:
                if cls in classes:
                    matched += 1
        hn_counts[q] = {"hits": len(hits), "pain_matched": matched}
        time.sleep(0.3)
    return {"per_app": per_app, "classes": classes,
            "total_fetched": total_fetched, "total_kept": total_kept,
            "hn": hn_counts}

def build_cards(cat, stats, today):
    """Score every (category x class) cluster; >= 4 becomes a need-card."""
    cards, observed = [], []
    for cls, s in stats["classes"].items():
        if s["count"] == 0 and s["noise"] == 0:
            continue
        sc = score_cluster(s["count"], s["workaround"], s["payment"],
                           len(s["apps"]), s["unresolved"], s["noise"])
        evidence = 2 if s["concrete"] >= 3 else (1 if s["concrete"] >= 1 else 0)
        row = {"class": cls, "stats": s, "score": sc, "evidence": evidence}
        if sc["total"] >= 4:
            cards.append(row)
        elif sc["total"] >= 2:
            observed.append(row)
    cards.sort(key=lambda r: (-r["score"]["total"], -r["stats"]["count"]))
    observed.sort(key=lambda r: (-r["score"]["total"], -r["stats"]["count"]))
    out = []
    for i, row in enumerate(cards, 1):
        cls, s, sc = row["class"], row["stats"], row["score"]
        spec = TAXONOMY[cls]
        quotes = sorted(s["quotes"], key=lambda q: (not q["strong"], -len(q["text"])))[:3]
        out.append({
            "id": f"{cat['prefix']}-E{i}",
            "date": today, "category": cat["key"], "category_zh": cat["name_zh"],
            "class": cls, "pain_zh": spec["name_zh"], "pain_en": spec["name_en"],
            "headline": f"{cat['name_zh']}用户在骂：{spec['name_zh']}",
            "score": sc, "evidence_strength": row["evidence"],
            "count": s["count"], "noise": s["noise"], "concrete": s["concrete"],
            "apps": sorted(s["apps"]),
            "workaround_hits": s["workaround"], "payment_hits": s["payment"],
            "unresolved_hits": s["unresolved"],
            "quotes": [{"text": q["text"], "app": q["app"]} for q in quotes],
            "audience": cat.get("audience", "待人工标注"),
            "asset_hint": cat.get("asset_hint", ""),
            "price_hypothesis": "待人工（Skill 判读时按 PaidScout 候选池口径填）",
            "opportunity_type": "待人工判读（增强/全新）",
            "falsify": spec["falsify"],
        })
    return out, observed

def render_card_md(card, star=False):
    sc = card["score"]
    head = "★ " if star else ""
    lines = [f"### {head}{card['id']} {card['headline']}",
             f"- 分类：{card['pain_zh']}（{card['pain_en']}）｜类型：{card['opportunity_type']}",
             f"- 痛点分 **{sc['total']}/6（冷启动期）**（频次 {sc['freq']}/强度 {sc['intensity']}/未被满足 {sc['unmet']}）"
             f"｜证据强度 {card['evidence_strength']}/2（具体型评论 {card['concrete']} 条，噪声另计 {card['noise']} 条）",
             f"- 计数证据：{card['count']} 条 1–3 星评论命中，覆盖 App：{', '.join(card['apps']) or '—'}"
             f"；土办法语言 {card['workaround_hits']} 条、付费语言 {card['payment_hits']} 条、未解决标记 {card['unresolved_hits']} 条",
             f"- 跨应用共振：{len(card['apps'])} 个 App（喂未被满足度判定，不单列计分）；持续性/跨源共振：冷启动期停算（快照攒满 4 周后启用）",
             f"- 资产契合：人工标记位——{card['asset_hint']}",
             f"- 可触达人群：{card['audience']}",
             f"- 报价假设：{card['price_hypothesis']}",
             f"- 证伪条件：{card['falsify']}"]
    if card["quotes"]:
        lines.append("- 去标识原话（内部版，≤3 条）：")
        for q in card["quotes"]:
            lines.append(f"  - 「{q['text']}」（{q['app']}）")
    lines.append("")
    return lines

def main():
    ap = argparse.ArgumentParser(description="PainScout — weekly complaint mining (PaidScout demand-side module)")
    ap.add_argument("--date", default=date_cls.today().isoformat())
    ap.add_argument("--config", default=None, help="path to config JSON (defaults: built-in seed categories)")
    ap.add_argument("--data-dir", default="data")
    ap.add_argument("--report-dir", default="reports")
    ap.add_argument("--pages", type=int, default=None, help="review RSS pages per app (default from config)")
    ap.add_argument("--dry-run", action="store_true", help="print the run plan only; no network, no files written")
    ap.add_argument("--version", action="version", version=f"PainScout {VERSION}")
    args = ap.parse_args()

    cfg = json.loads(json.dumps(DEFAULT_CONFIG))
    if args.config:
        with open(args.config, encoding="utf-8") as f:
            cfg.update(json.load(f))
    pages = args.pages or int(cfg.get("pages_per_app", 2))
    today = args.date
    cats = cfg["categories"]

    if args.dry_run:
        plan = {"date": today, "mode": "dry-run", "pages_per_app": pages,
                "categories": [{"key": c["key"], "apps": c["apps"],
                                "hn_queries": c.get("hn_queries", [])} for c in cats],
                "sources": ["App Store reviews RSS (US/CN)", "HN Algolia"],
                "never_automated": ["Reddit", "Google Play", "V2EX (no public keyword search; T3 manual)"]}
        print(json.dumps(plan, ensure_ascii=False, indent=1))
        return

    os.makedirs(args.data_dir, exist_ok=True)
    os.makedirs(args.report_dir, exist_ok=True)
    prior_snapshots = len([f for f in os.listdir(args.data_dir)
                           if f.startswith("painscout-") and f.endswith(".json")])

    all_cards, per_cat_stats = [], {}
    for cat in cats:
        stats = analyse_category(cat, pages)
        cards, observed = build_cards(cat, stats, today)
        per_cat_stats[cat["key"]] = {"stats": stats, "observed": observed}
        for c in cards:
            c["_cat_order"] = cats.index(cat)
        all_cards.extend(cards)

    # Weekly headline cards are capped at 3 across all categories.
    ranked = sorted(all_cards, key=lambda c: (-c["score"]["total"], -c["count"]))
    star_ids = {c["id"] + c["category"] for c in ranked[:3]}

    lines = [f"# PainScout Weekly — {today}",
             "Demand-side module of PaidScout: what users curse, counted — the supply side (charts) lives in the daily PaidScout report.",
             "",
             "口径：自动数据源只有 App Store 评论 RSS（US/CN，取 1–3 星）＋ HN Algolia 官方 API。"
             "Reddit、Google Play 永不进自动管道；V2EX 无免登录关键词检索接口，列 T3 人工、本期未接入。"
             "评分是冷启动 6 分制（频次/强度/未被满足，各 0–2，≥4 出卡）；持续性与跨源共振在快照攒满 4 周前停算。"
             "资产契合为人工标记位，不计分。评论量与计数全部来自本轮实跑，不估算下载/收入。",
             ""]
    if FAILURES:
        lines.append(f"- FETCH FAILURES ({len(FAILURES)}): " + " | ".join(FAILURES[:8]))
        lines.append("")
    lines.append("## 样本总账")
    lines.append("| 品类 | 抓取评论 | 1–3 星留存 | HN 命中（痛点匹配） | 出卡 |")
    lines.append("|---|---|---|---|---|")
    snapshot = {"date": today, "version": VERSION, "categories": {}, "cards": []}
    for cat in cats:
        st = per_cat_stats[cat["key"]]["stats"]
        hn_hits = sum(v["hits"] for v in st["hn"].values())
        hn_match = sum(v["pain_matched"] for v in st["hn"].values())
        n_cards = len([c for c in all_cards if c["category"] == cat["key"]])
        lines.append(f"| {cat['name_zh']} {cat['name_en']} | {st['total_fetched']} | {st['total_kept']} "
                     f"| {hn_hits}（{hn_match}） | {n_cards} |")
        snapshot["categories"][cat["key"]] = {
            "fetched": st["total_fetched"], "kept_1_3_star": st["total_kept"],
            "per_app": st["per_app"], "hn": st["hn"],
            "classes": {k: {"count": v["count"], "noise": v["noise"],
                            "workaround": v["workaround"], "payment": v["payment"],
                            "unresolved": v["unresolved"], "concrete": v["concrete"],
                            "apps": sorted(v["apps"])}
                        for k, v in st["classes"].items()}}
    lines.append("")
    lines.append(f"（本轮为第 {prior_snapshots + 1} 期快照；持续性/跨源共振 {( '已启用' if prior_snapshots >= 4 else '仍停算，攒满 4 周后启用')}）")
    lines.append("")

    if ranked:
        lines.append("## 本周主卡（≤3）")
        for c in ranked[:3]:
            lines += render_card_md(c, star=True)
        rest = ranked[3:]
        if rest:
            lines.append("## 入池卡（其余 ≥4 分）")
            for c in rest:
                lines += render_card_md(c)
    else:
        lines.append("## 本周出卡\n\n无（所有簇 <4 分，见观察区与计数全表）。\n")

    lines.append("## 观察区（2–3 分，未出卡）")
    any_obs = False
    for cat in cats:
        for row in per_cat_stats[cat["key"]]["observed"]:
            any_obs = True
            s = row["stats"]
            lines.append(f"- {cat['name_zh']}·{TAXONOMY[row['class']]['name_zh']}：{row['score']['total']}/6"
                         f"（频次 {row['score']['freq']}/强度 {row['score']['intensity']}/未被满足 {row['score']['unmet']}），"
                         f"命中 {s['count']} 条、覆盖 {len(s['apps'])} 个 App、噪声 {s['noise']} 条")
    if not any_obs:
        lines.append("- （无）")
    lines.append("")
    lines.append("## 分类计数全表（1–3 星评论命中数）")
    lines.append("| 品类 | " + " | ".join(TAXONOMY[k]["name_zh"] for k in TAXONOMY) + " |")
    lines.append("|" + "---|" * (len(TAXONOMY) + 1))
    for cat in cats:
        st = per_cat_stats[cat["key"]]["stats"]
        lines.append(f"| {cat['name_zh']} | " + " | ".join(str(st["classes"][k]["count"]) for k in TAXONOMY) + " |")
    lines.append("")
    lines.append("Notes: 关键词子串匹配是计数工具不是理解工具，出卡后须由 Skill 层复核原话再决策；"
                 "低星评论天然带幸存者偏差，需求卡只是访谈与付费验证的入口。原话已去标识（解析时不读作者字段，正文链接/邮箱已打码），"
                 "对外版周报会整段剥离原话。")
    report_path = os.path.join(args.report_dir, f"painscout-{today}.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    public_cards = []
    for c in all_cards:
        cc = dict(c)
        cc.pop("_cat_order", None)
        snapshot["cards"].append(cc)
        pc = dict(cc)
        pc["quotes"] = []  # public snapshot keeps counts only
        public_cards.append(pc)
    snap_path = os.path.join(args.data_dir, f"painscout-{today}.json")
    with open(snap_path, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, ensure_ascii=False, indent=1)

    pool_path = os.path.join(args.report_dir, "painscout-cards.md")
    new_pool = not os.path.exists(pool_path)
    with open(pool_path, "a", encoding="utf-8") as f:
        if new_pool:
            f.write("# PainScout 需求卡池（累积，只追加）\n\n"
                    "内部版：含去标识原话，仅本地/私有仓库。公开引用请用对外版（剥离原话）。\n")
        f.write(f"\n## {today}（第 {prior_snapshots + 1} 期）\n\n")
        if ranked:
            for c in ranked:
                f.write("\n".join(render_card_md(c, star=(c["id"] + c["category"]) in star_ids)) + "\n")
        else:
            f.write("（本期无 ≥4 分卡）\n")

    summary = {"date": today, "version": VERSION,
               "categories": {c["key"]: {"fetched": per_cat_stats[c["key"]]["stats"]["total_fetched"],
                                          "kept": per_cat_stats[c["key"]]["stats"]["total_kept"],
                                          "cards": len([x for x in all_cards if x["category"] == c["key"]])}
                              for c in cats},
               "cards_total": len(all_cards),
               "failures": FAILURES, "report": report_path, "snapshot": snap_path}
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    if FAILURES:
        sys.exit(1)

if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
        sys.exit(3)
