# 🍿 本周上新 · 电影 剧集 演唱会 发布会

> 一个页面看完这周的新东西：新上映电影（带豆瓣评分）、新开播剧集综艺、全国演唱会开票、数码发布会倒计时

**🌐 在线访问：[https://climb0516.github.io/weekly-new/](https://climb0516.github.io/weekly-new/)**

---

## 功能

- **概览**：顶部是「本周新上映」「新片最高分」「下一场发布会」「最近开票」；下面是从昨天到未来 5 天的日历，每天列出电影上映、剧集开播、定档、发布会、开票，并展示本周新片和近 14 天新开播的剧集综艺
- **电影**：豆瓣「正在热映」和「即将上映」，可按热度 / 想看人数、评分、上映日期排序；上映 7 天内的标「新片」；新闻里定档、豆瓣还没收录的电影单独列出
- **剧集 · 综艺**：豆瓣热门剧集和综艺（国产 + 海外），显示开播日期、播出平台、更新进度、评分；可切换「近 14 天开播」和「热门」；下方是新闻里的「即将定档」
- **演唱会**：全国演唱会的开票 / 演出日历（标题里有明确日期的），可按城市筛选；其余开票、官宣新闻放在「近期开票动态」
- **发布会**：手机、电脑、汽车等品牌发布会日程和倒计时；同一场发布会的报道日期不一致时（时差、口径不同），取报道最多的日期，并注明其他日期
- 全文搜索（`⌘K` / `Ctrl K`），右上角：↻ 重新读取数据，⚡ 跳转 GitHub Actions 手动触发抓取，☾ 切换深浅色；手机适配

---

## 人工补充发布会

编辑 `events.json`，push 后会自动重新抓取：

```
{
  "events": [
    { "date": "2026-10-28", "time": "01:00", "brand": "苹果", "title": "苹果秋季新品发布会", "url": "https://..." }
  ]
}
```

日期过去 3 天后自动不再显示。

---

## 技术架构

```
GitHub Actions（每天 08:00 北京时间 / 手动 dispatch / 修改 scraper.py、events.json 或 workflow 后 push）
  ↓ python scraper.py（只用标准库，无需安装依赖）
  ↓ 线程池并发（6 线程）：豆瓣电影热映 / 即将上映、豆瓣剧集综艺 4 个榜、新闻（演唱会 / 发布会 / 定档）Google + Bing RSS
  ↓ 豆瓣详情补全（剧集 / 电影，带缓存）→ 新闻 classify() 过滤 + 标题提日期 → 与上一份合并分组 → 发布会同场合并
  ↓ 读 events.json 人工发布会 → 下载缺失海报到 covers/、删除下榜海报
  ↓ 写入 data.json → commit data.json + covers
       ↓
GitHub Pages（index.html）
  ↓ 前端读取同目录 data.json，倒计时每分钟在浏览器里重算
  ↓ 概览 / 电影 / 剧集综艺 / 演唱会 / 发布会
  ↓ kit 详情抽屉（#/item/movie|tv|sched|concert|launch/…）+ 列表页（#/list/movie、tv、concert、day/<日期>）
```

- 不用数据库；新闻按分组累积在 `data.json` 里，事件日期过去 3 天后移除
- 某个来源本次抓取失败时沿用上一次的数据，右侧「来源状态」标注「旧数据」

---

## 数据来源

| 来源 | 方式 | 每次条数 | 备注 |
|------|------|---------|------|
| 豆瓣 `movie_showing` | 接口：`m.douban.com/rexxar/api/v2/subject_collection/<榜>/items`（移动端 UA + Referer） | 最多 50 | 正在热映：评分、评分人数、上映日期、想看人数、地区 / 类型 / 导演 / 演员 |
| 豆瓣 `movie_soon` | 同上 | 最多 50 | 即将上映 |
| 豆瓣 `tv_hot` / `tv_domestic` / `show_hot` / `show_domestic` | 同上 | 60 / 50 / 60 / 30（`TV_LISTS`），跨榜按 id 去重 | 热门剧集和综艺，评分、更新进度 |
| 豆瓣剧集详情 | 接口：`/tv/<id>` | 只请求缓存里没有或超过 5 天的（`DETAIL_TTL = 5`） | 开播日期（优先「中国大陆」）、播出平台、总集数、是否综艺、简介 |
| 豆瓣电影详情 | 接口：`/movie/<id>` | 只请求未抓过的；简介为空的 5 天后重试 | 简介、片长、各地上映日期、语言、又名 |
| Google 新闻 | RSS 搜索：`news.google.com/rss/search`（`hl=zh-CN`） | 3 类 × 4 个搜索词，每条返回数未确认 | 演唱会 / 发布会 / 定档 |
| Bing 新闻 | RSS 搜索：`bing.com/news/search?format=rss` | 同上，每条返回数未确认 | 补充；带摘要和配图，链接从 `url=` 参数还原原文 |
| `events.json` | 人工维护（可选） | 不限 | 重要发布会，页面标「人工确认」 |

新闻搜索词（`NEWS_QUERIES`）：
- 演唱会 `concert`：演唱会 开票、演唱会 开售、巡回演唱会 官宣、演唱会 预售
- 发布会 `launch`：发布会 定档、新品发布会 官宣、发布会 将于、新品 发布会 时间
- 定档 `schedule`：电视剧 定档、综艺 定档、新剧 官宣定档、电影 定档

**增删来源**：
- 搜索词：改 `NEWS_QUERIES`；剧集榜和条数：改 `TV_LISTS`
- 发布会品牌白名单：`BRANDS`（关键词 → 显示名，如 `"iPhone": "苹果"`）；排除词：`LAUNCH_EXCLUDE`
- 演唱会城市识别：`CITIES`；演唱会排除词：`CONCERT_EXCLUDE`
- 新增一类来源：写抓取函数，在 `main()` 的线程池里 `ex.submit(run, "名称", fn)`，并加进 `res` / `old` 字典

**限制**：
- 大麦有滑块验证，抓不了，演唱会信息来自新闻标题，会有漏抓和误判；标题里提取不到日期的不进日历，只放在「近期开票动态」
- 豆瓣图片有防盗链（非豆瓣 Referer 返回 418 / 403），海报由爬虫下载到 `covers/`

---

## 数据处理规则

- **电影上映日期**：豆瓣只给「10.05」这种月日，`guess_year()` 取离今天最近的那一年
- **剧集开播日期** `tv_detail()`：`pubdate` 里优先取带「中国大陆」的一条；只有年月时补成 1 日并标 `pub_precise: false`（前端只把精确日期放进日历）
- **新闻时间窗**：只要最近 `NEWS_DAYS = 21` 天发布的报道
- **新闻分类 `classify(kind, item, pub)`**：
  - 演唱会：标题必须含「演唱会」或「巡演」，且不命中 `CONCERT_EXCLUDE`（攻略、退票、酒店、黄牛、周边、座位表…）；日期紧挨「开票 / 开售 / 预售 / 开抢 / 售票」的算开票日（`sale: true`），否则多半是演出日；`city_of()` 取标题里最早出现的城市；分组 key = `日期|城市|标题前 8 字`
  - 发布会：标题必须含「发布」、不命中 `LAUNCH_EXCLUDE`（人寿、保险、银行、家居、地产、医药、新闻发布会、论坛、博览会…），且命中 `BRANDS` 白名单（英文按词边界）；分组 key = `品牌|日期`
  - 定档：标题必须含《剧名》和「定档」；按关键词判电影（电影 / 上映 / 院线）、综艺（综艺 / 真人秀 / 节目）、剧集；识别平台（腾讯视频、爱奇艺、优酷、芒果TV、各卫视、B站、Netflix…）；分组 key = `剧名|日期`
- **标题提日期 `extract_date(title, pub, near)`**：
  - 支持「2026 年 10 月 28 日（周三）晚上 8 点」这类写法（`DATE_RE`），下午 / 晚上的小时 +12
  - 相对日期 `REL_RE`：今天 / 明天 / 后天 / 今晚（「晚」默认 20:00），以发稿日为基准
  - 都没有时再看星期 `WEEK_RE`：「周四」「下周三」按发稿日往后推
  - 一个标题有多个日期时，取离关键词（开票、发布会、定档…）最近的那个
- **合并分组 `news()`**：上一份同类新闻按 key 读回来再追加本次报道；同组内按 URL 或标题去重；每组只留最新 5 篇报道；有日期的事件过去 `KEEP_PAST = 3` 天移除，没日期的最新报道超过 10 天移除；按日期排序（无日期排最后）
- **发布会同场合并 `merge_launch()`**：同品牌、日期相差 ≤2 天视为同一场；按报道数投票取日期，其余日期记进 `alt_dates`（前端注明「其他报道日期」）；合并后每场最多 6 篇报道
- **人工发布会 `manual_events()`**：`events.json` 里日期未过去 3 天的条目；前端与新闻提取的合并，同品牌同日以人工为准
- **海报 `save_covers()`**：把豆瓣 `m_ratio_poster` 换成小图 `s_ratio_poster` 再下载（6 线程，校验 JPEG / PNG 魔数），存 `covers/<豆瓣id>.jpg` 并写 `cover_local`；不在当前榜单的海报删除；下载失败的不给本地路径，页面显示占位图
- **缓存**：`tv_cache` / `movie_cache` 只保留本次仍在榜上的条目

---

## 数据结构

**data.json** 顶层（紧凑 JSON，无缩进）：

```
{
  "updated": "2026-10-22T12:49:36+08:00",       北京时间，每次运行都变
  "today":   "2026-10-22",
  "sources": { "showing" | "soon" | "tv" | "concert" | "launch" | "schedule": { "ok", "stale", "error", "count" } },
  "movies":  { "showing": [电影, …], "soon": [电影, …] },
  "tv":      [剧集综艺, …],
  "news":    { "concert": [演唱会, …], "launch": [发布会, …], "schedule": [定档, …] },
  "manual":  [events.json 里未过期的发布会, …],
  "tv_cache":    { "<豆瓣id>": { pubdate, pub_precise, platforms, episodes, is_show, intro, fetched } },
  "movie_cache": { "<豆瓣id>": { intro, durations, pubdates, languages, aka, fetched } }
}
```

电影：

```
{
  "id": "37068446", "title": "…", "original_title": "…", "rating": 7.3, "rating_count": 187788,
  "release": "2026-10-05", "year": "2026", "wish": 0, "cover": "豆瓣原图", "cover_local": "covers/37068446.jpg",
  "url": "https://movie.douban.com/subject/<id>/", "desc": "",
  "region": "…", "genres": "…", "directors": "…", "actors": "…",
  "intro": "…", "durations": [], "pubdates": [], "languages": [], "aka": []        来自详情缓存
}
```

剧集综艺：

```
{
  "id": "…", "title": "…", "kind": "tv | show", "rating": null, "rating_count": 0, "progress": "更新至13集",
  "year": "2026", "cover": "…", "cover_local": "…", "url": "…",
  "lists": ["tv_hot", "tv_domestic"], "rank": 1, "region": "…", "genres": "…", "directors": "…", "actors": "…",
  "pubdate": "2026-10-16", "pub_precise": true, "platforms": ["腾讯视频"], "episodes": 18, "intro": "…"
}
```

新闻事件（三类共用 `date` / `time` / `key` / `title` / `articles`）：

```
{
  "date": "2026-10-20 或 null", "time": "HH:MM 或空", "key": "分组键", "title": "最新一篇报道的标题",
  "articles": [{ "title", "url", "source", "published", "desc"（Bing）, "img"（Bing） }],
  concert 附加：  "city", "sale", "announce"
  launch 附加：   "brand", "alt_dates"（日期有分歧时）
  schedule 附加： "name", "cat": "movie | show | tv", "platform"
}
```

**events.json**（人工维护）：

```
{
  "note": "说明",
  "events": [{ "date": "2026-10-28", "time": "01:00", "brand": "苹果", "title": "…", "url": "…" }]
}
```

没有单独的历史文件；新闻分组在 `data.json` 里滚动累积，完整快照在 git 提交记录里。

---

## 前端

**kit 详情抽屉 / 列表页**：点任意条目，电脑上从右侧滑出详情抽屉，手机上从底部升起；地址同步成 `#/item/<类型>/<id>`，列表页是 `#/list/<key>`。地址可以直接分享，打开分享链接会直接弹出详情；条目已下榜 / 过期时弹出「这条内容已不在当前数据里」的提示。

列表页是新开的一层：从右侧滑入盖在首页上，返回时滑走；首页一直在底下不动，滚动位置不变。在列表里点开的详情盖在这一层之上；直接打开列表链接时不播进场动画；安卓手机可从左边缘右滑返回（iOS 用系统自带手势）。

| 类型 | 地址 | 内容 |
|------|------|------|
| 电影 | `#/item/movie/<豆瓣id>` | 评分 / 想看、简介、片长、上映日期、新闻定档信息、同类型电影 |
| 剧集综艺 | `#/item/tv/<豆瓣id>` | 开播日期、平台、更新进度、评分、所在榜单、近期开播的同类 |
| 定档 | `#/item/sched/<s + key 的短哈希>` | 定档日期、类型、平台、对应豆瓣条目、相关报道、其它定档 |
| 演唱会 | `#/item/concert/<c + key 的短哈希>` | 日期 / 开票时间 / 城市、倒计时、全部报道、同城其它演出 |
| 发布会 | `#/item/launch/<e + 品牌、日期、标题的短哈希>` | 品牌、日期倒计时、其他报道日期、相关报道、同品牌与其它品牌发布会；人工条目标「人工确认」 |

注意：`sched` / `concert` 用爬虫给的 `key`、`launch` 用品牌 + 日期 + 标题生成 FNV-1a 短哈希作 id，数据每天更新、顺序变化后分享链接仍指向同一条；以前的纯数字链接按数组下标兼容打开，条目已不在数据里时弹「已不在当前数据里」提示。

| 列表 key | 参数 |
|----------|------|
| `movie` 电影 | `tab`：showing（默认）/ soon；`sort`：hot / rating / date |
| `tv` 剧集 · 综艺 | `kind`：all / tv / show；`range`：hot / new（近 14 天开播） |
| `concert` 演唱会 | `city`：城市；`sort`：date / new |
| `day/<YYYY-MM-DD>` 某天的全部事件 | 顶部切换昨天到未来 5 天 |

**本项目特有**：
- 概览页：本周新上映、新片最高分、下一场发布会、最近开票四个指标，昨天到未来 5 天的日历
- 「新片」= 上映 7 天内；「近期开播」= 开播 14 天内且日期精确
- 倒计时每分钟在浏览器里重算并重绘（`setInterval` 60 秒，只重绘不重读数据）；数据靠刷新页面或右上角 ↻ 重读
- 视图、电影 / 剧集页签与排序、城市、主题存 `localStorage`（前缀 `wn:`）
- 右上角 ⚡ 跳转 GitHub Actions 手动触发抓取；`⌘K` 搜索

---

## 本地运行

```
python3 scraper.py                 # 抓取一次，生成 data.json 和 covers/
python3 -m http.server 8000        # 浏览器打开 http://localhost:8000
```

- 依赖：只用 Python 标准库（workflow 用 Python 3.12），无需 `pip install`
- 环境变量：无
- 直接双击 `index.html`（file://）读不到 `data.json`，必须通过 HTTP 服务打开

---

## 自动更新机制

| 触发方式 | 时机 |
|---------|------|
| GitHub Actions 定时任务 | `cron: '0 0 * * *'` = 每天 00:00 UTC = **北京时间 08:00**（高峰期可能延迟） |
| 修改后 push | push 到 main 且改动了 `scraper.py`、`events.json` 或 `.github/workflows/scrape.yml` 时，约 1-2 分钟后触发（所以人工补发布会 push 后会自动重抓） |
| GitHub Actions 手动 dispatch | 按需触发（页面右上角 ⚡ 或 Actions → Weekly New Scraper → Run workflow） |

- **心跳**：没有单独的 `last_*.txt`；`data.json` 的 `updated` 每次运行都变，所以每次运行都会产生 `data: update …` 提交，仓库保持活跃
- **60 天停用**：仓库 60 天没有提交时 GitHub 会自动停用定时任务（需在 Actions 页面重新启用）；正常每天一次提交不会被停用，一旦被停用就不再有新提交，需手动启用
