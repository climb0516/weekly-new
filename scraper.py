#!/usr/bin/env python3
# Created by 青云 on 2026/10/21.
"""本周上新 scraper — 抓取电影、剧集综艺、演唱会开票、数码发布会，输出 data.json。仅依赖 Python 标准库。"""
import html, json, re, time as _time, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, date, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

ROOT   = Path(__file__).parent
OUT    = ROOT / "data.json"
EVENTS = ROOT / "events.json"
COVERS = ROOT / "covers"     # 豆瓣图片有防盗链（非豆瓣 Referer 返回 418/403），海报下载到仓库里
CST    = timezone(timedelta(hours=8))
TODAY  = datetime.now(CST).date()

UA_MOBILE = {"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 "
                           "(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
             "Referer": "https://m.douban.com/", "Accept": "application/json"}
UA_DESK   = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                           "(KHTML, like Gecko) Chrome/126.0 Safari/537.36",
             "Accept-Language": "zh-CN,zh;q=0.9"}

DOUBAN       = "https://m.douban.com/rexxar/api/v2"
TV_LISTS     = {"tv_hot": 60, "tv_domestic": 50, "show_hot": 60, "show_domestic": 30}   # 榜单 → 取前几条
DETAIL_TTL   = 5        # 剧集详情（开播日期、平台）缓存几天后重新拉
NEWS_DAYS    = 21       # 新闻只看最近几天发布的
KEEP_PAST    = 3        # 事件日期过去几天后移除

# 新闻搜索词：Google 新闻为主，Bing 新闻补充
NEWS_QUERIES = {
    "concert":  ["演唱会 开票", "演唱会 开售", "巡回演唱会 官宣", "演唱会 预售"],
    "launch":   ["发布会 定档", "新品发布会 官宣", "发布会 将于", "新品 发布会 时间"],
    "schedule": ["电视剧 定档", "综艺 定档", "新剧 官宣定档", "电影 定档"],
}

# 数码发布会品牌白名单（标题里出现才收录），值为页面显示名
BRANDS = {
    "苹果": "苹果", "Apple": "苹果", "iPhone": "苹果", "华为": "华为", "鸿蒙": "华为", "小米": "小米", "Redmi": "小米",
    "红米": "小米", "OPPO": "OPPO", "一加": "一加", "vivo": "vivo", "iQOO": "vivo", "荣耀": "荣耀", "三星": "三星",
    "Galaxy": "三星", "realme": "realme", "真我": "realme", "魅族": "魅族", "努比亚": "努比亚", "红魔": "努比亚",
    "联想": "联想", "摩托罗拉": "摩托罗拉", "大疆": "大疆", "DJI": "大疆", "索尼": "索尼", "谷歌": "谷歌",
    "Google": "谷歌", "Pixel": "谷歌", "微软": "微软", "英伟达": "英伟达", "NVIDIA": "英伟达", "特斯拉": "特斯拉",
    "理想": "理想", "蔚来": "蔚来", "小鹏": "小鹏", "极氪": "极氪", "问界": "问界", "比亚迪": "比亚迪",
    "零跑": "零跑", "智界": "智界", "尊界": "尊界", "Meta": "Meta", "任天堂": "任天堂", "Switch": "任天堂",
    "PlayStation": "索尼", "传音": "传音", "中兴": "中兴", "华硕": "华硕", "ROG": "华硕", "影石": "影石",
}
# 发布会标题里出现这些词多半不是数码（保险、家居、地产、政务等），直接排除
LAUNCH_EXCLUDE = re.compile(r"人寿|保险|银行|家居|地产|楼盘|白酒|酒业|医药|药业|政府|新闻发布会|招聘|论坛|博览会|学校|大学|基金")

CITIES = ("北京 上海 广州 深圳 天津 重庆 成都 杭州 南京 武汉 西安 长沙 郑州 苏州 青岛 厦门 福州 合肥 济南 沈阳 大连 "
          "哈尔滨 长春 昆明 贵阳 南宁 海口 三亚 南昌 太原 石家庄 呼和浩特 兰州 西宁 银川 乌鲁木齐 拉萨 宁波 无锡 佛山 "
          "东莞 珠海 汕头 惠州 温州 绍兴 嘉兴 徐州 常州 南通 扬州 烟台 潍坊 泉州 洛阳 柳州 桂林 绵阳 澳门 香港 台北 "
          "高雄 新加坡 吉隆坡 首尔 东京").split()

