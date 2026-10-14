#!/usr/bin/env python3
"""Deterministic tests for layered_search's lead extraction.

Run: python3 scripts/test_layered_search.py

This is a pure-function test: no network, no files. It pins the behaviour of
the two filters that decide whether a lead is real, so a later tweak to the
stopword/stem lists cannot silently start emitting junk again.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import layered_search as ls  # noqa: E402

PASS = FAIL = 0


def check(label, got, want):
    global PASS, FAIL
    if got == want:
        PASS += 1
        print("  ok   %s" % label)
    else:
        FAIL += 1
        print("  FAIL %s -> got %r, want %r" % (label, got, want))


# ---- _strip_leading_noise: strip noise, but never eat a real name prefix ----
print("_strip_leading_noise")

check("strips 拟批复", ls._strip_leading_noise("拟批复河南普特威生物工程有限公司"),
      "河南普特威生物工程有限公司")
check("strips 据悉", ls._strip_leading_noise("据悉赢创工业集团"), "赢创工业集团")
check("keeps 中粮 (中 is a real name prefix)",
      ls._strip_leading_noise("中粮营养健康研究院"), "中粮营养健康研究院")
check("keeps 华为", ls._strip_leading_noise("华为技术有限公司"), "华为技术有限公司")
check("keeps 新华", ls._strip_leading_noise("新华制药"), "新华制药")
check("strips 该", ls._strip_leading_noise("该赢创集团"), "赢创集团")
check("no-op on clean name", ls._strip_leading_noise("洛阳栾川钼业集团"),
      "洛阳栾川钼业集团")
check("does not strip past the 4-char floor", ls._strip_leading_noise("的abc"), "的abc")


# ---- _is_generic_cn: descriptors rejected, real names kept ----
print("_is_generic_cn (expect True = reject)")

for bad in ["上市公司", "有限公司", "北交所上市公司", "海外龙头公司",
            "中国三大酶制剂公司", "三家公司", "各大集团", "该大学",
            "公司", "集团", "大学", "知名企业公司", "领先公司",
            "蛋氨酸公司", "新兴的生物科技公司", "一些新兴的生物科技公司"]:
    check("reject %s" % bad, ls._is_generic_cn(bad), True)

for good in ["河南普特威生物工程有限公司", "酶好生活集团", "中粮营养健康研究院",
             "赢创工业集团", "洛阳栾川钼业集团", "安迪苏集团",
             "中国农业大学", "新和成股份有限公司"]:
    check("keep %s" % good, ls._is_generic_cn(good), False)


# ---- _is_valid_latin: brand tokens only ----
print("_is_valid_latin (expect True = keep)")

for bad in ["HTTP", "div", "www", "com", "abc", "xyz", "the", "and",
            "SVG", "CSS", "PNG", "nbsp", "nbsp;"]:
    check("reject %s" % bad, ls._is_valid_latin(bad), False)

for good in ["Evonik", "BASF", "Novonesis", "QYResearch", "Adisseo", "DSM"]:
    check("keep %s" % good, ls._is_valid_latin(good), True)


# ---- extract_leads end-to-end on a synthetic record set ----
print("extract_leads (end to end)")

records = [
    {"engine": "baidu", "ok": True, "text":
        "拟批复河南普特威生物工程有限公司 酶制剂项目。海外龙头公司纷纷布局。"
        "赢创工业集团、诺维信 Novonesis 均在列。",
     "links": [{"text": "酶好生活集团官网", "href": "https://example.com"},
               {"text": "北交所上市公司列表", "href": "https://example.com/2"}]},
    {"engine": "bing_cn", "ok": True, "text":
        "赢创工业集团 与 Novonesis 竞争。中粮营养健康研究院参与标准制定。",
     "links": []},
]

leads = ls.extract_leads(records, top=20)
surfaces = [l["surface"] for l in leads]

check("keeps 赢创工业集团", "赢创工业集团" in surfaces, True)
check("keeps Novonesis", any(s.lower() == "novonesis" for s in surfaces), True)
check("keeps 酶好生活集团", "酶好生活集团" in surfaces, True)
check("keeps 中粮营养健康研究院", "中粮营养健康研究院" in surfaces, True)
check("rejects 北交所上市公司", "北交所上市公司" in surfaces, False)
check("rejects 海外龙头公司", "海外龙头公司" in surfaces, False)
check("cross-engine lead ranks first", leads[0]["surface"], "赢创工业集团")
check("cross-engine count is 2", leads[0]["engine_count"], 2)


# ---- build_drill_queries: bounded and intent-scoped ----
print("build_drill_queries")

drills = ls.build_drill_queries(leads, ["patent", "product"], per_lead=2)
check("one drill per lead", len(drills), len(leads))
check("4 queries per lead (2 intents x 2)", len(drills[0]["queries"]), 4)
check("queries mention the lead", all(drills[0]["lead"] in q for q in drills[0]["queries"]), True)

try:
    ls.build_drill_queries(leads, ["nonexistent-intent"])
    check("unknown intent raises", "no raise", "ValueError")
except ValueError:
    check("unknown intent raises", "ValueError", "ValueError")


# ---- build_plan: deterministic and profile-scoped ----
print("build_plan")

p1 = ls.build_plan("赢创", "company")
p2 = ls.build_plan("赢创", "company")
check("deterministic", p1, p2)
check("company has 6 directions", p1["direction_count"], 6)
check("comparison adds queries", ls.build_plan("赢创", "company", comparison=True)["query_count"] > p1["query_count"], True)

try:
    ls.build_plan("x", "not-a-profile")
    check("unknown profile raises", "no raise", "ValueError")
except ValueError:
    check("unknown profile raises", "ValueError", "ValueError")

check("auto-detect industry", ls.pick_profile("饲用酶制剂行业")[0], "industry")
check("auto-detect company", ls.pick_profile("蓝星安迪苏股份有限公司")[0], "company")
check("auto-detect tech", ls.pick_profile("Transformer 架构")[0], "tech")
check("defaults to company", ls.pick_profile("随便什么")[0], "company")


print("\n%d passed, %d failed" % (PASS, FAIL))
sys.exit(1 if FAIL else 0)
