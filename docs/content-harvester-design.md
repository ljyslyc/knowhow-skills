# content-harvester · 内容抓取技能设计方案

> **状态**：方案待评审（v0.1，2026-10-13）
> **设计依据**：本轮 FDE 知识库 v4 重构 + P1 原文回填的全部实战经验
> **拟归属**：knowhow-skills 套件（作为「搜得宽」与「用得上」之间的新环节）

---

## 0. 一句话定位

**把「搜到的链接」变成「可逐字引用的档案」的采集官。**

| 环节 | 技能 | 职责边界 |
|---|---|---|
| 搜得宽 | `multi-search-engine` | 39 引擎扇出，产出候选 URL 列表 |
| **存得住** | **`content-harvester`（本方案）** | **发现 → 抓取 → 核验 → 归档 → 登记 → 回填辅助** |
| 研得深 | `hv-analysis` | 消费档案做横纵研究 |
| 写得像人 | `khazix-writer` | 引用档案原文写作 |

multi-search-engine 止步于「拿到链接」；本技能负责「让链接变成带元数据、可复核、可逐字引用的本地档案」。

## 1. 触发场景与触发词

**触发**（任一说法出现即进入）：
- 「把这个链接存档 / 抓下来 / 归档」
- 「找 XX 主题的一手资料 / 可靠信源」
- 「验证这批链接还能不能打开」
- 「给知识库补充素材」（指向本项目时）
- 「备份这个网页 / 这本书 / 这个仓库」
- 「这个数字/引文的出处是哪」

**不触发**：纯写作、纯检索摘要、无归档意图的一次性问答。

## 2. 五步流程

```
PLAN 定采编单 → DISCOVER 发现候选 → FETCH 抓取 → VERIFY 核验 → ARCHIVE 归档登记
      ↑                                                              │
      └────────────────── 采集报告 + 失败原因分布 + 待人工队列 ←────────┘
```

| 步 | 输入 | 动作 | 输出 |
|---|---|---|---|
| **PLAN** | 主题 / 缺口清单 / 已知 URL | 生成采编单：目标分级（A/B/C 配额）、数量预算、必抓清单、禁收规则 | 采编单（markdown，可中断续跑） |
| **DISCOVER** | 主题 | 主题→多组检索式（中英 × 多角度）→ multi-search-engine 预设扇出 → 候选 URL 池：去重、按域名分类（官方/媒体/社区/API/仓库）、标注预期通道 | candidates.json |
| **FETCH** | candidates.json | 通道决策树（见 §3）按序降级；DNS 韧性；礼貌限速；幂等（已存则跳过） | raw/ 原始产物 + fetch 结果记录 |
| **VERIFY** | raw/ + 登记表 | HTTP 状态 + 标题核对 + 404 页检测 + 反爬判别 + 死链标定 | verify 记录（含失败原因分类） |
| **ARCHIVE** | 通过核验的产物 | front-matter 九项 + 原文逐字 + sha256 + 登记到库（适配器）+ 生成采集报告 | sources/ 档案 + 登记表 + 报告 |

## 3. 抓取通道决策树（本方案核心资产）

按目标形态选通道，失败沿降级路径走，**每一跳都记录用了什么**：

| 目标形态 | 首选通道 | 降级路径 | 已知陷阱（本轮实测） |
|---|---|---|---|
| 官方招聘/职位 API（Lever/Ashby/Greenhouse） | `curl` 直取 JSON → slim 重整 | 无 | 列表接口常不含正文→逐岗位补抓；响应体可达 13MB 必须原始 JSON + 派生精简双层存档 |
| GitHub 仓库 / 开源书 | `git trees API` + `codeload tarball` | 单文件 raw | raw.githubusercontent 可能被墙；tarball 最稳；逐章登记便于引用到章 |
| 静态 HTML（多数官网/新闻） | `curl`（dig取IP+`--resolve`）+ HTML→文本 | 无 | 系统 DNS 间歇故障/污染——**必须先 dig 再 --resolve 直连**，否则大规模误报失败 |
| JS 渲染页（palantir.com 等） | 浏览器/CDP | 标记待人工 | curl 只得 20-40 字符壳；**不要**把壳当内容存档 |
| 登录态站点（脉盟/知乎全文） | CDP 登录态 | 标记待人工（需用户扫码） | 匿名必被拦；不尝试绕过 |
| PDF / 扫描件 | 标记待转换（pdftotext/浏览器打印） | — | 二进制严禁当文本落盘 |
| 搜索引擎发现 | multi-search-engine 39 引擎预设 | GitHub API / 官方 API / 已知域名直采 | bing→cn.bing.com 跳转后 DNS 失败；DDG/archive.org 可能被墙——引擎失败≠无源，换通道 |

## 4. 八条铁律（违反即停止入库）

1. **先验证后入库**：HTTP 状态码 + 标题核对，双通过才准进（v3 教训：腾讯新闻链接 200 但返回 404 页）。
2. **原文一字不改**：只清 HTML 噪音（script/style/导航），不清内容、不概括、不纠错——错别字和宣传话术都是证据。
3. **非 200 ≠ 死链**：403/TIMEOUT/DNS 失败记原因（反爬/本机网络/JS 壳）后**保留收录**，粗暴剔除会丢最权威的来源。
4. **404 页不是内容**：HTTP 200 但正文是错误页 = 死链，标 dead 不留档。
5. **幂等**：同一 URL 不重复归档；重抓先比对 sha256，内容有变才更新并留 recheck 记录。
6. **可复核四件套**：每条档案必须带 `fetched / method / http / sha256`，缺一不可。
7. **分级强制**：A 一手官方 / B 权威署名 / C 二手待核，未判定默认 C 并挂「待核」标。
8. **留痕含失败**：失败也记录（原因分类 + 时间），形成「待人工队列」而不是静默丢失。

