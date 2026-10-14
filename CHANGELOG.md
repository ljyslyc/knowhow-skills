# CHANGELOG

## v0.2.0 — 2026-10-14

这一版解决三件事：**让第一次拿到套件的 agent 能直接上手**、**换任何宿主都能跑**、
**搜索从「一轮扇出」升级为「三层层级检索」**。

### 新增

- **三层分层检索**（`multi-search-engine` v4.1.0）：
  - `scripts/layered_search.py`——L1 按 9 个调查方向（产品/专利/市场/产能/战略/历程/竞品/口碑/风险）
    生成关键词计划，方向由 profile（company/industry/tech/person/concept/product）自动判定；
    L2 多引擎并发抓取；L3 从正文抽取实体线索（公司名、专利号、人物），按跨引擎一致性排序，
    再生成定向追查词。
  - 线索抽取为**确定性正则 + 频次**，每条线索可审计。过滤掉冒充名字的描述词
    （`上市公司`/`海外龙头公司`/`蛋氨酸公司`/`一些新兴的生物科技公司`）与网页/CSS 词元。
  - `scripts/test_layered_search.py`——**71 条确定性测试，不需要网络**。
  - 子命令：`plan` / `fanout` / `leads` / `drill` / `run`；`run --out` 的结果可被
    `leads --in` / `drill --in` 复用，不重跑网络。
- **`docs/WORKFLOW.md`**——编排层文档：全局流程图、逐个技能的交接契约（触发/输入/输出/上下游）、
  常见组合路径、写新技能的迁移规则、接手检查清单。

### 变更

- **全部 6 个技能的 `description` 重写为首次使用视角**：这是什么、什么时候触发、
  什么时候不要用、怎么工作、你需要准备什么、你会拿到什么。不再只堆一串触发词。
- **可迁移性修复**：
  - `hv-analysis`：移除硬编码路径 `/mnt/.claude/skills/web-access/SKILL.md`；联网指引改为
    工具中立（附宿主映射表）；并行的子 Agent 说明改为「宿主提供则用，不提供就顺序执行」；
    接入套件的分层检索作为第一步素材来源。
  - `neat-freak/references/agent-paths.md`：从仅覆盖 Claude/Codex 扩展到
    **Claude Code / OpenAI Codex / WorkBuddy / OpenClaw** 四平台速查。
  - `neat-freak/scripts/audit-inventory.sh`：平台目录探测补上 `.workbuddy`、`.openclaw`；
    全局规则文件候选补上 OpenClaw / WorkBuddy 路径。
- 各技能补充 `metadata.category` 与 `version`。

## v0.1.0 — 2026-10-12

首个版本。以「知识内容产出」为主线，从 khazix-skills（MIT）精选重组并扩展。

### 新增

- **套件骨架**：`install.sh` 本地复制安装（不联网、不执行远程脚本）、README、本变更日志、`docs/OPTIMIZATION.md`。

### 技能

- `multi-search-engine` **升级至 v4.0.0**：
  - 引擎从 17 个扩至 **39 个**，按 **7 大类**归类：中文综合 / 国际综合 / 学术与文献 / 技术社区 / 中文社区 / 新闻资讯 / 专用与事实。
  - 新增学术类：Google Scholar、arXiv、Semantic Scholar、PubMed、CNKI、Wikipedia（中/英）。
  - 新增技术类：GitHub、Stack Overflow、Hacker News、DEV Community。
  - 新增中文社区：知乎、微博、B 站、掘金、CSDN、小红书。
  - 新增新闻类：Google News、Bing News；新增通用类：Quark、Mojeek、Marginalia。
  - `fetch_search.py` 新增 **`presets`** 命令与 7 组场景预设（quick / deep-research / academic / tech / chinese / news / competitor / fact-check）。
  - `multi` 新增 `--preset` / `--category`，选择优先级：`--engines` > `--preset` > `--category` > 默认。
  - `engines` 支持 `--category` 过滤；引擎注册表新增 `category` 字段。
- `hv-analysis`：横纵分析法深度研究（原样纳入）。
- `khazix-writer`：公众号长文写作（原样纳入）。
- `leader`：目标拆解任务书（原样纳入）。
- `neat-freak`：知识收尾（原样纳入，移除 evals 测试夹具）。
- `aihot`：AI 资讯查询（原样纳入，**移除远程下载安装脚本 `install.sh`**）。

### 变更（相对上游 khazix-skills）

- 未纳入 `storage-analyzer`（磁盘清理，与知识内容产出无关）。
- 移除各技能的 evals 目录与远程安装器，统一由顶层 `install.sh` 安装。

### 安全

- 全部技能通过静态安全审计：无隐藏 Unicode、无 base64 载荷、无提示词注入话术、无凭据外送、域名白名单可解释。
