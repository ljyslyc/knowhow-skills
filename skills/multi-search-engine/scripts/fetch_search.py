#!/usr/bin/env python3
"""Portable, dependency-free search fetcher for the multi-search-engine skill.

Purpose
-------
Many agent hosts expose a URL-fetch tool, but some do not -- a bare OpenClaw
gateway without the browser plugin, a locked-down sandbox, a plain shell. This
script is the fallback so the skill still works: it only needs Python 3.8+ and
outbound HTTP, and it implements the same contract the skill documents
(rate limiting, in-memory cookies, cookie refresh + single retry on 403/429).

Usage
-----
    python3 fetch_search.py engines [--category C]
    python3 fetch_search.py presets
    python3 fetch_search.py url "<search-url>" [--max-chars N] [--links] [--json]
    python3 fetch_search.py multi --query "<text>" [--engines a,b,c]
                                  [--category academic,tech] [--preset deep-research]
                                  [--delay 1.5] [--max-chars N] [--links] [--json]

Selection precedence for `multi`: --engines > --preset > --category > default.

Options
-------
    --timeout SEC   Per-request timeout, default 20
    --delay SEC     Sleep between requests, default 1.5 (crawling etiquette)

Exit codes
----------
    0  every request succeeded
    1  usage error
    2  every request failed
    3  partial failure (at least one succeeded, at least one failed)

Cookies are held in memory for the lifetime of the process only. Nothing is
written to disk.
"""

from __future__ import annotations

import argparse
import html as html_mod
import http.cookiejar
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = SKILL_ROOT / "config.json"

BROWSER_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

BASE_HEADERS = {
    "User-Agent": BROWSER_UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Cache-Control": "no-cache",
}

# Built-in fallback registry. Used when config.json is absent or unreadable, so
# the script keeps working even if the skill directory is partially copied.
# format: slug -> (url, region, category)
ENGINES_FALLBACK = {
    "baidu": ("https://www.baidu.com/s?wd={keyword}", "cn", "cn_general"),
    "bing_cn": ("https://cn.bing.com/search?q={keyword}&ensearch=0", "cn", "cn_general"),
    "bing_int": ("https://cn.bing.com/search?q={keyword}&ensearch=1", "cn", "cn_general"),
    "360": ("https://www.so.com/s?q={keyword}", "cn", "cn_general"),
    "sogou": ("https://sogou.com/web?query={keyword}", "cn", "cn_general"),
    "wechat": ("https://wx.sogou.com/weixin?type=2&query={keyword}", "cn", "cn_community"),
    "shenma": ("https://m.sm.cn/s?q={keyword}", "cn", "cn_general"),
    "toutiao": ("https://so.toutiao.com/search?keyword={keyword}", "cn", "cn_general"),
    "google": ("https://www.google.com/search?q={keyword}", "global", "global_general"),
    "google_hk": ("https://www.google.com.hk/search?q={keyword}", "global", "global_general"),
    "duckduckgo": ("https://duckduckgo.com/html/?q={keyword}", "global", "global_general"),
    "yahoo": ("https://search.yahoo.com/search?p={keyword}", "global", "global_general"),
    "startpage": ("https://www.startpage.com/sp/search?query={keyword}", "global", "global_general"),
    "brave": ("https://search.brave.com/search?q={keyword}", "global", "global_general"),
    "ecosia": ("https://www.ecosia.org/search?q={keyword}", "global", "global_general"),
    "qwant": ("https://www.qwant.com/?q={keyword}", "global", "global_general"),
    "wolframalpha": ("https://www.wolframalpha.com/input?i={keyword}", "global", "special"),
    "google_scholar": ("https://scholar.google.com/scholar?q={keyword}", "global", "academic"),
    "arxiv": ("https://arxiv.org/search/?query={keyword}&searchtype=all", "global", "academic"),
    "pubmed": ("https://pubmed.ncbi.nlm.nih.gov/?term={keyword}", "global", "academic"),
    "github": ("https://github.com/search?q={keyword}&type=repositories", "global", "tech"),
    "zhihu": ("https://www.zhihu.com/search?type=content&q={keyword}", "cn", "cn_community"),
}

