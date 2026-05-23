# 智筛 AI · AI 协作规范

> 本文件面向接手此项目的 AI（Claude 等）。读完此文件即可快速上手，无需再问用户基础问题。

---

## ⚠️ 强制工作规范（必须严格遵守）

### 1. 每次改动后必须 git push

每完成一个有意义的改动，必须：

```bash
git add <changed_files>
git commit -m "简洁描述改动"
git push
```

**原因**：项目部署在 Streamlit Cloud（`https://hr-demo-tencent.streamlit.app/`），push 后平台自动重新部署，用户才能在线看到效果。不 push = 用户看不到任何改动。

### 2. 每次改动后必须更新技术文档

改动涉及以下任一内容时，同步更新本文件（AGENTS.md）对应章节：

- 修改了某个文件的关键逻辑
- 修复了 Bug（在「已知 Bug 与修复记录」中追加）
- 改变了依赖、模型、API 配置
- 重构了某个模块

**原因**：对话上下文有限，跨会话时 AI 需要靠文档快速重建上下文，避免重复踩同样的坑。

---

## 项目概览

**智筛 AI** — 可信简历筛选系统，面向腾讯 AI-HR 方向组面（2026.05.25）演示用。

核心价值主张：**Trustworthy Screening（可信筛选）**，解决「HR 不敢用 AI 结果 + 候选人不服气 + 合规风险」三重矛盾。

### 两个版本

| 版本 | 文件 | 说明 |
|------|------|------|
| **纯前端版**（主交付物） | `demo.html` | 单文件，浏览器直接打开，无需安装，候选人数据全部内嵌，无真实 API 调用 |
| **Streamlit 全栈版** | `app.py` + 其他 `.py` | 真实 LLM 评分，SQLite 持久化，部署在 Streamlit Cloud |

演示优先用 `demo.html`；Streamlit 版用于展示「真实 AI 调用」能力。

---

## 文件结构

```
hr-demo/
├── app.py              # Streamlit 主应用，所有 UI Tab 逻辑
├── llm.py              # OpenRouter API 调用（Claude 评分）
├── data.py             # 候选人预设数据（10人，产品岗A-E + 后端岗F-J）
├── database.py         # SQLite 封装（overrides, pool, screenings 三张表）
├── utils.py            # build_resume_text() 等工具函数
├── demo.html           # 纯前端版（主交付物，React + Tailwind CDN）
├── requirements.txt    # Python 依赖
├── .streamlit/
│   ├── config.toml     # 主题配置（primaryColor=#3b82f6）
│   └── secrets.toml    # ⚠️ API Key，已加入 .gitignore，绝对不提交
├── AGENTS.md           # 本文件：AI 工作规范 + 技术导航
├── DESIGN_DOC.md       # 产品设计文档（~980字，面试用）
├── HANDOFF.md          # 项目交接文档（给人类读的概览）
└── SCRIPT.md           # 10分钟演示脚本
```

---

## 关键配置

### API Key（绝对不提交 git）

```toml
# .streamlit/secrets.toml（已在 .gitignore 中）
OPENROUTER_API_KEY = "sk-or-v1-..."
# OPENROUTER_MODEL = "anthropic/claude-3.5-haiku"  # 可选，默认见 llm.py
```

Streamlit Cloud 部署时在 App Settings → Secrets 粘贴同样内容。

### 当前使用模型

```python
# llm.py
DEFAULT_MODEL = "anthropic/claude-3.5-haiku"
```

> ⚠️ `anthropic/claude-3.5-sonnet` 已从 OpenRouter 下线（返回 404），不要使用。
> 可选替换：`anthropic/claude-sonnet-4.5`、`anthropic/claude-haiku-4.5`

### 部署地址

- **Streamlit Cloud**：`https://hr-demo-tencent.streamlit.app/`
- **GitHub Repo**：`https://github.com/ihcoaixnaug/hr-demo`

---

