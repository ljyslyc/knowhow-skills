---
name: multi-search-engine
description: Cross-engine web search over 39 engines in 7 categories (Chinese general, global general, academic, tech, Chinese community, news, special) with no API keys, plus 8 scenario presets. Use when one engine is not enough, or when research needs broad multi-source coverage.
license: MIT
version: 4.0.0
compatibility: Requires an HTTP fetch capability. Works with any agent-provided web-fetch tool, shell curl/wget, or python3 3.8+ via the bundled fallback script.
allowed-tools: web_fetch WebFetch fetch browser exec
description_zh: "集成 39 个搜索引擎（7 大类），无 API Key，内置 8 组场景预设，多源结果合并去重"
visibility: "public"
metadata: { "author": "ljy", "version": "4.0.0", "openclaw": { "emoji": "🔎" } }
agent_created: true
---

# Multi Search Engine

Cross-engine web search with no API keys. A query becomes a plain search-engine URL,
and that URL is fetched with whatever HTTP capability the host agent has.

This skill is deliberately tool-neutral. It must not assume any single fetch tool name.

## Step 0 — Resolve the fetch capability (always do this first)

Pick the first option the host actually provides:

| Host agent | Fetch mechanism |
| --- | --- |
| WorkBuddy | `web_fetch` tool |
| Claude Code / Claude agents | `WebFetch` tool |
| OpenClaw | the `browser` tool when the browser plugin is enabled; otherwise `exec` running `curl -sSL` |
| Cursor, Codex, Gemini CLI, other harnesses | the agent's own web/HTTP tool if one exists; otherwise shell `curl` or `wget` |
| No HTTP tool, but python3 available | bundled fallback: `python3 {baseDir}/scripts/fetch_search.py url "<URL>"` |
| No HTTP tool, no python3, but a shell | `curl -sSL -A "<browser UA>" "<URL>"` |

Throughout this document the verb **fetch** means "use whichever mechanism was selected above".
Never write one host's tool name into the workflow as if it were universal.

The bundled `scripts/fetch_search.py` is stdlib-only and covers the whole pipeline on its own:
single fetch, multi-engine fan-out, category/preset selection, rate limiting, cookie refresh on
403/429, HTML-to-text. Reach for it whenever the host has python3 but no native fetch tool.

## Workflow

1. **Classify the query.** Chinese query -> use China engines first. Non-Chinese query ->
   use global engines first. Mixed-language -> pair one China engine with one global engine.
2. **Select engines.** Either pick a **preset** (recommended, see below), pick by **category**,
   or name 2-4 engines explicitly. Do not fan out over all 39.
3. **Fetch with rate limiting.** Keep 1-2 s between requests. Work in batches of 3-4 engines,
   sequentially inside a batch. Send normal browser headers so requests are identifiable.
4. **Handle denial.** On HTTP 403 or 429, fetch that engine's homepage to refresh session
   cookies, wait 2 s, then retry once. If it fails again, drop that engine and report the gap.
5. **Aggregate.** De-duplicate by URL, group results by engine, rank the strongest sources
   first. State which engines responded and which did not — never present partial coverage
   as complete.

## Presets (start here)

`scripts/fetch_search.py presets` prints the live list. Presets beat hand-picking engines for
recurring research shapes:

| Preset | Engines | Use for |
| --- | --- | --- |
| `quick` | baidu, bing_cn, duckduckgo | fast sanity check, 3 engines |
| `deep-research` | bing_cn, google, duckduckgo, google_scholar, wikipedia_en, brave | general deep research |
| `academic` | google_scholar, arxiv, semantic_scholar, pubmed, cnki, wikipedia_en | papers, literature, standards |
| `tech` | github, stack_overflow, hacker_news, dev_community, juejin, csdn | code, libraries, engineering |
| `chinese` | baidu, bing_cn, sogou, zhihu, wechat, weibo, bilibili, xiaohongshu | Chinese-language sentiment and community |
| `news` | google_news, bing_news, toutiao, baidu, bing_cn | breaking news and recent events |
| `competitor` | bing_cn, google, baidu, cnki, google_scholar, wechat, zhihu, github | company / competitor intelligence |
| `fact-check` | wikipedia_en, wikipedia_zh, wolframalpha, google, bing_cn, duckduckgo | verify a claim or a number |