# ── 工具 ──────────────────────────────────────────────────────────────────────

def fetch(url, headers=UA_DESK, timeout=20):
    return urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=timeout).read()

def clean(text):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", text or ""))).strip()

def run(label, fn):
    try:
        res = fn()
        print(f"  ✓ {label:<16} {len(res):>4}")
        return res, ""
    except Exception as e:
        err = f"{type(e).__name__}: {e}"[:200]
        print(f"  ✗ {label:<16}    0 {err}")
        return None, err

def guess_year(month, day, ref):
    """只有月日时，取离 ref 最近的那一年。"""
    best = None
    for y in (ref.year - 1, ref.year, ref.year + 1):
        try:
            d = date(y, month, day)
        except ValueError:
            continue
        if best is None or abs((d - ref).days) < abs((best - ref).days):
            best = d
    return best

def subject_url(kind, sid):
    return f"https://movie.douban.com/subject/{sid}/"

def split_subtitle(s):
    """豆瓣 card_subtitle：年份 / 地区 / 类型 / 导演 / 演员"""
    parts = [p.strip() for p in (s or "").split(" / ")]
    parts += [""] * (5 - len(parts))
    return {"region": parts[1], "genres": parts[2], "directors": parts[3], "actors": parts[4]}

def rating_of(i):
    r = i.get("rating") or {}
    v = r.get("value") or 0
    return (round(v, 1) if v else None), (r.get("count") or 0)

# ── 电影（豆瓣） ──────────────────────────────────────────────────────────────

def douban_list(name, count):
    d = json.loads(fetch(f"{DOUBAN}/subject_collection/{name}/items?start=0&count={count}", UA_MOBILE))
    return d.get("subject_collection_items") or []

def movies(name):
    out = []
    for i in douban_list(name, 50):
        rd = None
        m = re.match(r"(\d{1,2})\.(\d{1,2})", i.get("release_date") or "")
        if m:
            rd = guess_year(int(m[1]), int(m[2]), TODAY).isoformat()
        rating, count = rating_of(i)
        sub = split_subtitle(i.get("card_subtitle"))
        out.append({
            "id": i["id"], "title": i.get("title"), "original_title": i.get("original_title") or "",
            "rating": rating, "rating_count": count, "release": rd, "year": i.get("year") or "",
            "wish": i.get("wish_count") or 0, "cover": (i.get("cover") or {}).get("url", ""),
            "url": subject_url("movie", i["id"]), "desc": (i.get("description") or "")[:200], **sub,
        })
    if not out:
        raise ValueError("empty")
    return out

# ── 剧集 / 综艺（豆瓣） ───────────────────────────────────────────────────────

def tv_detail(sid):
    d = json.loads(fetch(f"{DOUBAN}/tv/{sid}", UA_MOBILE))
    pubs = d.get("pubdate") or []
    pick = next((p for p in pubs if "中国大陆" in p), pubs[0] if pubs else "")
    m = re.match(r"(\d{4})-(\d{2})(?:-(\d{2}))?", pick)
    pubdate = f"{m[1]}-{m[2]}-{m[3] or '01'}" if m else None
    return {"pubdate": pubdate, "pub_precise": bool(m and m[3]),
            "platforms": [v.get("title") for v in d.get("vendors") or [] if v.get("title")],
            "episodes": d.get("episodes_count") or 0, "is_show": bool(d.get("is_show")),
            "intro": (d.get("intro") or "")[:200], "fetched": TODAY.isoformat()}

