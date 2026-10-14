#!/usr/bin/env python3
"""Layered (multi-round) search orchestration for the multi-search-engine skill.

Why this exists
---------------
A single fan-out sends one query to many engines. That is enough for a lookup,
but not for research: the questions that matter are not known until you see the
first results. Layered search mirrors how a human analyst works and how the
Adisseo competitor-analysis pipeline works:

    L1  PLAN   -- turn a topic into a set of *directional* queries
                  (product / patent / market / capacity / strategy / ...)
    L2  FANOUT -- run each direction across engines, collect raw text + links
    L3  DRILL  -- pull named leads (companies, products, people, patent numbers)
                  out of L2, then build targeted follow-up queries per lead

L1 and L3 are deterministic: same input -> same queries, so runs are comparable
and results are reproducible. The semantic judgement that cannot be made
mechanically -- "which direction matters most here", "is this lead worth
drilling" -- stays with the agent, which reads the emitted JSON and decides.

Usage
-----
    # L1 only: show the keyword plan
    python3 layered_search.py plan --topic "饲用酶制剂行业" --profile industry

    # L2 only: run the plan, save raw results
    python3 layered_search.py fanout --topic "..." --profile industry --out l2.json

    # L3 only: extract leads from an L2 file, show drill queries
    python3 layered_search.py leads  --from l2.json --top 20
    python3 layered_search.py drill  --from l2.json --intent patent,person

    # End to end
    python3 layered_search.py run --topic "..." --profile industry --depth 3

Exit codes
----------
    0  ok
    1  usage error
    2  every request failed
    3  partial failure

stdlib only. No API keys. Shares the fetch layer with fetch_search.py.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import fetch_search as fs  # noqa: E402  (sibling module, same directory)


# --------------------------------------------------------------------------
# L1 -- directional keyword plan
# --------------------------------------------------------------------------
#
# A "direction" is one angle of inquiry. Each carries several keyword
# templates; `{topic}` is substituted with the research subject. Templates are
# written to work across engines (no operator that only one engine honours).

DIRECTIONS = {
    "product": {
        "label": "产品与技术",
        "templates": [
            "{topic} 产品 型号 参数",
            "{topic} 技术路线 性能 指标",
            "{topic} 差异化 优势 特点",
        ],
    },
    "patent": {
        "label": "专利与标准",
        "templates": [
            "{topic} 专利 布局 申请",
            "{topic} 标准 起草单位 制定",
        ],
    },
    "market": {
        "label": "市场与价格",
        "templates": [
            "{topic} 市场份额 排名 格局",
            "{topic} 价格 报价 客户",
        ],
    },
    "capacity": {
        "label": "产能与供应链",
        "templates": [
            "{topic} 产能 扩产 基地",
            "{topic} 供应链 原料 一体化",
        ],
    },
    "strategy": {
        "label": "战略与资本",
        "templates": [
            "{topic} 战略 并购 投资",
            "{topic} 管理层 表态 规划",
        ],
    },
    "timeline": {
        "label": "历程与里程碑",
        "templates": [
            "{topic} 发展历程 重要节点",
            "{topic} 融资 里程碑 时间线",
        ],
    },
    "competitor": {
        "label": "竞品与替代",
        "templates": [
            "{topic} 竞品 对比 横向",
            "{topic} 替代方案 替代品 路线",
        ],
    },
    "community": {
        "label": "口碑与讨论",
        "templates": [
            "{topic} 评价 口碑 体验",
            "{topic} 讨论 争议 质疑",
        ],
    },
    "risk": {
        "label": "风险与合规",
        "templates": [
            "{topic} 风险 监管 合规",
            "{topic} 诉讼 处罚 争议",
        ],
    },
}

# Which directions each research profile turns on, in priority order.
PROFILES = {
    "company": ["product", "patent", "market", "capacity", "strategy", "timeline"],
    "industry": ["market", "capacity", "strategy", "competitor", "timeline", "risk"],
    "tech": ["product", "patent", "community", "competitor", "timeline"],
    "person": ["timeline", "strategy", "community", "risk"],
    "concept": ["timeline", "product", "community", "competitor"],
    "product": ["product", "market", "competitor", "community", "patent"],
}

# Keyword hints that pick a profile automatically when --profile is omitted.
PROFILE_HINTS = [
    ("industry", ["行业", "产业", "赛道", "市场格局", "产业链"]),
    ("company", ["公司", "集团", "股份", "有限公司", "企业"]),
    ("tech", ["技术", "算法", "框架", "模型", "协议", "架构"]),
    ("person", ["创始人", "CEO", "高管", "人物", "履历"]),
    ("product", ["产品", "型号", "设备", "制剂", "软件", "平台"]),
]

# Extra queries appended to every direction when the topic reads as a company
# comparison -- mirrors the Adisseo "mix in the comparison word" rule.
COMPARISON_SUFFIXES = ["对比 我方", "行业地位", "竞争威胁"]


def pick_profile(topic: str) -> tuple[str, str]:
    """Guess a research profile from the topic text. Returns (profile, reason)."""
    for profile, hints in PROFILE_HINTS:
        for hint in hints:
            if hint in topic:
                return profile, "matched hint %r" % hint
    return "company", "no hint matched; defaulted to company"


def build_plan(topic: str, profile: str, max_directions: int = 0,
               comparison: bool = False) -> dict:
    """L1: return the keyword plan as a JSON-able dict."""
    if profile not in PROFILES:
        raise ValueError("unknown profile: %s (choose from %s)"
                         % (profile, ", ".join(sorted(PROFILES))))

    keys = PROFILES[profile]
    if max_directions:
        keys = keys[:max_directions]

    directions = []
    for key in keys:
        spec = DIRECTIONS[key]
        queries = [t.format(topic=topic) for t in spec["templates"]]
        if comparison:
            queries.append("%s %s" % (topic, COMPARISON_SUFFIXES[0]))
        directions.append({
            "key": key,
            "label": spec["label"],
            "queries": queries,
            "purpose": _purpose_of(key),
        })

    return {
        "topic": topic,
        "profile": profile,
        "direction_count": len(directions),
        "query_count": sum(len(d["queries"]) for d in directions),
        "directions": directions,
    }


def _purpose_of(key: str) -> str:
    return {
        "product": "搞清产品是什么、技术路线与硬指标",
        "patent": "搞清专利布局与标准话语权",
        "market": "搞清市场地位与价格带",
        "capacity": "搞清产能、供给结构与成本基础",
        "strategy": "搞清战略意图与资本动作",
        "timeline": "搞清发展脉络与关键转折",
        "competitor": "搞清横向对手与替代路线",
        "community": "搞清真实口碑与争议点",
        "risk": "搞清监管、诉讼与合规风险",
    }.get(key, "")


# --------------------------------------------------------------------------
# L3 -- lead extraction and drill-query building
# --------------------------------------------------------------------------
#
# Leads are named entities worth a targeted follow-up search. Extraction is
# regex + frequency based, so it is deterministic and auditable: you can see
# exactly why a lead surfaced.

LEAD_PATTERNS = [
    ("patent", re.compile(r"\bCN\s?\d{6,}[A-Z]?\b", re.I)),
    ("company_cn", re.compile(
        r"[\u4e00-\u9fa5]{2,12}?(?:有限公司|股份有限公司|集团|研究院|研究所|大学|公司)")),
    ("company_brand", re.compile(r"\b[A-Z][A-Za-z0-9&.\-]{2,18}\b")),
    ("person_role", re.compile(
        r"[\u4e00-\u9fa5]{2,4}(?:教授|博士|院士|总经理|董事长|CEO|创始人|研究员)")),
]

# Leading tokens a greedy Chinese match commonly swallows before the real name
# ("拟批复河南普特威…", "据悉xx公司…"). Stripped only when enough surface remains.
#
# Deliberately conservative: single characters that legitimately begin company
# names are NOT listed. 中粮 / 华为 / 新华 / 大有 / 上海汽车 all start with a
# character a naive list would strip, so "中", "华", "新", "大", "上", "海"
# are excluded on purpose. Only unambiguously non-name material is stripped.
LEAD_LEADING_NOISE = [
    "拟批复", "批复", "据悉", "近日", "上述", "此外", "同时", "目前",
    "该公司", "本公司", "目标公司", "该", "本", "据", "经", "拟", "将",
    "的", "了", "被", "让", "使", "给", "把", "由", "是", "等",
    # Bare quantifiers. A company name never opens with these, but a snippet
    # often does ("一些新兴的生物科技公司…"), and the greedy Chinese match
    # swallows them. 新兴 (as in 新兴铸管) is NOT listed -- it can be a
    # legitimate name prefix; the 的-rule in _is_generic_cn catches the
    # "...的..." phrasing instead.
    "一些", "一堆", "许多", "若干", "各类", "各种", "诸多", "众多", "少数",
]

# Generic descriptor words that end in 公司/集团/大学 but name no one.
LEAD_GENERIC_BLOCK = [
    "上市公司", "有限公司", "股份公司", "总公司", "分公司", "子公司", "母公司",
    "该公司", "本公司", "你公司", "某公司", "各公司", "这些公司", "那些公司",
    "相关公司", "多家公司", "两家公司", "三家公司", "三大公司", "几家公司",
    "同类公司", "竞争公司", "目标公司", "一家公司", "国际公司", "海外公司",
    "集团", "大集团", "该集团", "某集团", "各大集团",
    "大学", "该大学", "某大学", "各大学", "研究院", "研究所",
]

# Stems that mark a match as a descriptor rather than a name. Checked against
# the part before the 公司/集团/… suffix.
LEAD_GENERIC_STEMS = [
    "上市", "龙头", "知名", "大型", "中小", "国内", "国际", "海外", "全球",
    "三大", "四大", "多家", "相关", "同类", "竞争", "目标", "上述", "这些",
    "那些", "一家", "多家", "几家", "众多", "各大", "所有", "全部", "部分",
    "本地", "当地", "各省", "各地", "中国", "美国", "日本", "欧洲",
]

# Quantifier / judgement words that make a stem a descriptor *wherever* they
# appear. Exact matching in LEAD_GENERIC_STEMS misses composites such as
# "中国三大酶制剂"(三大) or "知名企业"(知名). Geography prefixes are checked
# separately (see LEAD_GENERIC_PREFIXES) so a real name like 中国农业大学,
# whose stem starts with 中国, is not lost.
LEAD_GENERIC_QUALIFIERS = [
    "三大", "四大", "五大", "多家", "几家", "数家", "众多", "诸多",
    "龙头", "上市", "知名", "著名", "领先", "主要", "主流", "相关",
    "同类", "竞争", "上述", "这些", "那些", "各大", "所有", "部分",
]

# A stem that *starts* with one of these is a descriptor only when it carries
# no proper-noun material of its own -- approximated by requiring the remainder
# to be short (<= 4 chars). "中国农业大学" -> remainder 农业 (2) ... which is
# short too, so this list stays deliberately free of 中国/美国/日本; those are
# handled by the exact-stem list above instead.
LEAD_GENERIC_PREFIXES = [
    "海外", "全球", "国际", "国内", "国外", "全国", "各地", "各省",
    "本地", "当地", "海外龙头", "国内龙头",
]

# Curated: stems that are common nouns or product/category terms, not names.
# "蛋氨酸公司" is a category, "安迪苏集团" is a company -- no regex separates
# them, so this list is explicit and meant to grow. Add an entry whenever a
# run surfaces a category word masquerading as an entity.
LEAD_CATEGORY_STEMS = [
    "蛋氨酸", "氨基酸", "维生素", "抗生素", "益生菌", "酶制剂", "添加剂",
    "饲料", "化肥", "农药", "疫苗", "药品", "原料药", "中间体",
    "新能源", "半导体", "芯片", "光伏", "锂电", "储能", "机器人",
]

# Tokens that must never be treated as a latin brand name.
LEAD_STOPWORDS = {
    "the", "and", "for", "with", "from", "that", "this", "are", "was", "were",
    "not", "but", "you", "your", "our", "their", "has", "have", "will", "can",
    "http", "https", "www", "com", "org", "net", "html", "php", "index",
    "cookie", "policy", "privacy", "terms", "search", "results", "about",
    "more", "next", "prev", "page", "home", "login", "sign", "help", "contact",
    "javascript", "css", "div", "span", "class", "style", "script", "body",
    "head", "meta", "title", "width", "height", "color", "font", "button",
    "submit", "input", "form", "label", "table", "tbody", "thead", "href",
    "src", "alt", "png", "jpg", "svg", "gif", "webp", "utf", "charset",
    "lang", "zh", "cn", "en", "true", "false", "null", "none", "auto",
    "block", "flex", "grid", "margin", "padding", "border", "content",
    "google", "baidu", "bing", "duckduckgo", "yahoo", "sogou", "weibo",
    "zhihu", "github", "wikipedia", "facebook", "twitter", "youtube",
    "instagram", "linkedin", "reddit", "apple", "android", "chrome",
    "safari", "firefox", "edge", "jan", "feb", "mar", "apr", "dec",
    "nov", "oct", "sep", "aug", "jul", "jun", "may", "mon", "tue", "wed",
    "thu", "fri", "sat", "sun", "all", "new", "top", "best", "free",
    "login", "signup", "register", "download", "click", "here", "read",
}


def _strip_leading_noise(surface: str) -> str:
    """Remove leading function words from a greedy Chinese match."""
    changed = True
    while changed and len(surface) > 4:
        changed = False
        for noise in LEAD_LEADING_NOISE:
            if surface.startswith(noise) and len(surface) - len(noise) >= 4:
                surface = surface[len(noise):]
                changed = True
                break
    return surface


def _is_generic_cn(surface: str) -> bool:
    """True when a Chinese match is a descriptor rather than a name.

    A match is a descriptor when the whole surface is generic, or when the stem
    left after removing the 公司/集团/… suffix names nobody. Two independent
    signals flag such a stem: an exact hit in the stem list ("上市", "龙头"),
    and a *contained* quantifier or judgement word ("中国三大酶制剂" carries
    三大, "知名企业" carries 知名). The containment rule is what catches
    composites the exact list cannot enumerate.

    Geography prefixes are judged separately (LEAD_GENERIC_PREFIXES) so that a
    real name whose stem starts with 中国 -- 中国农业大学 -- survives.
    """
    if surface in LEAD_GENERIC_BLOCK:
        return True
    suffixes = ("股份有限公司", "有限公司", "研究所", "研究院", "公司", "集团", "大学")
    for suffix in suffixes:
        if surface == suffix:
            return True
        if not surface.endswith(suffix):
            continue
        stem = surface[: -len(suffix)]
        if not stem:
            return True
        if stem in LEAD_GENERIC_BLOCK or stem in LEAD_GENERIC_STEMS:
            return True
        # A stem ending in a generic qualifier ("…龙头", "…上市") is a descriptor.
        if any(stem.endswith(q) for q in ("龙头", "上市", "知名", "领先", "主要")):
            return True
        # A stem carrying a bare quantifier/judgement word anywhere is generic:
        # 中国三大酶制剂 / 知名企业 / 领先. Proper names essentially never
        # contain these as substrings.
        if any(q in stem for q in LEAD_GENERIC_QUALIFIERS):
            return True
        # Geography-only prefixes: descriptor unless proper-noun material remains.
        for prefix in LEAD_GENERIC_PREFIXES:
            if stem.startswith(prefix) and len(stem) - len(prefix) <= 3:
                return True
        # Category words ("蛋氨酸公司") name a product class, not a company.
        if stem in LEAD_CATEGORY_STEMS:
            return True
        # "…的…" is prose, not a proper name: 一些新兴的 -> 生物科技公司.
        if "的" in stem:
            return True
    return False


def _is_valid_latin(surface: str) -> bool:
    """A latin brand-ish token: >=3 chars, not a stopword, not a CSS/JS token.

    Two shapes qualify. A *word* (Evonik, Novonesis, Adisseo) needs a vowel. An
    *acronym* (BASF, DSM, SABIC) is all-caps, consonant-heavy and often has no
    vowel at all, so the vowel rule is dropped for it -- instead it must be
    3-6 chars and not collide with the web-token stopword list (HTTP, SVG, PNG,
    CSS, DIV are all listed there, so the acronym branch cannot readmit them).
    """
    low = surface.lower()
    if low in LEAD_STOPWORDS:
        return False
    body = re.sub(r"[^A-Za-z]", "", surface)
    if len(body) < 3:
        return False

    # Acronym branch: BASF / DSM / SABIC. All-caps, short, letters only.
    if body.isupper() and 3 <= len(body) <= 6 and body == surface.strip():
        return True

    # Word branch: needs a vowel to look like a pronounceable brand name.
    if len(surface) < 4:
        return False
    if not re.search(r"[aeiouy]", low):
        return False
    if body.isupper() and len(body) < 5:
        return False
    return True


# Pattern confidence. A patent number and a Chinese name carrying a company
# suffix are structural matches -- hard to produce by accident. A bare latin
# capitalized token is the loosest pattern we run, so it breaks ties last.
LEAD_KIND_RANK = {
    "patent": 0,
    "company_cn": 1,
    "person_role": 2,
    "company_brand": 3,
}


def extract_leads(records, top: int = 20) -> list[dict]:
    """Pull candidate leads out of L2 records.

    `records` is the list produced by fetch_search.cmd_multi -- each item is
    {"engine","url","status","ok","chars","text","links"}.
    Returns leads sorted by frequency, each with its hit count and sources.
    """
    counter: dict[str, dict] = {}

    def note(kind: str, surface: str, engine: str):
        surface = surface.strip()
        if not surface:
            return
        if kind == "company_cn":
            surface = _strip_leading_noise(surface)
            if _is_generic_cn(surface):
                return
        if kind == "company_brand" and not _is_valid_latin(surface):
            return
        if len(surface) < 4 and kind != "patent":
            return
        key = surface.lower()
        entry = counter.setdefault(key, {"kind": kind, "surface": surface,
                                         "count": 0, "engines": set()})
        entry["count"] += 1
        if engine:
            entry["engines"].add(engine)

    for record in records:
        if not record.get("ok"):
            continue
        engine = record.get("engine", "")
        # Search-result snippets mention the subject heavily; the page title
        # areas carry the entity names. Scan both text and link labels.
        blobs = [record.get("text", "") or ""]
        for link in record.get("links", []) or []:
            blobs.append(link.get("text", "") or "")
        for blob in blobs:
            for kind, pattern in LEAD_PATTERNS:
                for match in pattern.finditer(blob):
                    note(kind, match.group(0), engine)

    leads = []
    for entry in counter.values():
        entry["engines"] = sorted(entry["engines"])
        entry["engine_count"] = len(entry["engines"])
        leads.append(entry)

    # Rank by what actually predicts a usable lead:
    #   1. cross-engine agreement -- a name on many engines is a real entity,
    #      and agreement beats raw frequency (one snippet repeating a title 20
    #      times is weaker evidence than two engines naming the same company);
    #   2. pattern confidence -- patent / 公司-suffix names before bare latin
    #      tokens, so 赢创工业集团 outranks a stray capitalized word;
    #   3. raw frequency;
    #   4. surface length as a last deterministic tiebreak.
    leads.sort(key=lambda x: (-x["engine_count"],
                              LEAD_KIND_RANK.get(x["kind"], 9),
                              -x["count"],
                              -len(x["surface"]),
                              x["surface"]))
    return leads[:top]


DRILL_INTENTS = {
    "patent": ["{lead} 专利 申请 布局", "{lead} patent application"],
    "standard": ["{lead} 标准 起草 参与", "{lead} standard"],
    "financial": ["{lead} 营收 利润 财报 业绩", "{lead} revenue earnings"],
    "person": ["{lead} 履历 背景 经历", "{lead} background"],
    "product": ["{lead} 产品 参数 型号 规格", "{lead} product specification"],
    "capacity": ["{lead} 产能 基地 扩产 投产", "{lead} capacity expansion"],
    "cooperation": ["{lead} 合作 客户 用户 供应商", "{lead} partnership"],
    "verify": ["{lead} 澄清 声明 真实性", "{lead} fact check"],
}


def build_drill_queries(leads, intents, per_lead: int = 2) -> list[dict]:
    """L3: turn leads into targeted follow-up queries.

    `intents` is a list of DRILL_INTENTS keys. Each lead gets at most
    `per_lead` queries per intent so the fan-out stays bounded.
    """
    unknown = [i for i in intents if i not in DRILL_INTENTS]
    if unknown:
        raise ValueError("unknown intent(s): %s (choose from %s)"
                         % (", ".join(unknown), ", ".join(sorted(DRILL_INTENTS))))

    drills = []
    for lead in leads:
        templates = []
        for intent in intents:
            templates.extend(DRILL_INTENTS[intent][:per_lead])
        queries = [t.format(lead=lead["surface"]) for t in templates]
        if not queries:
            continue
        drills.append({
            "lead": lead["surface"],
            "kind": lead["kind"],
            "engine_count": lead.get("engine_count", 0),
            "intents": intents,
            "queries": queries,
        })
    return drills


# --------------------------------------------------------------------------
# L2 -- fan-out execution
# --------------------------------------------------------------------------

def run_fanout(plan, engines, engines_per_direction: int, args, quiet=False):
    """Execute L2: one fan-out per direction. Returns (results, diff_report)."""
    opener = fs.make_opener()
    results = []
    attempts = failures = 0

    for direction in plan["directions"]:
        # Use the direction's first query as its representative probe; extra
        # templates are available for the agent to run on demand.
        query = direction["queries"][0]
        slugs = _pick_engines(engines, direction["key"], engines_per_direction)
        records = []
        for index, slug in enumerate(slugs):
            if index:
                time.sleep(args.delay)
            url = fs.build_url(engines[slug], query)
            attempts += 1
            record = fs.fetch_one(opener, url, slug, args)
            if not record["ok"]:
                failures += 1
            records.append(record)
            if not quiet:
                state = "ok" if record["ok"] else "FAIL"
                print("  [%s] %-16s %-6s %s" % (direction["key"], slug, state,
                                                "%d chars" % record["chars"]),
                      file=sys.stderr)
        results.append({
            "direction": direction["key"],
            "label": direction["label"],
            "query": query,
            "all_queries": direction["queries"],
            "engines": slugs,
            "records": records,
        })

    report = {"attempts": attempts, "failures": failures,
              "success": attempts - failures}
    return results, report


def _pick_engines(engines, direction_key, limit):
    """Choose engines for a direction, biased by what that direction needs.

    Patent/standard work wants academic + Chinese sources; market/capacity
    wants news + general; community wants community engines. Falling back to
    the deep-research preset keeps behaviour predictable.
    """
    preferred = {
        "product": ["bing_cn", "baidu", "google", "zhihu"],
        "patent": ["google_scholar", "cnki", "bing_cn", "baidu"],
        "market": ["bing_cn", "baidu", "google_news", "sogou"],
        "capacity": ["bing_cn", "baidu", "google", "sogou"],
        "strategy": ["bing_cn", "google", "google_news", "baidu"],
        "timeline": ["bing_cn", "baidu", "google", "wikipedia_zh"],
        "competitor": ["bing_cn", "google", "baidu", "zhihu"],
        "community": ["zhihu", "weibo", "wechat", "bilibili"],
        "risk": ["bing_cn", "baidu", "google", "google_news"],
    }.get(direction_key, ["bing_cn", "baidu", "google"])

    chosen = [s for s in preferred if s in engines]
    if not chosen:
        chosen = [s for s in ("baidu", "bing_cn", "duckduckgo") if s in engines]
    return chosen[:limit] if limit else chosen


# --------------------------------------------------------------------------
# Commands
# --------------------------------------------------------------------------

def _resolve_profile(args):
    if getattr(args, "profile", ""):
        return args.profile, "explicit"
    return pick_profile(args.topic)


def cmd_plan(args):
    profile, reason = _resolve_profile(args)
    plan = build_plan(args.topic, profile, args.max_directions,
                      comparison=args.comparison)
    plan["profile_reason"] = reason
    if args.json:
        print(json.dumps(plan, ensure_ascii=False, indent=2))
        return 0
    print("topic   : %s" % plan["topic"])
    print("profile : %s  (%s)" % (plan["profile"], reason))
    print("plan    : %d directions / %d queries\n"
          % (plan["direction_count"], plan["query_count"]))
    for direction in plan["directions"]:
        print("[%s] %s — %s" % (direction["key"], direction["label"],
                                direction["purpose"]))
        for query in direction["queries"]:
            print("    %s" % query)
        print()
    return 0


def cmd_fanout(args):
    engines = fs.load_engines()
    profile, reason = _resolve_profile(args)
    plan = build_plan(args.topic, profile, args.max_directions,
                      comparison=args.comparison)
    if not args.quiet:
        print("L1 plan: profile=%s (%s), %d directions"
              % (profile, reason, plan["direction_count"]), file=sys.stderr)
        print("L2 fanout: %d engines per direction, %ss delay"
              % (args.engines_per_direction, args.delay), file=sys.stderr)

    results, report = run_fanout(plan, engines, args.engines_per_direction, args,
                                 quiet=args.quiet)
    payload = {"layer": "L2", "topic": args.topic, "profile": profile,
               "plan": plan, "results": results, "report": report}

    if args.out:
        Path(args.out).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print("wrote %s" % args.out, file=sys.stderr)

    if args.json:
        flat = [dict(r, text=(r.get("text") or "")[:args.max_chars])
                for d in results for r in d["records"]]
        print(json.dumps({"layer": "L2", "profile": profile,
                          "report": report, "records": flat},
                         ensure_ascii=False, indent=2))
    elif not args.quiet:
        print("\nL2 done: %d/%d requests ok" % (report["success"],
                                                report["attempts"]))

    if report["success"] == 0:
        return 2
    if report["failures"]:
        return 3
    return 0


def _load_records(path):
    """Accept any of: `fanout --out` payload, `run --out` payload, or a bare list.

    `fanout` writes {"results": [...]}; `run` writes {"l2_results": [...]};
    `--json` on either writes a flat {"records": [...]}. All three are handled
    so a file produced by one subcommand can feed another.
    """
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(data, dict):
        if "results" in data:
            return [r for d in data["results"] for r in d["records"]]
        if "l2_results" in data:
            return [r for d in data["l2_results"] for r in d["records"]]
        if "records" in data:
            return data["records"]
    if isinstance(data, list):
        return data
    raise ValueError("cannot find records in %s (expected results / l2_results / records)"
                     % path)


def cmd_leads(args):
    records = _load_records(args.source)
    leads = extract_leads(records, top=args.top)
    if args.json:
        print(json.dumps({"count": len(leads), "leads": leads},
                         ensure_ascii=False, indent=2))
        return 0
    print("leads from %d records: %d\n" % (len(records), len(leads)))
    for lead in leads:
        print("%-34s %-12s engines=%d hits=%d"
              % (lead["surface"], lead["kind"], lead["engine_count"],
                 lead["count"]))
    return 0


def cmd_drill(args):
    records = _load_records(args.source)
    leads = extract_leads(records, top=args.top)
    if args.leads_filter:
        wanted = [w.strip().lower() for w in args.leads_filter.split(",")]
        leads = [l for l in leads if l["surface"].lower() in wanted]
    intents = [i.strip() for i in args.intent.split(",") if i.strip()]
    drills = build_drill_queries(leads, intents, per_lead=args.per_lead)
    payload = {"layer": "L3", "intents": intents, "lead_count": len(leads),
               "query_count": sum(len(d["queries"]) for d in drills),
               "drills": drills}
    if args.out:
        Path(args.out).write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                                  encoding="utf-8")
        print("wrote %s" % args.out, file=sys.stderr)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0
    print("L3 drill plan: %d leads -> %d queries (intents: %s)\n"
          % (len(leads), payload["query_count"], ", ".join(intents)))
    for drill in drills:
        print("[%s] %s" % (drill["kind"], drill["lead"]))
        for query in drill["queries"]:
            print("    %s" % query)
    return 0


def cmd_run(args):
    """End-to-end: L1 plan -> L2 fanout -> L3 drill plan."""
    engines = fs.load_engines()
    profile, reason = _resolve_profile(args)

    # ---- L1
    plan = build_plan(args.topic, profile, args.max_directions,
                      comparison=args.comparison)
    if not args.quiet:
        print("=" * 68, file=sys.stderr)
        print("L1 PLAN  profile=%s (%s)  %d directions / %d queries"
              % (profile, reason, plan["direction_count"], plan["query_count"]),
              file=sys.stderr)
        print("=" * 68, file=sys.stderr)

    # ---- L2
    results, report = run_fanout(plan, engines, args.engines_per_direction, args,
                                 quiet=args.quiet)

    # ---- L3
    all_records = [r for d in results for r in d["records"]]
    leads = extract_leads(all_records, top=args.top)
    intents = [i.strip() for i in args.intent.split(",") if i.strip()]
    drills = build_drill_queries(leads, intents, per_lead=args.per_lead)

    payload = {
        "topic": args.topic,
        "profile": profile,
        "profile_reason": reason,
        "l1_plan": plan,
        "l2_report": report,
        "l3_lead_count": len(leads),
        "l3_query_count": sum(len(d["queries"]) for d in drills),
        "l3_drills": drills,
        "l2_results": [{"direction": d["direction"], "query": d["query"],
                        "engines": d["engines"],
                        "records": [dict(r, text=(r.get("text") or "")[:args.max_chars])
                                    for r in d["records"]]}
                       for d in results],
    }

    if args.out:
        Path(args.out).write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                                  encoding="utf-8")
        if not args.quiet:
            print("wrote %s" % args.out, file=sys.stderr)

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    elif not args.quiet:
        print("=" * 68, file=sys.stderr)
        print("L2  %d/%d ok" % (report["success"], report["attempts"]),
              file=sys.stderr)
        print("L3  %d leads -> %d drill queries"
              % (len(leads), payload["l3_query_count"]), file=sys.stderr)
        print("=" * 68, file=sys.stderr)
        for drill in drills[:args.show_drills]:
            print("[%s] %s" % (drill["kind"], drill["lead"]))
            for query in drill["queries"]:
                print("    %s" % query)

    if report["success"] == 0:
        return 2
    if report["failures"]:
        return 3
    return 0


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def build_parser():
    parser = argparse.ArgumentParser(
        prog="layered_search.py",
        description="Layered (L1 plan -> L2 fanout -> L3 drill) search orchestration.",
    )
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--topic", required=True, help="research subject")
    common.add_argument("--profile", default="",
                        help="research profile: %s (default: auto-detect)"
                             % ", ".join(sorted(PROFILES)))
    common.add_argument("--max-directions", type=int, default=0,
                        help="cap the number of directions (0 = profile default)")
    common.add_argument("--comparison", action="store_true",
                        help="append comparison-word queries (for competitor work)")

    fan = argparse.ArgumentParser(add_help=False)
    fan.add_argument("--engines-per-direction", type=int, default=3,
                     help="engines probed per direction (default 3)")
    fan.add_argument("--timeout", type=float, default=20.0)
    fan.add_argument("--delay", type=float, default=1.5)
    fan.add_argument("--max-chars", type=int, default=12000)
    fan.add_argument("--links", action="store_true", default=True)
    fan.add_argument("--json", action="store_true")
    fan.add_argument("--quiet", action="store_true")
    fan.add_argument("--out", default="", help="write the full payload to this path")

    lead = argparse.ArgumentParser(add_help=False)
    lead.add_argument("--top", type=int, default=20, help="max leads to return")
    lead.add_argument("--json", action="store_true")

    sub = parser.add_subparsers(dest="command", required=True)

    p_plan = sub.add_parser("plan", help="L1 only: print the keyword plan",
                            parents=[common])
    p_plan.add_argument("--json", action="store_true")
    p_plan.set_defaults(func=cmd_plan,
                        max_directions=0, comparison=False)

    p_fan = sub.add_parser("fanout", help="L2 only: run the plan over engines",
                           parents=[common, fan])
    p_fan.set_defaults(func=cmd_fanout)

    p_leads = sub.add_parser("leads", help="L3 step 1: extract leads from L2 output",
                             parents=[lead])
    p_leads.add_argument("--from", dest="source", required=True,
                         help="L2 JSON file written by `fanout --out`")
    p_leads.set_defaults(func=cmd_leads)

    p_drill = sub.add_parser("drill", help="L3 step 2: build drill queries from leads",
                             parents=[lead])
    p_drill.add_argument("--from", dest="source", required=True)
    p_drill.add_argument("--intent", default="patent,person,product",
                         help="intents: %s" % ", ".join(sorted(DRILL_INTENTS)))
    p_drill.add_argument("--per-lead", type=int, default=2,
                         help="max queries per lead per intent")
    p_drill.add_argument("--leads-filter", default="",
                         help="comma-separated surfaces to keep")
    p_drill.add_argument("--out", default="")
    p_drill.set_defaults(func=cmd_drill)

    p_run = sub.add_parser("run", help="end to end: L1 -> L2 -> L3",
                           parents=[common, fan])
    p_run.add_argument("--intent", default="patent,person,product")
    p_run.add_argument("--per-lead", type=int, default=2)
    p_run.add_argument("--top", type=int, default=15)
    p_run.add_argument("--show-drills", type=int, default=6)
    p_run.set_defaults(func=cmd_run)

    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except ValueError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