```bash
# Fan out with a preset
python3 {baseDir}/scripts/fetch_search.py multi --query "solid-state battery" --preset deep-research

# Fan out by category
python3 {baseDir}/scripts/fetch_search.py multi --query "mRNA vaccine" --category academic,news

# Or name engines explicitly (highest precedence)
python3 {baseDir}/scripts/fetch_search.py multi --query "react 19" --engines github,stack_overflow
```

Selection precedence: `--engines` > `--preset` > `--category` > default (baidu, bing_cn, duckduckgo).

## Cookie and privacy rules

- Cookies live in memory only. Never persist them to `config.json` or any other file.
- Acquire cookies on demand, only from the domain that denied the request.
- Clear them when the search session ends.
- No API keys, no accounts, no personal data leaves the machine.

## Engines (39, in 7 categories)

`config.json` in the skill root is the machine-readable source of truth for this list.
`scripts/fetch_search.py engines` prints it; add `--category <name>` to filter.

### 中文综合 · cn_general (8)

| Engine | Search URL |
| --- | --- |
| Baidu | `https://www.baidu.com/s?wd={keyword}` |
| Bing CN | `https://cn.bing.com/search?q={keyword}&ensearch=0` |
| Bing INT | `https://cn.bing.com/search?q={keyword}&ensearch=1` |
| 360 | `https://www.so.com/s?q={keyword}` |
| Sogou | `https://sogou.com/web?query={keyword}` |
| Shenma | `https://m.sm.cn/s?q={keyword}` |
| Toutiao | `https://so.toutiao.com/search?keyword={keyword}` |
| Quark | `https://quark.sm.cn/s?q={keyword}` |

### 国际综合 · global_general (10)

| Engine | Search URL |
| --- | --- |
| Google | `https://www.google.com/search?q={keyword}` |
| Google HK | `https://www.google.com.hk/search?q={keyword}` |
| DuckDuckGo | `https://duckduckgo.com/html/?q={keyword}` |
| Yahoo | `https://search.yahoo.com/search?p={keyword}` |
| Startpage | `https://www.startpage.com/sp/search?query={keyword}` |
| Brave | `https://search.brave.com/search?q={keyword}` |
| Ecosia | `https://www.ecosia.org/search?q={keyword}` |
| Qwant | `https://www.qwant.com/?q={keyword}` |
| Mojeek | `https://www.mojeek.com/search?q={keyword}` |
| Marginalia | `https://search.marginalia.nu/search?query={keyword}` |

### 学术与文献 · academic (7)

| Engine | Search URL |
| --- | --- |
| Google Scholar | `https://scholar.google.com/scholar?q={keyword}` |
| arXiv | `https://arxiv.org/search/?query={keyword}&searchtype=all` |
| Semantic Scholar | `https://www.semanticscholar.org/search?q={keyword}` |
| PubMed | `https://pubmed.ncbi.nlm.nih.gov/?term={keyword}` |
| CNKI | `https://kns.cnki.net/kns8s/defaultresult/index?kw={keyword}` |
| Wikipedia ZH | `https://zh.wikipedia.org/w/index.php?search={keyword}` |
| Wikipedia EN | `https://en.wikipedia.org/w/index.php?search={keyword}` |

### 技术社区 · tech (4)

| Engine | Search URL |
| --- | --- |
| GitHub | `https://github.com/search?q={keyword}&type=repositories` |
| Stack Overflow | `https://stackoverflow.com/search?q={keyword}` |
| Hacker News | `https://hn.algolia.com/?q={keyword}` |
| DEV Community | `https://dev.to/search?q={keyword}` |

### 中文社区 · cn_community (7)

| Engine | Search URL |
| --- | --- |
| Zhihu | `https://www.zhihu.com/search?type=content&q={keyword}` |
| WeChat | `https://wx.sogou.com/weixin?type=2&query={keyword}` |
| Weibo | `https://s.weibo.com/weibo?q={keyword}` |
| Bilibili | `https://search.bilibili.com/all?keyword={keyword}` |
| Juejin | `https://juejin.cn/search?query={keyword}` |
| CSDN | `https://so.csdn.net/so/search?q={keyword}` |
| Xiaohongshu | `https://www.xiaohongshu.com/search_result?keyword={keyword}` |

### 新闻资讯 · news (2)

| Engine | Search URL |
| --- | --- |
| Google News | `https://news.google.com/search?q={keyword}` |
| Bing News | `https://www.bing.com/news/search?q={keyword}` |