def tv(prev_cache):
    items, seen = [], {}
    for name, n in TV_LISTS.items():
        try:
            lst = douban_list(name, n)
        except Exception as e:
            print(f"    {name} 失败：{e}")
            continue
        for rank, i in enumerate(lst, 1):
            sid = i["id"]
            if sid in seen:
                seen[sid]["lists"].append(name)
                continue
            rating, count = rating_of(i)
            sub = split_subtitle(i.get("card_subtitle"))
            it = {"id": sid, "title": i.get("title"), "kind": "show" if name.startswith("show") else "tv",
                  "rating": rating, "rating_count": count, "progress": i.get("episodes_info") or "",
                  "year": i.get("year") or "", "cover": (i.get("pic") or {}).get("normal", ""),
                  "url": subject_url("tv", sid), "lists": [name], "rank": rank, **sub}
            seen[sid] = it
            items.append(it)
    if not items:
        raise ValueError("empty")

    # 详情只拉缓存里没有或已过期的，避免每天请求上百次
    stale = [it["id"] for it in items
             if it["id"] not in prev_cache
             or (TODAY - date.fromisoformat(prev_cache[it["id"]]["fetched"])).days >= DETAIL_TTL]
    cache = dict(prev_cache)

    def one(sid):
        _time.sleep(0.3)
        try:
            return sid, tv_detail(sid)
        except Exception:
            return sid, None
    with ThreadPoolExecutor(4) as ex:
        for sid, det in ex.map(one, stale):
            if det:
                cache[sid] = det
    print(f"    剧集详情：新拉 {len(stale)} 条，成功 {sum(1 for s in stale if cache.get(s, {}).get('fetched') == TODAY.isoformat())} 条")

    for it in items:
        det = cache.get(it["id"]) or {}
        it.update({k: det.get(k) for k in ("pubdate", "pub_precise", "platforms", "episodes", "intro")})
        if det.get("is_show"):
            it["kind"] = "show"
    # 缓存只保留这次还在榜上的条目
    tv.cache = {sid: cache[sid] for sid in seen if sid in cache}
    return items
tv.cache = {}

# ── 新闻 RSS（Google / Bing） ─────────────────────────────────────────────────

def google_news(q):
    url = "https://news.google.com/rss/search?" + urllib.parse.urlencode(
        {"q": q, "hl": "zh-CN", "gl": "CN", "ceid": "CN:zh-Hans"})
    x = fetch(url).decode("utf-8", "ignore")
    out = []
    for it in re.findall(r"<item>(.*?)</item>", x, re.S):
        t = clean(re.search(r"<title>(.*?)</title>", it, re.S)[1])
        link = clean(re.search(r"<link>(.*?)</link>", it, re.S)[1])
        pub = re.search(r"<pubDate>(.*?)</pubDate>", it, re.S)
        src = re.search(r"<source[^>]*>(.*?)</source>", it, re.S)
        source = clean(src[1]) if src else ""
        if source and t.endswith(" - " + source):
            t = t[: -len(source) - 3]
        out.append({"title": t, "url": link, "source": source, "published": pub and pub[1]})
    return out

def bing_news(q):
    url = "https://www.bing.com/news/search?" + urllib.parse.urlencode({"q": q, "format": "rss", "setlang": "zh-cn"})
    x = fetch(url).decode("utf-8", "ignore")
    out = []
    for it in re.findall(r"<item>(.*?)</item>", x, re.S):
        t = clean(re.search(r"<title>(.*?)</title>", it, re.S)[1])
        link = clean(re.search(r"<link>(.*?)</link>", it, re.S)[1])
        real = urllib.parse.parse_qs(urllib.parse.urlparse(link).query).get("url")
        pub = re.search(r"<pubDate>(.*?)</pubDate>", it, re.S)
        src = re.search(r"<News:Source>(.*?)</News:Source>", it, re.S)
        out.append({"title": t, "url": real[0] if real else link, "source": clean(src[1]) if src else "",
                    "published": pub and pub[1]})
    return out

def parse_pub(s):
    try:
        return parsedate_to_datetime(s).astimezone(CST)
    except Exception:
        return None

DATE_RE = re.compile(r"(?:(20\d{2})\s*年\s*)?(\d{1,2})\s*月\s*(\d{1,2})\s*[日号]"
                     r"(?:\s*(?:\(|（)?周.(?:\)|）)?)?\s*(?:(上午|中午|下午|晚上|晚)?\s*(\d{1,2})[:：点](\d{2})?)?")
