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

五个 Tab：

| Tab | 名称 | 视角标签 | 关键函数 |
|-----|------|---------|---------|
| Tab 1 | 规则构建 | HR 视角 | `render_rule_builder()` |
| Tab 2 | 筛选工作台 | HR 视角 | `render_screening()` |
| Tab 3 | 候选人视图 | 候选人视角 | `render_candidate_view()` |
| Tab 4 | 简历备选池 | HR 视角 | `render_pool_view()` |
| Tab 5 | 规则验证 | 候选人视角 | `render_verification()` |

### Tab 2 专有功能

- **漏斗推算**：基于本批强推率推算全量 12000 份简历的到面人数（到面比 ≤8:1 绿色，>8 红色）
- **申诉管理面板**（`st.expander`，展开可见）：列出全部候选人提交的申诉，包含候选人姓名、质疑维度、补充证据，HR 可标记「已复核」或「驳回」

### Tab 3 专有功能

- **候选人切换按钮**：带颜色指示点（🟢强推/🟡待定/🔴不推进）+ 选中态 primary 样式，一目了然

### Tab 5 专有功能

- **离线演示模式**：无 API Key 时，可选择预设岗位（PM岗/Dev岗），跳过 AI 提取直接加载预设维度，继续完成权重调整 + 指纹生成演示

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
CREATE TABLE locked_rules (id, job_key, job_label, dims_json, fingerprint, locked_at, created_at)
CREATE TABLE screening_results (id, candidate_id, rule_id, scores_json, reasons_json, ai_result, source, created_at)
CREATE TABLE hr_overrides (id, candidate_id, rule_id, original_result, override_result, override_note, created_at)
CREATE TABLE talent_pool (id, candidate_id, from_job_label, added_at)
CREATE TABLE appeals (id, candidate_id, candidate_name, appeal_text, status DEFAULT 'pending', submitted_at)
```

关键函数（全部已在 `app.py` 中 import）：

| 函数 | 作用 |
|------|------|
| `save_appeal(cid, name, text)` | 候选人提交申诉 |
| `get_all_appeals()` | HR 查看所有申诉列表 |
| `update_appeal_status(id, status)` | HR 标记申诉为 reviewed / dismissed |
| `save_hr_override(cid, rule_id, orig, new, note)` | HR 覆盖留痕 |
| `get_screening_results(rule_id)` | 读取某规则下所有候选人评分 |

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

## LLM 调用清单

项目有两处独立的 LLM 调用（都在 `llm.py`）：

| 函数 | 触发时机 | 作用 | 失败处理 |
|------|---------|------|---------|
| `extract_dims_from_jd(jd, job_label)` | Rule Builder 点击岗位按钮时 | 从 JD 任职要求提取评估维度（每条要求 → 一个维度，1:1，不合并不增加） | 回退到 `data.py` 预设维度 |
| `screen_candidate_with_llm(candidate, dims, jd)` | 筛选工作台点击「开始筛选」时 | 按锁定维度对简历打分，返回各维度分数+理由+推荐结论 | 回退到 `data.py` 预设分数 |

### extract_dims_from_jd 关键 Prompt 规则

- 只读「任职要求」部分，每条 → 一个维度，顺序一致
- 维度 label：**直接从该条要求原文中摘取 2-6 汉字短语，不得改写或意译**（这是 hash 可信的基础）
- 维度 id：label 的英文简写，仅供内部使用，不参与 hash 计算
- 权重初始相等（总计 100%，余数加到最后一个）
- **禁止**合并多条要求 / 凭空增加维度
- 提取结果用于 Rule Builder 显示（供 HR 调整权重后锁定）；候选人在 Tab 5 验证时用同一函数重新提取

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

### 设计变更 — rule_fingerprint 改用 (label, weight)（commit `43ed96e`）

**原因**：`id` 是 AI 自动生成的英文 key（随机性高），不同次提取可能不同，导致候选人无法复现 hash。`label` 是直接从 JD 原文摘取的中文短语，复现性远高于 id。

**影响**：已锁定规则的 hash 会变（演示环境可接受）。生产环境切换时需重新锁定规则。

**不可回退**：如果将来需要再改 hash 算法，会破坏已有 hash 的可验证性，需谨慎。

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

---

### Bug 7 — 候选人评分晕轮效应，各维度分数趋同（已修复，commit `7fac0bb`）

**现象**：强候选人每个维度都偏高（如 A：85/80/86/86），弱候选人每个维度都偏低，各维度缺乏独立性，不反映真实情况。

**根因（两处）**：
1. `screen_candidate_with_llm` 的 prompt 未明确禁止晕轮效应，LLM 会受整体印象影响拉平各维度分数。
2. `data.py` 预设分数（兜底数据）本身也是趋同的（全高或全低），演示时看不出维度差异。

**修复**：
1. `llm.py` prompt 增加 `【严禁晕轮效应（Halo Effect）】` 段落：
   - 即使候选人整体很强，若某维度证据不足，该维度仍必须给低分
   - 增加 `【独立评分要求】`：各维度必须单独对照简历证据评分
   - 提示词：「如果你给出的所有维度分数都很接近，说明可能存在晕轮效应，请重新检查」
   - 更新评分档位（85-100/70-84/55-69/0-54）和推荐阈值（不推进 <55 或核心维度 <45）
2. `data.py` 预设分数全面重设，体现真实维度差异：
   - B（双非强推）：project:93，tech:92，但 **collab:68**（solo 项目为主）
   - F（双非强推）：problem:93（主动发现线上问题），但 **collab:68**（实习经历有限）
   - G（985硕士强推）：project:91，**collab:90**（跨职能协作最丰富），但 coding:82（偏中等）
   - J（自学强推）：problem:94（生产环境排查），但 **collab:58**（仅远程异步，无团队经历）
   - A（985本科强推）：communication:90（最佳表达），但 tech:76（数据分析深度一般）

---

### Bug 8 — 操作按钮文字截断 + 全面 UI 重设计（已修复，commit `e568b9c`）

**现象**：「展开详细理由 ▼」「查看原始简历」文字跑出按钮边界。

**根因**：`st.columns([1,1,1,4])` 按钮列宽仅约 110px，配合 `white-space:nowrap` 时文字超出列边界。

**修复**：
- 按钮标签缩短为「▼ 展开理由」「📄 原始简历」「＋ 备选池」
- 列宽改为 `[5,4,4,3]`（有备选池）或 `[5,4,7]`（无备选池），配合 `use_container_width=True`

**全面 UI 重设计**：
- CSS：多层阴影、渐变、`letter-spacing`、`-webkit-font-smoothing`
- Score bars：4 档颜色（green/blue/amber/red）渐变填充，数字带颜色
- 汇总 metrics：自定义 HTML 彩色卡片替换 `st.metric`
- 候选人卡片：`border-radius:16px`、`box-shadow`、scores 区域加分隔线
- AI 理由面板：白色卡片 + 标签 chip 设计
- 规则锁定卡：深色渐变（`#111827→#1e1b4b`）+ 绿色指纹大字
- 候选人视图：蓝色指纹区域、更清晰的 banner 布局
- Header：副标题改为英文 tagline

