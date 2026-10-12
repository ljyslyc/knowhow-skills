# CHANGELOG

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
