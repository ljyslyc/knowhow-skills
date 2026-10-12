# Changelog

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