# Named multi-engine presets, tuned per research scenario. Slugs must exist in
# the registry; unknown slugs are dropped with a warning rather than failing.
PRESETS = {
    "quick": ["baidu", "bing_cn", "duckduckgo"],
    "deep-research": ["bing_cn", "google", "duckduckgo", "google_scholar", "wikipedia_en", "brave"],
    "academic": ["google_scholar", "arxiv", "semantic_scholar", "pubmed", "cnki", "wikipedia_en"],
    "tech": ["github", "stack_overflow", "hacker_news", "dev_community", "juejin", "csdn"],
    "chinese": ["baidu", "bing_cn", "sogou", "zhihu", "wechat", "weibo", "bilibili", "xiaohongshu"],
    "news": ["google_news", "bing_news", "toutiao", "baidu", "bing_cn"],
    "competitor": ["bing_cn", "google", "baidu", "cnki", "google_scholar", "wechat", "zhihu", "github"],
    "fact-check": ["wikipedia_en", "wikipedia_zh", "wolframalpha", "google", "bing_cn", "duckduckgo"],
}

_SCRIPT_RE = re.compile(r"<(script|style|noscript)\b[^>]*>.*?</\1>", re.I | re.S)
_COMMENT_RE = re.compile(r"<!--.*?-->", re.S)
_BREAK_RE = re.compile(r"</?(?:br|p|div|li|tr|h[1-6]|section|article)\b[^>]*>", re.I)
_TAG_RE = re.compile(r"<[^>]+>")
_BLANK_RE = re.compile(r"[ \t\r\f\v]+")
_MULTINL_RE = re.compile(r"\n{3,}")
_LINK_RE = re.compile(
    r'<a\b[^>]*href=["\'](?P<href>https?://[^"\']+)["\'][^>]*>(?P<text>.*?)</a>',
    re.I | re.S,
)


def load_engines():
    """Return {slug: {"url": template, "region": region, "category": category}}."""
    engines = {}
    try:
        raw = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raw = None

    for item in (raw or {}).get("engines", []) if isinstance(raw, dict) else []:
        name = str(item.get("name", "")).strip()
        url = str(item.get("url", "")).strip()
        if not name or "{keyword}" not in url:
            continue
        engines[_slugify(name)] = {
            "url": url,
            "region": str(item.get("region", "")).strip() or "unknown",
            "category": str(item.get("category", "")).strip() or "uncategorized",
        }

    if engines:
        return engines

    return {
        slug: {"url": url, "region": region, "category": category}
        for slug, (url, region, category) in ENGINES_FALLBACK.items()
    }


def categories_of(engines):
    """Return sorted list of distinct categories."""
    return sorted({meta["category"] for meta in engines.values()})


def resolve_selection(engines, args):
    """Pick engine slugs by precedence: --engines > --preset > --category > default.

    Returns (slugs, warnings). Unknown slugs/categories are dropped, not fatal.
    """
    warnings = []

    def match_category(name):
        name = name.strip()
        if not name:
            return []
        if name in categories_of(engines):
            return [s for s, m in engines.items() if m["category"] == name]
        # allow shorthand: "academic" also matches region shortcuts
        if name in ("cn", "global"):
            return [s for s, m in engines.items() if m["region"] == name]
        warnings.append("unknown category: %s" % name)
        return []

    if args.engines:
        wanted, unknown = [], []
        for slug in (s.strip() for s in args.engines.split(",")):
            if not slug:
                continue
            (wanted if slug in engines else unknown).append(slug)
        if unknown:
            warnings.append("unknown engine(s): %s" % ", ".join(unknown))
        return wanted, warnings

    if getattr(args, "preset", None):
        preset = PRESETS.get(args.preset)
        if preset is None:
            warnings.append("unknown preset: %s" % args.preset)
            return [], warnings
        wanted = [s for s in preset if s in engines]
        missing = [s for s in preset if s not in engines]
        if missing:
            warnings.append("preset engines not in registry: %s" % ", ".join(missing))
        return wanted, warnings

    if getattr(args, "category", None):
        wanted = []
        for name in args.category.split(","):
            wanted.extend(match_category(name))
        # de-dup, keep registry order
        return [s for s in sorted(wanted, key=lambda x: (engines[x]["category"], x))], warnings

    return ["baidu", "bing_cn", "duckduckgo"], warnings


