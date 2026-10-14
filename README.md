# knowhow-skills · 知识内容产出套件

一套面向**知识内容产出**的智能体技能集：把"搜得宽 → 研得深 → 写得像人 → 拆得清 → 收得干净"串成一条流水线。
基于 [khazix-skills](https://github.com/KKKKhazix/khazix-skills)（MIT）精选重组，并按知识内容产出场景做了扩展与增强。

## 套件定位

| 环节 | 技能 | 解决的问题 |
|---|---|---|
| **入口 · 搜得宽** | `multi-search-engine` | 39 个引擎、7 大类，零 API Key；**三层层级检索**：按方向生成关键词 → 多引擎扇出 → 抽取线索深挖 |
| **研究 · 研得深** | `hv-analysis` | 横纵分析法：纵轴追历程、横轴比同类，产出长篇 PDF 研究报告 |
| **写作 · 写得像人** | `khazix-writer` | 公众号长文写作，四层自检压掉"AI 味" |
| **目标 · 拆得清** | `leader` | 把一句话想法拆成 agent 能独立跑完的任务书 |
| **收尾 · 收得干净** | `neat-freak` | 对齐文档 / 规则文件 / 记忆与实际代码 |
| **资讯 · 查得快** | `aihot` | 实时查询中文 AI 资讯，不凭训练记忆答新闻 |

**各技能怎么串起来、交接什么、换到别的 agent 上怎么直接用**——见 [docs/WORKFLOW.md](docs/WORKFLOW.md)。这是给接手套件的 agent 看的编排层文档，含全局流程图、逐个交接契约（触发/输入/输出/上下游）和常见组合路径。

## 安装

```bash
# 安装到 WorkBuddy 用户级技能目录
./install.sh

# 或指定目标目录
./install.sh ~/.workbuddy/skills
./install.sh ~/.claude/skills
```

脚本只做复制，**不联网、不执行下载、不修改任何已有技能**；同名技能默认跳过，需覆盖时加 `--force`。

### 依赖

套件本体零依赖——`multi-search-engine` 只用 Python 标准库；`hv-analysis` 的 PDF 导出脚本是**可选**能力，不用它就不需要装任何东西。

| 能力 | 依赖 | 安装 |
|---|---|---|
| Markdown → PDF（`hv-analysis/scripts/md_to_pdf.py`） | `markdown`、`weasyprint` | `pip install markdown weasyprint` |

`weasyprint` 在 macOS 上还需系统级 `pango` 等库（`brew install pango`）；缺失时脚本会报 `ModuleNotFoundError`，只影响 PDF 导出，不影响报告正文生成。

## 典型用法

| 你想做的事 | 这样说 |
|---|---|
| 摸清一个行业/竞品 | 「帮我研究一下 XX」→ `hv-analysis`，检索走 `multi-search-engine` |
| 写一篇长文 | 「用我的风格写篇文章」→ `khazix-writer` |
| 一次覆盖多平台 | 先 `multi-search-engine` 扇出素材，再交 `khazix-writer` |
| 把想法丢给 agent 自己跑 | 「帮我给 agent 写个目标」→ `leader` |
| 项目收尾 | 「把文档和记忆整理一下」→ `neat-freak` |
| 今天 AI 圈发生了什么 | 直接问 → `aihot` |

### 搜索预设

`multi-search-engine` v4 内置 7 组预设，直接按场景调用：

```bash
python3 skills/multi-search-engine/scripts/fetch_search.py presets
# quick / deep-research / academic / tech / chinese / news / competitor / fact-check

python3 skills/multi-search-engine/scripts/fetch_search.py multi \
  --query "饲用酶制剂 竞争格局" --preset competitor --json
```

### 分层检索

一次搜索不可能搜全——关键字对不对，得先看第一轮搜回来什么才知道。所以 v4.1 加了
**三层层级检索**：按「调查方向」自动铺开关键词 → 多引擎并发抓取 → 从正文里抽出公司名、
专利号等实体，据此生成定向追查词。第二轮的深挖是**数据驱动**的，不是凭感觉猜第二组关键词。

```bash
# 只看计划，不花网络调用
python3 skills/multi-search-engine/scripts/layered_search.py plan --topic "饲用酶制剂行业"

# 一次跑完三层
python3 skills/multi-search-engine/scripts/layered_search.py run \
  --topic "赢创工业集团" --profile company --comparison \
  --max-directions 4 --engines-per-direction 3 --out /tmp/l2.json

# 复用已抓到的结果，不重跑网络
python3 skills/multi-search-engine/scripts/layered_search.py drill --in /tmp/l2.json --intents patent,product

# 71 条确定性测试，不需要网络
python3 skills/multi-search-engine/scripts/test_layered_search.py
```

## 目录结构

```
knowhow-skills/
├── install.sh
├── README.md
├── CHANGELOG.md
├── LICENSE.upstream-khazix
├── docs/
│   ├── WORKFLOW.md          # 各技能的交接契约、编排关系、迁移规则（接手套件先看这份）
│   ├── OPTIMIZATION.md      # 周期性优化机制与指标
│   └── content-harvester-design.md  # 规划中的「存得住」环节设计方案（v0.1，未实现）
└── skills/
    ├── multi-search-engine/ # 搜索层（v4.1，39 引擎 + 三层层级检索）
    ├── hv-analysis/         # 深度研究
    ├── khazix-writer/       # 长文写作
    ├── leader/              # 目标拆解
    ├── neat-freak/          # 知识收尾
    └── aihot/               # AI 资讯
```

## 许可与致谢

- 上游技能来自 [KKKKhazix/khazix-skills](https://github.com/KKKKhazix/khazix-skills)，MIT 许可，原始许可文本见 `LICENSE.upstream-khazix`。
- `multi-search-engine` 为本套件自有扩展版本（上游为 v3.0.0 / 17 引擎，本套件为 v4.0.0 / 39 引擎 + 分类 + 预设）。
- 各技能目录内若自带 `LICENSE`，以该文件为准。

## 安全说明

所有技能在纳入本套件前已做静态安全审计：无隐藏字符、无 base64 载荷、无提示词注入话术、无凭据外送。
`aihot/install.sh`（远程下载 + 执行）已从本套件移除，本套件统一用顶层 `install.sh` 本地复制安装。