REL_RE  = re.compile(r"(今日|今天|今晚|今夜|明日|明天|明晚|后天)")
WEEK_RE = re.compile(r"(下周|本周|这周)?(?:周|星期)([一二三四五六日天])")
WEEKDAY = {"一": 0, "二": 1, "三": 2, "四": 3, "五": 4, "六": 5, "日": 6, "天": 6}

def extract_date(title, pub, near):
    """从标题里提取事件日期；有多个日期时取离关键词（near）最近的那个。返回 (date, 'HH:MM' 或 '')。"""
    ref = pub.date() if pub else TODAY
    cands = []
    for m in DATE_RE.finditer(title):
        y, mo, d = m[1], int(m[2]), int(m[3])
        try:
            dt = date(int(y), mo, d) if y else guess_year(mo, d, ref)
        except ValueError:
            continue
        if dt is None:
            continue
        hm = ""
        if m[5]:
            h = int(m[5])
            if m[4] in ("下午", "晚上", "晚") and h < 12:
                h += 12
            if h < 24:
                hm = f"{h:02d}:{int(m[6] or 0):02d}"
        cands.append((m.start(), dt, hm))
    for m in REL_RE.finditer(title):
        off = {"明日": 1, "明天": 1, "明晚": 1, "后天": 2}.get(m[1], 0)
        cands.append((m.start(), ref + timedelta(days=off), "20:00" if "晚" in m[1] else ""))
    if not cands:
        for m in WEEK_RE.finditer(title):     # 「定档周四」「下周三发布」：按发稿日往后找
            wd = WEEKDAY[m[2]]
            if m[1] == "下周":
                dt = ref - timedelta(days=ref.weekday()) + timedelta(days=7 + wd)
            else:
                dt = ref + timedelta(days=(wd - ref.weekday()) % 7)
            cands.append((m.start(), dt, ""))
    if not cands:
        return None, ""
    kpos = [k.start() for k in re.finditer(near, title)] or [0]
    best = min(cands, key=lambda c: min(abs(c[0] - p) for p in kpos))
    return best[1], best[2]

def city_of(t):
    hits = [(t.find(c), c) for c in CITIES if c in t]
    return min(hits)[1] if hits else ""

# 演唱会标题里出现这些词多半是攻略、周边、维权、酒店等，不是开票信息
CONCERT_EXCLUDE = re.compile(r"攻略|靠谱|退票|退款|申请退|酒店|黄牛|假信息|虚假|周边|清单|怎么买|合理吗|崩了|散场|住院|抢购.*门票。|座位表")

def norm(t):
    return re.sub(r"[^\u4e00-\u9fa5A-Za-z]", "", t)

def brand_of(t):
    for k, v in BRANDS.items():
        if re.search(r"(?<![A-Za-z])" + re.escape(k) + r"(?![A-Za-z])", t):
            return v
    return ""

def classify(kind, it, pub):
    t = it["title"]
    if kind == "concert":
        if ("演唱会" not in t and "巡演" not in t) or CONCERT_EXCLUDE.search(t):
            return None
        d, hm = extract_date(t, pub, r"开票|开售|预售|开抢|开启售票")
        # 日期紧挨着开票类关键词才算「开票日」，否则多半是演出日
        sale_kw = re.search(r"开票|开售|预售|开抢|售票", t)
        sale = bool(sale_kw and d and re.search(r"\d[日号][^，,。！!]{0,8}(?:开票|开售|预售|开抢|售票)|(?:今日|今天|明天|明日)[^，,。！!]{0,6}(?:开票|开售|预售|开抢)", t))
        return {"date": d, "time": hm, "city": city_of(t), "sale": sale, "announce": bool(sale_kw),
                "key": f"{d}|{city_of(t)}|{norm(t)[:8]}" if d else norm(t)[:24]}
    if kind == "launch":
        if "发布" not in t or LAUNCH_EXCLUDE.search(t):
            return None
        b = brand_of(t)
        if not b:
            return None
        d, hm = extract_date(t, pub, r"发布会|发布|定档|官宣")
        return {"date": d, "time": hm, "brand": b, "key": f"{b}|{d}"}
    if kind == "schedule":
        m = re.search(r"《([^》]{1,30})》", t)
        if not m or "定档" not in t:
            return None
        d, hm = extract_date(t, pub, r"定档|首播|开播|上映|播出")
        cat = "movie" if re.search(r"电影|上映|院线|影片", t) else "show" if re.search(r"综艺|真人秀|节目", t) else "tv"
        plat = next((p for p in ("腾讯视频", "爱奇艺", "优酷", "芒果TV", "湖南卫视", "浙江卫视", "东方卫视", "江苏卫视",
                                 "央视", "CCTV", "B站", "哔哩哔哩", "Netflix", "Disney+") if p in t), "")
        return {"date": d, "time": hm, "name": m[1], "cat": cat, "platform": plat, "key": f"{m[1]}|{d}"}
    return None