---

### Bug 9 — LLM 评分仍可读取院校名称（已修复，commit `da2a7b4`）

**现象**：`build_resume_text()` 将 `学校：{name}（不得用于评分）` 送给 LLM，仅靠 prompt 提示"不得使用"是无效控制。

**根因**：把答案放在 LLM 面前再说"别看"，无法从技术层面消除院校偏见。这与 demo 核心承诺直接冲突——候选人可凭「规则公开 + 院校不影响评分」主张反歧视权利。

**修复**：
- `utils.py build_resume_text()`：彻底移除院校名称，只保留「专业+GPA」（可观察事实）和经历正文
- `llm.py` 评分 prompt：告知 LLM「简历中已移除院校名称，你不会收到也不应推断」，强化禁止以学历层次、公司知名度代替事实证据

**设计原则**：
- 院校名 → 从技术上彻底隔离（LLM 看不到 = 不可能用）
- 机构名（字节跳动、某互联网公司等）→ 保留，属于经历事实的一部分
- 学历（本科/硕士/博士）→ LLM 可见，但 prompt 明确禁止用作评分依据

---

### 功能迭代记录（commit `latest`）— 6项UI优化

1. **Tab 5 离线兜底**：无 API Key 时不再直接 `return`，改为显示预设岗位选择按钮（PM岗/Dev岗），选后加载预设维度，后续的权重调整+指纹生成完全可用
2. **HR 申诉管理面板**：Tab 2 筛选工作台末尾新增 expander「📬 申诉管理面板」，读取 `appeals` 表，展示候选人姓名+质疑维度+补充证据，支持标记「已复核」/「驳回」（调用 `update_appeal_status()`）
3. **视角标签**：每个 Tab 标题旁加 `_role_badge("HR 视角")` 或 `_role_badge("候选人视角")` 彩色标签，demo 时听众一眼知道当前视角
4. **业务漏斗推算**：Tab 2 汇总栏下方新增一排，公式：`预计进入面试 = round(12000 × 强推率)`，`到面比 = 进入面试数 / 120`，颜色判断：≤8:1 绿色/>8:1 红色
5. **候选人切换器 UX**：Tab 3 选择器按钮带颜色点（🟢🟡🔴）+ 选中态 `type="primary"`，实时读取 screening_results 或预设 result 字段确定颜色
6. **预设数据模式横幅**：Tab 2 和 Tab 3 在无 API Key 时顶部显示明显的黄色 banner，不再只依赖 header 和单卡片的 `📋 预设数据` 小标签

新增辅助函数：`_role_badge(role)` 和 `_preset_mode_banner()`（均在 `app.py` 中 `_get_final()` 之后定义）

*最后更新：2026-05-23*
