# Changelog

## v4.1.0 (2026-10-14)

### Layered research pipeline (new)

- Added `scripts/layered_search.py`, a three-round research pipeline over the existing
  fetch layer. One round of search cannot be complete, because you cannot know the right
  keyword until you have seen what round one returned.
  - **L1 PLAN** (`plan`): expands a topic into keyword sets grouped by 9 investigation
    directions (product / patent / market / capacity / strategy / timeline / competitor /
    community / risk). Active directions come from a **profile** auto-detected from the
    topic text (company / industry / tech / person / concept / product), or set explicitly
    with `--profile`. `--comparison` mixes in competitive-analysis keywords.
  - **L2 FANOUT** (`fanout`, `run`): runs each keyword set across several engines
    concurrently and stores fetched page text.
  - **L3 DRILL** (`leads`, `drill`): extracts named-entity **leads** (company names, patent
    numbers, people) from L2 text, ranks them, and generates targeted follow-up queries per
    lead across 8 drill intents.
- Lead extraction is deterministic (regex + frequency) so every lead is auditable.
  Filters reject descriptors that masquerade as names (`上市公司`, `海外龙头公司`,
  `蛋氨酸公司`, `一些新兴的生物科技公司`) and web/CSS tokens. Ranking prefers
  cross-engine agreement, then match-type confidence.
- Curated, growable filter lists (`LEAD_CATEGORY_STEMS`, `LEAD_GENERIC_QUALIFIERS`):
  when a run surfaces a category word posing as a company, add it and pin a test.
- Added `scripts/test_layered_search.py` — **71 deterministic checks, no network or files
  required**. Run it after touching any filter list.

### Description rewrite

- Skill `description` rewritten to be usable by an agent that has never seen this skill:
  what it does, when to trigger, when *not* to, how it works, what you must supply, what
  you get back.

## v4.0.0 (2026-10-12)

### Scale and structure

- Engine registry expanded from **17 to 39 engines**, grouped into **7 categories**:
  `cn_general` (8), `global_general` (10), `academic` (7), `tech` (4),
  `cn_community` (7), `news` (2), `special` (1).
- New academic engines: Google Scholar, arXiv, Semantic Scholar, PubMed, CNKI,
  Wikipedia (ZH/EN).
- New tech engines: GitHub, Stack Overflow, Hacker News, DEV Community.
- New Chinese community engines: Zhihu, Weibo, Bilibili, Juejin, CSDN, Xiaohongshu.
  (`WeChat` moved from `cn_general` to `cn_community`.)
- New news engines: Google News, Bing News.
- New general engines: Quark (CN), Mojeek and Marginalia (global, independent indexes).

### Selection UX

- Added **8 named presets**: `quick`, `deep-research`, `academic`, `tech`, `chinese`,
  `news`, `competitor`, `fact-check`. New `presets` subcommand lists them.
- `multi` now accepts `--preset` and `--category` in addition to `--engines`.
  Precedence: `--engines` > `--preset` > `--category` > default.
- `engines` subcommand accepts `--category` to filter the registry.
- Unknown engine slugs and categories now produce a warning and are dropped
  individually instead of failing the whole run.

### Internals

- `config.json` engine entries gained a `category` field; the file now also declares
  a `categories` map with human-readable Chinese labels.
- `load_engines()` returns `category`; added `categories_of()` and `resolve_selection()`.
- Fallback registry (`ENGINES_FALLBACK`) updated to the 3-tuple form and extended.

## v3.0.0 (2026-09-15)

### Portability

- Abstracted the fetch step into a tool-neutral "fetch capability" layer.
  The workflow no longer hardcodes one host's tool name; `SKILL.md` now carries a
  per-host mapping table (WorkBuddy `web_fetch`, Claude `WebFetch`, OpenClaw
  `browser` or `exec` + `curl`, generic shell `curl`/`wget`).
- Added `scripts/fetch_search.py`: stdlib-only, dependency-free fetcher with
  single-URL fetch, multi-engine fan-out, rate limiting, in-memory cookies, and
  automatic cookie refresh + one retry on HTTP 403/429.
- Frontmatter normalised to the portable Agent Skills spec so the same directory
  installs on OpenClaw (`~/.openclaw/workspace/skills/`, ClawHub) and other hosts:
  `name`, `description`, `license`, `version`, `compatibility`, `allowed-tools`,
  plus an `metadata.openclaw` block for OpenClaw-specific UI.
- Added `LICENSE` (MIT) so the package is publishable as-is.

### Documentation

- Reference guides no longer embed a host-specific tool call; examples read
  `fetch <URL>` and are realised per host in `SKILL.md`.

### Consistency fixes

- Engine registry reconciled to a single canonical list of 17 (8 China + 9 global).
  Previously `SKILL.md` documented 16 engines while `config.json` listed 17 with a
  different China set. `Shenma` is now consistently present; the `Jisilu` entry was
  dropped because it is a finance community rather than a search engine and the
  endpoint does not behave as a keyword search.
- Removed the duplicated `CHANNELLOG.md` (misspelling of `CHANGELOG.md`).
- Version aligned across `SKILL.md`, `config.json`, `metadata.json`, `CHANGELOG.md`.

## v2.1.3

- Marketplace release metadata.

## v2.0.1 (2026-02-06)

- Simplified documentation.
- Removed gov-related content.
- Optimized for ClawHub publishing.

## v2.0.0 (2026-02-06)

- Added 9 international search engines.
- Enhanced advanced search capabilities.
- Added DuckDuckGo Bangs support.
- Added WolframAlpha knowledge queries.

## v1.0.0 (2026-02-04)

- Initial release with 8 domestic search engines.