def news(kind, prev):
    raw = []
    for q in NEWS_QUERIES[kind]:
        for fn in (google_news, bing_news):
            try:
                raw += fn(q)
            except Exception as e:
                print(f"    {fn.__name__}({q}) 失败：{e}")
    if not raw:
        raise ValueError("all queries failed")

    cutoff = datetime.now(CST) - timedelta(days=NEWS_DAYS)
    groups = {e["key"]: e for e in prev}          # 与上一份合并，RSS 只返回最近一批
    for e in groups.values():
        e["_urls"] = {a["url"] for a in e["articles"]}
    for it in raw:
        pub = parse_pub(it["published"])
        if not pub or pub < cutoff:
            continue
        info = classify(kind, it, pub)
        if not info:
            continue
        if info["date"]:
            info["date"] = info["date"].isoformat()
        art = {"title": it["title"], "url": it["url"], "source": it["source"], "published": pub.isoformat(timespec="minutes")}
        g = groups.get(info["key"])
        if g is None:
            g = groups[info["key"]] = {**info, "articles": [], "_urls": set()}
        if art["url"] in g["_urls"] or any(a["title"] == art["title"] for a in g["articles"]):
            continue
        g["_urls"].add(art["url"])
        g["articles"].append(art)

    out = []
    for g in groups.values():
        g.pop("_urls", None)
        g["articles"].sort(key=lambda a: a["published"], reverse=True)
        g["articles"] = g["articles"][:5]
        latest = g["articles"][0]["published"][:10] if g["articles"] else ""
        if g.get("date"):
            if date.fromisoformat(g["date"]) < TODAY - timedelta(days=KEEP_PAST):
                continue
        elif not latest or date.fromisoformat(latest) < TODAY - timedelta(days=10):
            continue
        g["title"] = g["articles"][0]["title"]
        out.append(g)
    if kind == "launch":
        out = merge_launch(out)
    out.sort(key=lambda g: (g.get("date") or "9999", g["articles"][0]["published"]))
    return out

def merge_launch(items):
    """同品牌、日期相差 2 天内视为同一场发布会：取报道最多的日期，其余日期记在 alt_dates。"""
    dated = sorted((g for g in items if g.get("date")), key=lambda g: (g["brand"], g["date"]))
    out, cur = [g for g in items if not g.get("date")], None
    for g in dated:
        if cur and cur["brand"] == g["brand"] and \
                (date.fromisoformat(g["date"]) - date.fromisoformat(cur["_last"])).days <= 2:
            cur["_votes"][g["date"]] = cur["_votes"].get(g["date"], 0) + len(g["articles"])
            cur["articles"] += g["articles"]
            cur["_last"] = g["date"]
            continue
        cur = {**g, "articles": list(g["articles"]), "_votes": {g["date"]: len(g["articles"])}, "_last": g["date"]}
        out.append(cur)
    for g in out:
        votes = g.pop("_votes", None)
        g.pop("_last", None)
        if votes and len(votes) > 1:
            g["date"] = max(votes, key=lambda d: (votes[d], d))
            g["alt_dates"] = sorted(d for d in votes if d != g["date"])
            g["key"] = f"{g['brand']}|{g['date']}"
            g["time"] = ""
        uniq = {a["url"]: a for a in g["articles"]}       # 上一份合并过的和本次新抓的可能重复
        g["articles"] = sorted(uniq.values(), key=lambda a: a["published"], reverse=True)[:6]
        g["title"] = g["articles"][0]["title"]
    return out