def _slugify(name):
    slug = name.strip().lower().replace(" ", "_").replace("-", "_")
    return re.sub(r"[^a-z0-9_]", "", slug)


def build_url(engine, query):
    return engine["url"].replace("{keyword}", urllib.parse.quote_plus(query))


def make_opener():
    """An opener whose cookie jar lives only in this process."""
    jar = http.cookiejar.CookieJar()
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))


def http_get(opener, url, timeout):
    """Return (status, body_text, error_message)."""
    req = urllib.request.Request(url, headers=dict(BASE_HEADERS))
    try:
        with opener.open(req, timeout=timeout) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            body = resp.read().decode(charset, errors="replace")
            return resp.status, body, None
    except urllib.error.HTTPError as exc:
        return exc.code, "", "HTTP %s" % exc.code
    except urllib.error.URLError as exc:
        return 0, "", "URLError: %s" % exc.reason
    except OSError as exc:
        return 0, "", "OSError: %s" % exc


def homepage_of(url):
    parts = urllib.parse.urlsplit(url)
    return "%s://%s/" % (parts.scheme, parts.netloc)


def fetch_with_retry(opener, url, timeout, delay):
    """Fetch, refreshing cookies once on 403/429, mirroring the skill contract."""
    status, body, err = http_get(opener, url, timeout)
    if status in (403, 429):
        time.sleep(max(delay, 2.0))
        http_get(opener, homepage_of(url), timeout)  # seed fresh session cookies
        time.sleep(max(delay, 1.0))
        status, body, err = http_get(opener, url, timeout)
    return status, body, err


def html_to_text(markup):
    text = _SCRIPT_RE.sub(" ", markup)
    text = _COMMENT_RE.sub(" ", text)
    text = _BREAK_RE.sub("\n", text)
    text = _TAG_RE.sub(" ", text)
    text = html_mod.unescape(text)
    text = _BLANK_RE.sub(" ", text)
    text = "\n".join(line.strip() for line in text.splitlines())
    return _MULTINL_RE.sub("\n\n", text).strip()


def extract_links(markup, limit=40):
    seen, links = set(), []
    for match in _LINK_RE.finditer(markup):
        href = match.group("href")
        if href in seen:
            continue
        seen.add(href)
        label = html_mod.unescape(_TAG_RE.sub(" ", match.group("text")))
        label = _BLANK_RE.sub(" ", label).strip()
        links.append({"text": label[:160], "href": href})
        if len(links) >= limit:
            break
    return links


def render(record, want_json, want_links, max_chars):
    if want_json:
        payload = dict(record)
        payload["text"] = payload["text"][:max_chars]
        if not want_links:
            payload.pop("links", None)
        else:
            payload["links"] = payload["links"][:40]
        return json.dumps(payload, ensure_ascii=False, indent=2)

    lines = []
    header = "[%s] %s" % (record["engine"], record["url"])
    lines.append(header)
    lines.append("-" * min(len(header), 78))
    if not record["ok"]:
        lines.append("FAILED: %s" % record["error"])
    else:
        lines.append("status=%s chars=%s" % (record["status"], record["chars"]))
        lines.append("")
        lines.append(record["text"][:max_chars])
        if want_links and record.get("links"):
            lines.append("")
            lines.append("Links:")
            for link in record["links"][:20]:
                lines.append("  - %s -> %s" % (link["text"] or "(no text)", link["href"]))
    return "\n".join(lines)


def fetch_one(opener, url, engine_label, args):
    status, body, err = fetch_with_retry(opener, url, args.timeout, args.delay)
    ok = status == 200 and bool(body)
    text = html_to_text(body) if ok else ""
    record = {
        "engine": engine_label,
        "url": url,
        "status": status,
        "ok": ok,
        "chars": len(text),
        "error": None if ok else (err or "empty response"),
        "text": text,
        "links": extract_links(body) if ok else [],
    }
    return record