## 5. 目录结构与脚本清单

```
skills/content-harvester/
├── SKILL.md                     # 主入口：触发词、五步流程、铁律、报告格式
├── references/
│   ├── channels.md              # 通道决策树详版 + 每通道可复制命令模板
│   ├── archive-format.md        # front-matter 九项规范 + A/B/C 分层 + sha256 纪律
│   ├── verify-discipline.md     # 核验细则：404 检测正则、反爬判别、DNS 韧性、重试策略
│   └── kb-adapter.md            # 知识库集成契约：sources.js schema、claims 回填协议
└── scripts/
    ├── fetch.py                 # 统一抓取 CLI：dig+--resolve、UA、限速、404检测、通道降级
    ├── discover.py              # 主题→检索式→扇出→候选池（可调 multi-search-engine）
    ├── verify.py                # 批量核验：状态+标题+存活，输出实测表
    ├── archive.py               # 落盘+sha256+登记（经 kb-adapter 写入目标库）
    └── harvest.py               # 主编排：采编单→一条龙→采集报告（可 --resume）
```

**脚本间只传文件不传状态**（candidates.json / fetch-results.json / verify-table.json），任一环可单独重跑。

## 6. 与知识库的集成契约（kb-adapter）

知识库侧只提供三样，技能保持通用：

```jsonc
// knowledge-base.json（适配器配置示例）
{
  "registry": "FDE知识库/data/sources.js",   // 登记表路径
  "archiveDir": "FDE知识库/sources",          // 档案根目录
  "dirByCred": { "A": "A-一手官方", "B": "B-权威转述", "C": "C-二手待核" },
  "idPrefix": "S-",                           // 档案 ID 规则
  "claimFile": "FDE知识库/data/cases.js",     // 回填目标（可选）
  "quoteVerify": true                          // 落档后扫描 claims 提议 origin=quote 升级
}
```

**回填辅助（本技能对知识库的最大增值）**：归档完成后，`archive.py --suggest` 扫描登记表内既有论断（claims/methods.caseEvidence），找出与档案原文逐字（归一化后）匹配的句子，产出**回填建议清单**（案例 ID + claim 序号 + 建议 quote 文本 + 置信度），人工确认后一键写入。这把 P2「抽事实与引文」从手工变成半自动。

## 7. 实战经验 → 机制映射表

| # | 本轮实测经验 | 技能内机制 |
|---|---|---|
| 1 | 系统 DNS 间歇故障+污染导致大面积误报失败 | fetch.py 默认 dig 取 IP + `--resolve` 直连（§3/verify-discipline） |
| 2 | HTTP 200 但是 404 错误页（华能链接） | 404 检测正则 + 标题核对（铁律 1/4） |
| 3 | palantir.com 等 JS 渲染只得壳页面 | 通道决策树「JS 壳 → 浏览器/CDP」，壳页禁止落档（铁律 2） |
| 4 | 403/超时不等于死链（OpenAI、cnii、people.com.cn） | 失败原因分类学 + 保留收录（铁律 3） |
| 5 | 范冰书 33 万字节需逐章可引用 | codeload tarball + 逐章登记（§3） |
| 6 | API 快照 17MB 不可直接当档案 | slim 双层：原始 JSON 字节存档 + 派生精简 md（§3 + kb-adapter） |
| 7 | 官方数字口径会骗人（"经测算"被挂成官方口径） | 归档时提取口径信号词（实测/测算/官方称/据介绍），caliber 自动建议 |
| 8 | 引文必须逐字可查 | 落档后 B2 式逐字自检（归一化空白/引号），不通过即报错 |
| 9 | 135 处 `（undefined）` 渲染 bug | archive.py 输出前空值扫描 |
| 10 | 招聘数据有时效性（110 vs 111） | 登记快照日期 + recheck 历史，报告显式提示时效 |
| 11 | 重复抓取浪费且可能覆盖 | 幂等 + sha256 比对（铁律 5） |
| 12 | 采集要能中断续跑 | 采编单 + `--resume` + 每步独立 JSON 中间态 |

## 8. 实施计划

| 阶段 | 范围 | 工期估计 |
|---|---|---|
| **MVP** | fetch.py（DNS 韧性 + 404 检测 + 通道降级）+ archive.py（front-matter + sha256 + kb-adapter）+ SKILL.md 主流程 | 半天（本次实战代码已成型，主要是通用化改造） |
| **v1.0** | discover.py（检索式生成 + 调 multi-search-engine）+ harvest.py 编排 + 采集报告 + --resume | 1 天 |
| **v1.1** | --suggest 回填辅助（claims 逐字匹配建议）+ verify.py 批量复检 + 口径信号词提取 | 1 天 |

## 9. 待决策问题

1. **归属**：进 knowhow-skills 套件（与 6 技能并列，install.sh 自动带上）vs 独立仓库？
2. **命名**：`content-harvester`（采集官）vs `source-archiver`（归档官）vs 其他？
3. **回填辅助进不进 MVP**：它写知识库数据文件（有风险），MVP 只出建议清单、v1.1 才给一键写入，是否同意？
4. **多引擎依赖**：discover.py 是否硬依赖 multi-search-engine（套件内已装），还是自带 curl 兜底？