def manual_events():
    if not EVENTS.exists():
        return []
    d = json.loads(EVENTS.read_text("utf-8"))
    return [e for e in d.get("events", []) if e.get("date") and e["date"] >= (TODAY - timedelta(days=KEEP_PAST)).isoformat()]

# ── 海报 ──────────────────────────────────────────────────────────────────────

def save_covers(items):
    """下载缺失的海报（小图），删除已不在榜上的。返回新下载数量。"""
    COVERS.mkdir(exist_ok=True)
    want = {}
    for it in items:
        if it.get("cover"):
            want[f"{it['id']}.jpg"] = it["cover"].replace("/m_ratio_poster/", "/s_ratio_poster/")
            it["cover_local"] = f"covers/{it['id']}.jpg"
    missing = [(n, u) for n, u in want.items() if not (COVERS / n).exists()]

    def one(job):
        name, url = job
        try:
            data = fetch(url, {**UA_DESK, "Referer": "https://movie.douban.com/"})
            if data[:3] == b"\xff\xd8\xff" or data[:4] == b"\x89PNG":
                (COVERS / name).write_bytes(data)
                return True
        except Exception:
            pass
        return False
    with ThreadPoolExecutor(6) as ex:
        ok = sum(ex.map(one, missing))
    for f in COVERS.glob("*.jpg"):
        if f.name not in want:
            f.unlink()
    for it in items:      # 下载失败的不给本地路径，页面显示占位图
        if it.get("cover_local") and not (ROOT / it["cover_local"]).exists():
            it.pop("cover_local")
    print(f"    海报：新下载 {ok}/{len(missing)}，共 {len(list(COVERS.glob('*.jpg')))} 张")
    return ok

# ── 主流程 ────────────────────────────────────────────────────────────────────

def main():
    prev = {}
    if OUT.exists():
        try:
            prev = json.loads(OUT.read_text("utf-8"))
        except Exception:
            prev = {}
    pn = prev.get("news") or {}

    print(f"本周上新 · {TODAY}")
    with ThreadPoolExecutor(6) as ex:
        f_show  = ex.submit(run, "电影·热映", lambda: movies("movie_showing"))
        f_soon  = ex.submit(run, "电影·即将上映", lambda: movies("movie_soon"))
        f_tv    = ex.submit(run, "剧集综艺", lambda: tv(prev.get("tv_cache") or {}))
        f_con   = ex.submit(run, "演唱会", lambda: news("concert", pn.get("concert") or []))
        f_lau   = ex.submit(run, "发布会", lambda: news("launch", pn.get("launch") or []))
        f_sch   = ex.submit(run, "定档", lambda: news("schedule", pn.get("schedule") or []))
    res = {"showing": f_show.result(), "soon": f_soon.result(), "tv": f_tv.result(),
           "concert": f_con.result(), "launch": f_lau.result(), "schedule": f_sch.result()}

    prev_movies = prev.get("movies") or {}
    old = {"showing": prev_movies.get("showing"), "soon": prev_movies.get("soon"), "tv": prev.get("tv"),
           "concert": pn.get("concert"), "launch": pn.get("launch"), "schedule": pn.get("schedule")}
    sources, val = {}, {}
    for k, (data, err) in res.items():
        stale = data is None
        val[k] = (old[k] or []) if stale else data
        sources[k] = {"ok": not stale, "stale": stale and bool(old[k]), "error": err, "count": len(val[k])}

    save_covers(val["showing"] + val["soon"] + val["tv"])

    data = {
        "updated": datetime.now(CST).isoformat(timespec="seconds"),
        "today": TODAY.isoformat(),
        "sources": sources,
        "movies": {"showing": val["showing"], "soon": val["soon"]},
        "tv": val["tv"],
        "news": {"concert": val["concert"], "launch": val["launch"], "schedule": val["schedule"]},
        "manual": manual_events(),
        "tv_cache": tv.cache or prev.get("tv_cache") or {},
    }
    OUT.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), "utf-8")
    print(f"→ data.json {OUT.stat().st_size / 1024:.0f} KB")

if __name__ == "__main__":
    main()