## app.py 架构速览

四个 Tab：

| Tab | 名称 | 关键函数 |
|-----|------|---------|
| Tab 1 | 规则构建 | `render_rule_builder()` |
| Tab 2 | 筛选工作台 | `render_screening()` |
| Tab 3 | 候选人视图 | `render_candidate_view()` |
| Tab 4 | 简历备选池 | `render_pool()` |

### 重要 session_state 键

| Key | 含义 |
|-----|------|
| `selected_cands` | Tab 2 当前勾选的候选人 ID 列表 |
| `chk_{cid}` | 每个候选人复选框的 widget state（必须与 selected_cands 同步） |
| `expand_{cid}` | 该候选人的「展开理由」是否打开 |
| `show_resume_{cid}` | 该候选人的「查看原始简历」弹窗是否打开 |
| `screening_done` | 是否已完成 AI 批量评分 |

### HTML 渲染注意事项

**必须用 `st.html()`，不能用 `st.markdown(unsafe_allow_html=True)`**

原因：Streamlit 的 markdown 解析器会破坏嵌套 flex div 结构，导致右侧分数/徽章区域以纯文本渲染。`st.html()`（Streamlit 1.31+）直接渲染 HTML，不经过 markdown 处理。

---

## database.py 表结构

```sql
-- 候选人 AI 评分结果
screenings(candidate_id, job_id, scores_json, reasons_json, ai_result, source, created_at)

-- HR 人工覆盖记录
overrides(candidate_id, job_id, result, note, created_at)

-- 备选池（跨岗位候选人）
pool(candidate_id, added_by, note, created_at)
```

---

## 已知 Bug 与修复记录

### Bug 1 — 全选按钮失效（已修复，commit `5070fcb`）

**现象**：点击「全选」后，重新渲染时候选人仍为未选中状态。

**根因**：`st.checkbox(value=..., key=f"chk_{cid}")` — Streamlit 在 key 存在后忽略 `value` 参数，以 widget 自身 state 为准。Toggle-all 只改了 `selected_cands` 列表，没有同步改每个 `session_state[f"chk_{cid}"]`，下一次 rerun 时 checkbox 全部返回 False，导致列表被清空。

**修复**：toggle-all handler 中同步设置每个 `session_state[f"chk_{cid}"] = True/False`。

---

### Bug 2 — 候选人卡片 HTML 以原始文本显示（已修复，commit `43afc88`）

**现象**：卡片右侧的徽章、分数区域显示为 `<div class="...">` 纯文本，维度分数栏显示乱码。

**根因**：使用 `st.markdown(..., unsafe_allow_html=True)` 时，markdown 解析器干扰了嵌套 flex div。

**修复**：全部改为 `st.html()`。影响范围：Tab 2 候选人主卡片、AI 理由块，Tab 3 候选人视图卡片、Demo 说明，Tab 4 备选池卡片。

---

### Bug 3 — API 调用全部失败，所有卡片显示「📋 预设数据」（已修复，commit `d594f8b`）

**现象**：即使配置了正确的 OPENROUTER_API_KEY，所有候选人仍显示预设数据标签。

**根因**：`DEFAULT_MODEL = "anthropic/claude-3.5-sonnet"` 已从 OpenRouter 下线，所有请求返回 404。异常被静默吞掉（`except Exception: return None`），导致无任何报错提示。

**修复**：
1. 改 `DEFAULT_MODEL = "anthropic/claude-3.5-haiku"`
2. 异常 handler 增加 `logging.warning(...)` 输出

---

### Bug 4 — UI 样式与 demo.html 差异明显（已修复，commit `d594f8b`）

**现象**：操作按钮为大号 `st.button` 列，HR 覆盖为下拉框，与原版 HTML 风格不匹配。

**根因**：初版实现直接用了 Streamlit 默认控件，未对齐 demo.html 的 Tailwind 紧凑风格。