def cmd_engines(args):
    engines = load_engines()
    if getattr(args, "category", None):
        keep = {c.strip() for c in args.category.split(",") if c.strip()}
        engines = {s: m for s, m in engines.items() if m["category"] in keep or m["region"] in keep}
    if args.json:
        print(json.dumps(engines, ensure_ascii=False, indent=2))
        return 0
    for slug in sorted(engines, key=lambda s: (engines[s]["category"], engines[s]["region"], s)):
        meta = engines[slug]
        print("%-16s %-16s %-8s %s" % (slug, meta["category"], meta["region"], meta["url"]))
    print("\ntotal: %d" % len(engines))
    return 0


def cmd_presets(args):
    engines = load_engines()
    payload = {}
    for name, slugs in sorted(PRESETS.items()):
        valid = [s for s in slugs if s in engines]
        payload[name] = {"engines": valid, "count": len(valid)}
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0
    for name, info in payload.items():
        print("%-16s (%d)  %s" % (name, info["count"], ", ".join(info["engines"])))
    print("\ncategories: %s" % ", ".join(categories_of(engines)))
    return 0


def cmd_url(args):
    opener = make_opener()
    record = fetch_one(opener, args.target, "direct", args)
    print(render(record, args.json, args.links, args.max_chars))
    return 0 if record["ok"] else 2


def cmd_multi(args):
    engines = load_engines()
    wanted, warnings = resolve_selection(engines, args)
    for w in warnings:
        print("[WARN] %s" % w, file=sys.stderr)

    if not wanted:
        print("no valid engines selected; run `fetch_search.py engines` to list slugs.", file=sys.stderr)
        return 1

    opener = make_opener()
    records = []
    for index, slug in enumerate(wanted):
        if index:
            time.sleep(args.delay)
        url = build_url(engines[slug], args.query)
        records.append(fetch_one(opener, url, slug, args))

    if args.json:
        print(json.dumps(
            [dict(r, text=r["text"][:args.max_chars],
                  links=r["links"][:40] if args.links else r["links"])
             for r in records],
            ensure_ascii=False, indent=2,
        ))
    else:
        print("query: %s" % args.query)
        print("engines: %s\n" % ", ".join(wanted))
        for record in records:
            print(render(record, False, args.links, args.max_chars))
            print()

    ok_count = sum(1 for r in records if r["ok"])
    if ok_count == 0:
        return 2
    if ok_count < len(records):
        return 3
    return 0


def build_parser():
    parser = argparse.ArgumentParser(
        prog="fetch_search.py",
        description="Portable search fetcher for the multi-search-engine skill.",
    )
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--timeout", type=float, default=20.0)
    common.add_argument("--delay", type=float, default=1.5)
    common.add_argument("--max-chars", type=int, default=12000)
    common.add_argument("--links", action="store_true", help="also extract result links")
    common.add_argument("--json", action="store_true", help="emit JSON instead of text")

    sub = parser.add_subparsers(dest="command", required=True)

    p_engines = sub.add_parser("engines", help="list configured engines")
    p_engines.add_argument("--category", default="", help="filter by category (comma-separated)")
    p_engines.add_argument("--json", action="store_true")
    p_engines.set_defaults(func=cmd_engines, timeout=20.0, delay=1.5,
                           max_chars=12000, links=False, engines="")

    p_presets = sub.add_parser("presets", help="list named multi-engine presets")
    p_presets.add_argument("--json", action="store_true")
    p_presets.set_defaults(func=cmd_presets, timeout=20.0, delay=1.5,
                           max_chars=12000, links=False, engines="", category="")

    p_url = sub.add_parser("url", help="fetch a single search URL", parents=[common])
    p_url.add_argument("target")
    p_url.set_defaults(func=cmd_url)

    p_multi = sub.add_parser("multi", help="fan out over several engines", parents=[common])
    p_multi.add_argument("--query", required=True)
    p_multi.add_argument("--engines", default="", help="comma-separated slugs (highest precedence)")
    p_multi.add_argument("--preset", default="", help="named preset, e.g. deep-research / academic / competitor")
    p_multi.add_argument("--category", default="", help="category slugs, e.g. academic,tech")
    p_multi.set_defaults(func=cmd_multi)

    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