### 专用与事实 · special (1)

| Engine | Search URL |
| --- | --- |
| WolframAlpha | `https://www.wolframalpha.com/input?i={keyword}` |

## Tool-neutral examples

Written as `fetch <URL>` on purpose — substitute the mechanism chosen in Step 0.

```
fetch https://www.google.com/search?q=python+tutorial
fetch https://www.baidu.com/s?wd=Python教程
fetch https://scholar.google.com/scholar?q=solid+state+battery
fetch https://github.com/search?q=react&type=repositories
fetch https://www.google.com/search?q=ai+news&tbs=qdr:w
fetch https://www.wolframalpha.com/input?i=100+USD+to+CNY
```

Concrete realisation per host:

```bash
# WorkBuddy
web_fetch({"url": "https://www.google.com/search?q=python+tutorial"})

# OpenClaw / any shell
exec: curl -sSL -A "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36" \
  "https://www.google.com/search?q=python+tutorial"

# Any host with python3 (bundled fallback)
python3 {baseDir}/scripts/fetch_search.py url "https://www.google.com/search?q=python+tutorial"
```

## Bundled script

```bash
# List engines (optionally filter by category)
python3 {baseDir}/scripts/fetch_search.py engines
python3 {baseDir}/scripts/fetch_search.py engines --category academic

# List scenario presets
python3 {baseDir}/scripts/fetch_search.py presets

# One URL -> readable text (or --json)
python3 {baseDir}/scripts/fetch_search.py url "https://duckduckgo.com/html/?q=privacy" --max-chars 8000

# Fan out with a preset, rate-limited, cookie refresh on 403/429
python3 {baseDir}/scripts/fetch_search.py multi --query "AI 芯片 出口管制" --preset competitor --json

# Fan out by category
python3 {baseDir}/scripts/fetch_search.py multi --query "mRNA" --category academic --delay 1.5 --json
```

Exit codes: `0` success, `1` usage error, `2` every request failed, `3` partial failure.

## Advanced operators

| Operator | Example | Description |
| --- | --- | --- |
| `site:` | `site:github.com python` | Search within one site |
| `filetype:` | `filetype:pdf report` | Restrict to a file type |
| `""` | `"machine learning"` | Exact phrase |
| `-` | `python -snake` | Exclude a term |
| `OR` | `cat OR dog` | Either term |

## Time filters (Google)

| Parameter | Meaning |
| --- | --- |
| `tbs=qdr:h` | Past hour |
| `tbs=qdr:d` | Past day |
| `tbs=qdr:w` | Past week |
| `tbs=qdr:m` | Past month |
| `tbs=qdr:y` | Past year |

## Privacy engines

- **DuckDuckGo** — no tracking
- **Startpage** — Google results behind a privacy layer
- **Brave** — independent index
- **Qwant** — EU GDPR compliant
- **Mojeek** — fully independent crawler
- **Marginalia** — non-commercial / indie web index

## DuckDuckGo bangs

| Bang | Destination |
| --- | --- |
| `!g` | Google |
| `!gh` | GitHub |
| `!so` | Stack Overflow |
| `!w` | Wikipedia |
| `!yt` | YouTube |

## WolframAlpha queries

- Math: `integrate x^2 dx`
- Conversion: `100 USD to CNY`
- Stocks: `AAPL stock`
- Weather: `weather in Beijing`

## Documentation

- `references/advanced-search.md` — China engine guide
- `references/international-search.md` — global engine guide
- `CHANGELOG.md` — version history
- `config.json` — machine-readable engine registry

## Security and privacy notice

**Cookie handling**

- Purpose: maintain search session state only when access is denied (403/429).
- Storage: strictly in memory; never persisted to disk or config files.
- Acquisition: on demand, from the failing engine's own homepage only.
- Lifecycle: cleared when the search session completes.
- No pre-configuration: nothing is loaded from `config.json` or any external file at startup.
- No API keys: plain public search URLs, no authentication.

**Crawling ethics**

- Rate limit: 1-2 s between requests.
- Honour `robots.txt` and each engine's crawling policy.
- Users are responsible for complying with search-engine terms of service.
- Intended for legitimate search aggregation, not bulk scraping.

**Data handling**

- No personal data collected or transmitted.
- Runs locally; no third-party relay.
- Cookies are session-scoped and discarded.

## License

MIT