**修复**：
- 操作行改为 `st.columns([1,1,1,4])` 紧凑布局，标签为「展开详细理由 ▼ / 查看原始简历 / ＋ 加入备选池」
- HR 覆盖改为三个横排 pill 按钮（强推进面试 / 待定 / 不推进），当前状态用 `type="primary"` 高亮

---

## demo.html 关键结构（纯前端版参考）

- 技术栈：React 18 + Babel（browser-mode，CDN）+ Tailwind CSS（CDN）
- 全部逻辑在 `<script type="text/babel">` 标签内
- 关键 state（在 `App` 组件）：`lockedDims`, `fingerprint`, `selectedJob`, `pool`, `overrides`
- `overrides` 已做状态提升：从 `ScreeningDashboard` 提升到 `App`，Tab 2 和 Tab 3 共享
- 候选人视图跨岗位维度：用 `JOB_PRESETS[c.job]?.dims`，不用 `activeDims`
- 备选池按钮条件：`finalResult === "不推进"`（判断最终结果，含 HR 覆盖后）
- 如需修改候选人数据：找 `const CANDIDATES = [...]`
- 如需新增岗位：找 `const JOB_PRESETS = {...}`

---

## 常用命令速查

```bash
# 本地启动 Streamlit
cd /Users/asyncgxc/Documents/hr-demo
source venv/bin/activate
streamlit run app.py

# 提交并推送（每次改动后必做）
git add app.py llm.py   # 按实际修改文件列出
git commit -m "描述"
git push

# 查看 OpenRouter 可用 Claude 模型
curl https://openrouter.ai/api/v1/models \
  -H "Authorization: Bearer $(cat .streamlit/secrets.toml | grep API_KEY | cut -d'"' -f2)" \
  | python3 -m json.tool | grep '"id"' | grep anthropic
```

---

### Bug 5 — Header logo 不可见（已修复，commit `ba8e89c`）

**现象**：「智筛 AI」logo 那一行在页面上完全看不见。

**根因**：`render_header()` 使用 `st.markdown()` 渲染嵌套 flex div，同 Bug 2 一样被 markdown 解析器破坏，导致整个 header div 高度坍缩为 0 或内容不可见。

**修复**：`render_header()` 改用 `st.html()`，header 设计为白色卡片样式（含 gradient logo icon + 阴影），脱离 Streamlit 原生 header 布局。

---

### Bug 6 — 岗位选择需两步点击（已修复，commit `ba8e89c`）

**现象**：规则构建页有 HTML 卡片（不可点击）+ 独立「选择XX岗」按钮两个元素，用户需要点击按钮才能加载，不符合 demo.html 的单击卡片体验。

**根因**：初始实现用 `st.markdown(_job_card())` 渲染视觉卡片，再加 `st.button("选择...岗")` 触发逻辑，两者分离。

**修复**：移除 HTML 卡片和 `_job_card()` 函数，改为 `st.button(f"🎯 产品经理实习生", type="primary"/"secondary")` + `st.caption()` 描述。选中态用 `type="primary"` 高亮，直接点击按钮即触发加载维度逻辑。

---

## UI 设计规范（Streamlit 版）

### 渲染方式

| 内容类型 | 用法 |
|---------|------|
| 纯文本、简单 inline HTML | `st.markdown(unsafe_allow_html=True)` |
| 含嵌套 flex/grid 的复杂 HTML 块 | **必须用 `st.html()`** |
| 互动元素（按钮、输入框等）| Streamlit 原生控件 |

### 颜色规范

| 用途 | 值 |
|-----|-----|
| 主色（按钮 primary）| 渐变 `#1d4ed8 → #111827` |
| 背景 | `#f3f4f6` |
| 卡片背景 | `white` |
| 边框 | `#e5e7eb` |
| 文字主色 | `#111827` |
| 文字次色 | `#6b7280` |
| 文字占位 | `#9ca3af` |

---

*最后更新：2026-05-23*
