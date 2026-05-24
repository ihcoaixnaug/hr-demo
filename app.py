# app.py — 智筛 AI · Streamlit（精美 UI 版，对齐原 demo.html 风格）

import copy
import time
from datetime import datetime

import streamlit as st

from data import JOB_PRESETS, CANDIDATES, CANDIDATES_MAP
from utils import rule_fingerprint, weighted_score, result_color, build_public_page_html
from database import (
    init_db, save_rule, get_all_rules,
    save_screening_result, get_screening_results,
    save_hr_override, get_hr_overrides,
    save_appeal, get_all_appeals, update_appeal_status,
)
from llm import screen_candidate_with_llm, extract_dims_from_jd, has_api_key

# ─── 页面基础配置 ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="智筛 AI · 可信简历筛选系统",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ─── 全局 CSS ─────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&display=swap');

/* ══ 设计 Token ═══════════════════════════════════════════════════════════ */
:root{
  --bg:        #F0F4FA;
  --surface:   #FFFFFF;
  --surface-2: #EEF2F8;
  --border:    #DDE5F0;
  --border-lt: #E6EEF8;
  --tx-1:      #1E293B;
  --tx-2:      #4F6580;
  --tx-3:      #94A9BC;

  /* trust blue 主色 */
  --mint:      #2563EB;
  --mint-lt:   #EFF4FF;
  --mint-md:   #93C5FD;
  --mint-dark: #1D4ED8;

  /* neumorphic 阴影 */
  --shadow-neo-sm: 4px 4px 10px rgba(30,41,59,.07),-2px -2px 6px rgba(255,255,255,.90);
  --shadow-neo-md: 6px 6px 16px rgba(30,41,59,.09),-3px -3px 9px rgba(255,255,255,.92);
  --shadow-neo-in: inset 2px 2px 5px rgba(30,41,59,.07),inset -2px -2px 5px rgba(255,255,255,.85);
  --shadow-sm: 0 1px 3px rgba(30,41,59,.07),0 1px 2px rgba(30,41,59,.04);
  --shadow-md: 0 4px 14px rgba(30,41,59,.09),0 2px 4px rgba(30,41,59,.05);
  --shadow-lg: 0 8px 28px rgba(30,41,59,.11),0 3px 8px rgba(30,41,59,.06);
  --spring:    cubic-bezier(0.34,1.56,0.64,1);
  --smooth:    cubic-bezier(0.4,0,0.2,1);
  --ease-out:  cubic-bezier(0,0,0.2,1);
  --r-pill:    999px;
  --r-card:    20px;
  --r-sm:      12px;
}

/* ══ 动效关键帧 ═══════════════════════════════════════════════════════════ */
@keyframes fadeUp{
  from{opacity:0;transform:translateY(18px);}
  to{opacity:1;transform:translateY(0);}
}
@keyframes springIn{
  0%  {opacity:0;transform:scale(.93) translateY(12px);}
  55% {transform:scale(1.018) translateY(-2px);}
  100%{opacity:1;transform:scale(1) translateY(0);}
}
@keyframes popIn{
  0%  {opacity:0;transform:scale(.82);}
  58% {transform:scale(1.07);}
  100%{opacity:1;transform:scale(1);}
}
@keyframes shimmer{
  0%,100%{opacity:.7;}50%{opacity:1;}
}

/* ══ 基础重置 ══════════════════════════════════════════════════════════════ */
html,body,[class*="css"]{
  font-family:"Plus Jakarta Sans","PingFang SC",BlinkMacSystemFont,
    "Segoe UI",sans-serif!important;
  -webkit-font-smoothing:antialiased!important;
}
.stApp{background:var(--bg)!important;}
.stMainBlockContainer,.block-container{
  max-width:940px!important;
  margin:0 auto!important;
  padding:28px 24px 120px!important;
}

/* ══ 隐藏 Streamlit chrome ══════════════════════════════════════════════════ */
#MainMenu,footer,.stDeployButton{display:none!important;}
[data-testid="stToolbar"]{display:none!important;}
header[data-testid="stHeader"]{display:none!important;}

/* ══ Tab 导航 ══════════════════════════════════════════════════════════════ */
.stTabs [data-baseweb="tab-list"]{
  background:var(--surface)!important;
  border:1px solid var(--border)!important;
  border-radius:var(--r-pill)!important;
  padding:5px!important;
  gap:3px!important;
  box-shadow:var(--shadow-neo-sm)!important;
  margin-bottom:10px!important;
  display:flex!important;
  width:100%!important;
}
.stTabs [data-baseweb="tab"]{
  background:transparent!important;
  color:var(--tx-2)!important;
  font-size:13px!important;
  font-weight:500!important;
  padding:8px 16px!important;
  border-radius:var(--r-pill)!important;
  margin:0!important;
  transition:all .26s var(--spring)!important;
  white-space:nowrap!important;
  flex:1!important;
  justify-content:center!important;
  display:flex!important;
}
.stTabs [aria-selected="true"]{
  color:#fff!important;
  background:var(--mint)!important;
  font-weight:700!important;
  box-shadow:0 2px 8px rgba(37,99,235,.35),0 1px 3px rgba(37,99,235,.25)!important;
}
.stTabs [data-baseweb="tab"]:hover:not([aria-selected="true"]){
  color:var(--tx-1)!important;
  background:var(--mint-lt)!important;
}
.stTabs [data-baseweb="tab-highlight"]{display:none!important;}
.stTabs [data-baseweb="tab-border"]{display:none!important;}
.stTabs [data-baseweb="tab-panel"]{padding:18px 0 0!important;}

/* ══ Primary 按钮 — pill + mint ═══════════════════════════════════════════ */
.stButton>button[kind="primary"]{
  background:var(--mint)!important;
  color:#fff!important;
  border:none!important;
  border-radius:var(--r-pill)!important;
  font-size:14px!important;
  font-weight:600!important;
  padding:10px 28px!important;
  letter-spacing:.01em!important;
  box-shadow:0 3px 10px rgba(37,99,235,.32),0 1px 3px rgba(37,99,235,.20)!important;
  transition:all .30s var(--spring)!important;
  white-space:nowrap!important;
}
.stButton>button[kind="primary"]:hover:not(:disabled){
  background:var(--mint-dark)!important;
  color:#fff!important;
  box-shadow:0 6px 22px rgba(37,99,235,.40),0 2px 6px rgba(37,99,235,.22)!important;
  transform:translateY(-2px) scale(1.01)!important;
}
.stButton>button[kind="primary"]:active:not(:disabled){
  transform:translateY(0) scale(.97)!important;
  color:#fff!important;
  box-shadow:0 1px 4px rgba(37,99,235,.25)!important;
}

/* ══ Secondary / 默认按钮 — pill + neo shadow ══════════════════════════════ */
.stButton>button{
  border-radius:var(--r-pill)!important;
  font-size:13px!important;
  font-weight:500!important;
  padding:7px 18px!important;
  border:1px solid var(--border)!important;
  color:var(--tx-1)!important;
  background:var(--surface)!important;
  box-shadow:var(--shadow-neo-sm)!important;
  transition:all .26s var(--spring)!important;
  white-space:nowrap!important;
  overflow:visible!important;
}
.stButton>button:hover:not(:disabled){
  border-color:var(--mint-md)!important;
  background:var(--mint-lt)!important;
  color:var(--mint-dark)!important;
  box-shadow:var(--shadow-neo-md)!important;
  transform:translateY(-1px)!important;
}
.stButton>button:active:not(:disabled){
  transform:translateY(0) scale(.97)!important;
  box-shadow:var(--shadow-neo-in)!important;
}
.stButton>button:disabled{opacity:.38!important;cursor:not-allowed!important;}

/* ══ Slider — mint ════════════════════════════════════════════════════════ */
[data-testid="stSlider"] [role="slider"]{
  background:var(--mint)!important;
  box-shadow:0 0 0 3px rgba(37,99,235,.20)!important;
}
[data-testid="stSlider"] [data-testid="stSliderThumbValue"]{
  background:var(--mint)!important;color:#fff!important;
  font-family:monospace!important;font-size:11px!important;
  border-radius:var(--r-pill)!important;
}
[data-testid="stSlider"] > div > div > div > div{
  background:var(--mint)!important;
  border-radius:999px!important;
}
[data-testid="stSlider"] label{font-size:13px!important;font-weight:500!important;color:var(--tx-1)!important;}

/* ══ Input / Textarea — rounded + inset neo ════════════════════════════════ */
.stTextInput input,.stTextArea textarea{
  border-radius:14px!important;
  border:1.5px solid var(--border)!important;
  font-size:13.5px!important;
  color:var(--tx-1)!important;
  background:var(--surface)!important;
  box-shadow:var(--shadow-neo-in)!important;
  transition:border-color .2s var(--smooth),box-shadow .2s var(--smooth)!important;
}
.stTextInput input:focus,.stTextArea textarea:focus{
  border-color:var(--mint-md)!important;
  box-shadow:var(--shadow-neo-in),0 0 0 3px rgba(37,99,235,.14)!important;
  outline:none!important;
}
.stTextArea label,.stTextInput label{
  font-size:12px!important;color:var(--tx-2)!important;font-weight:500!important;
}

/* ══ Checkbox ══════════════════════════════════════════════════════════════ */
.stCheckbox label{font-size:13.5px!important;color:var(--tx-1)!important;}
.stCheckbox [data-testid="stCheckbox"]:hover label{color:var(--mint-dark)!important;}

/* ══ Metric 卡片 ══════════════════════════════════════════════════════════ */
[data-testid="metric-container"]{
  background:var(--surface)!important;
  border:1px solid var(--border)!important;
  border-radius:var(--r-card)!important;
  padding:20px 22px!important;
  box-shadow:var(--shadow-sm)!important;
  transition:box-shadow .28s var(--spring),transform .28s var(--spring)!important;
  animation:fadeUp .5s var(--ease-out) both!important;
}
[data-testid="metric-container"]:hover{
  box-shadow:var(--shadow-md)!important;
  transform:translateY(-2px)!important;
}
[data-testid="stMetricValue"]{
  font-size:26px!important;font-weight:800!important;
  color:var(--tx-1)!important;letter-spacing:-.02em!important;
}
[data-testid="stMetricLabel"]{
  font-size:11.5px!important;color:var(--tx-3)!important;
  font-weight:500!important;text-transform:uppercase!important;
  letter-spacing:.05em!important;
}

/* ══ Alerts ══════════════════════════════════════════════════════════════ */
.stAlert{border-radius:var(--r-card)!important;font-size:13px!important;}

/* ══ Expander ══════════════════════════════════════════════════════════════ */
.stExpander{
  border:1px solid var(--border)!important;
  border-radius:var(--r-card)!important;
  background:var(--surface)!important;
  box-shadow:var(--shadow-sm)!important;
  overflow:hidden!important;
  transition:box-shadow .26s var(--spring)!important;
}
.stExpander:hover{box-shadow:var(--shadow-md)!important;}
.stExpander summary{
  font-size:13px!important;font-weight:600!important;color:var(--tx-1)!important;
  padding:13px 16px!important;
}
.stExpander summary:hover{background:var(--mint-lt)!important;}

/* ══ Border container ══════════════════════════════════════════════════════ */
div[data-testid="stVerticalBlockBorderWrapper"]{
  border-radius:var(--r-card)!important;
  box-shadow:var(--shadow-sm)!important;
  border:1px solid var(--border)!important;
  background:var(--surface)!important;
  transition:box-shadow .26s var(--spring)!important;
}
div[data-testid="stVerticalBlockBorderWrapper"]:hover{
  box-shadow:var(--shadow-md)!important;
}

/* ══ Progress bar — mint ══════════════════════════════════════════════════ */
[data-testid="stProgress"] > div > div{
  background:var(--mint)!important;
  border-radius:999px!important;
  transition:width .4s var(--ease-out)!important;
}

/* ══ 全局间距 ══════════════════════════════════════════════════════════════ */
.element-container{margin-bottom:6px!important;}
div[data-testid="stVerticalBlock"]>div{gap:8px!important;}

/* ══ 列容器不裁切子元素（防止 pill 按钮圆角被 overflow:hidden 裁掉） ══════ */
[data-testid="column"]{
  overflow:visible!important;
}
[data-testid="column"] .element-container{
  overflow:visible!important;
}

/* ══ 候选人卡片操作按钮行：确保文字不截断 ═══════════════════════════════════ */
.cand-action-btn .stButton>button{
  font-size:12.5px!important;
  padding:6px 10px!important;
  min-width:0!important;
  width:100%!important;
}

/* ══ Divider ══════════════════════════════════════════════════════════════ */
hr{border:none!important;border-top:1px solid var(--border-lt)!important;margin:10px 0!important;}

/* ══ Caption ══════════════════════════════════════════════════════════════ */
.stCaption,.stCaption p{
  font-size:12px!important;color:var(--tx-3)!important;line-height:1.5!important;
}

/* ══ 隐藏 textarea 的 ⌘+Enter 提示 ══════════════════════════════════════ */
[data-testid="InputInstructions"]{display:none!important;}

/* ══ 卡片入场动效 — 错落节奏 ════════════════════════════════════════════════ */
.stHtml:nth-child(1){animation:fadeUp .38s var(--ease-out) .04s both;}
.stHtml:nth-child(2){animation:fadeUp .38s var(--ease-out) .08s both;}
.stHtml:nth-child(3){animation:fadeUp .38s var(--ease-out) .12s both;}
.stHtml:nth-child(4){animation:fadeUp .38s var(--ease-out) .16s both;}
.stHtml:nth-child(5){animation:fadeUp .38s var(--ease-out) .20s both;}
.stHtml:nth-child(6){animation:fadeUp .38s var(--ease-out) .23s both;}
.stHtml:nth-child(7){animation:fadeUp .38s var(--ease-out) .26s both;}
.stHtml:nth-child(8){animation:fadeUp .38s var(--ease-out) .28s both;}

/* ══ 卡片悬停升浮 ════════════════════════════════════════════════════════ */
.zh-card{
  transition:box-shadow .26s var(--spring),transform .26s var(--spring)!important;
}
.zh-card:hover{
  box-shadow:var(--shadow-md)!important;
  transform:translateY(-2px)!important;
}

/* ══ 数字等宽 ════════════════════════════════════════════════════════════ */
.zh-num{
  font-variant-numeric:tabular-nums;
  font-feature-settings:"tnum";
}

/* ══ Markdown 内容区排版 ═════════════════════════════════════════════════ */
.stMarkdown p{
  font-size:14px!important;
  line-height:1.7!important;
  /* color 不加 !important，让内联 style 可以正常覆盖（否则深色卡片内文字变黑不可见） */
  color:var(--tx-1);
}
</style>
""", unsafe_allow_html=True)


# ─── Session State 初始化 ─────────────────────────────────────────────────────
def _init():
    defs = {
        # ─ 多岗位锁定状态 ──────────────────────────────────────────────────────
        "locked_jobs":       {},    # {job_key: {dims, fingerprint, locked_at, rule_id, label}}
        "active_job":        None,  # 筛选工作台当前查看的岗位 key
        # ─ 规则构建（构建中状态）───────────────────────────────────────────────
        "selected_job":      None,
        "editing_dims":      None,
        # ─ 筛选结果（候选人 ID 全局唯一，无需按岗位分桶）────────────────────────
        "screening_results": {},
        "overrides":         {},
        "selected_cands":    [],
        # ─ 其他 ──────────────────────────────────────────────────────────────
        "appeal_submitted":  set(),
        "hiring_target":     120,
        "goto_tab":          -1,
        "cv_selected":       "",
        "_db_restored":      False,  # 防止每次 rerun 都重复读库
    }
    for k, v in defs.items():
        if k not in st.session_state:
            st.session_state[k] = v

_init()
init_db()

# ─── 从数据库恢复 locked_jobs + screening_results（仅首次加载执行一次）────────
if not st.session_state._db_restored:
    import json as _json
    _all_rules = get_all_rules()
    # 每个岗位只取最新一条规则
    _latest: dict[str, dict] = {}
    for _r in _all_rules:
        _jk = _r["job_key"]
        if _jk not in _latest:
            _latest[_jk] = _r
    for _jk, _r in _latest.items():
        if _jk not in st.session_state.locked_jobs:
            st.session_state.locked_jobs[_jk] = {
                "dims":        _json.loads(_r["dims_json"]),
                "fingerprint": _r["fingerprint"],
                "locked_at":   _r["created_at"],
                "rule_id":     _r["id"],
                "label":       _r["job_label"],
            }
        # 恢复该规则对应的筛选结果
        _saved = get_screening_results(_r["id"])
        st.session_state.screening_results.update(_saved)
    if not st.session_state.active_job and st.session_state.locked_jobs:
        st.session_state.active_job = list(st.session_state.locked_jobs.keys())[0]
    st.session_state._db_restored = True



# ─── HTML 辅助函数 ────────────────────────────────────────────────────────────

COLOR_MAP = {
    "green":  {"bg":"#F2FBF4","border":"#A7D9B3","badge_bg":"#DDF3E4","badge_text":"#166534","accent":"#22C55E","top":"#4ADE80"},
    "yellow": {"bg":"#FFFBEB","border":"#F5D87A","badge_bg":"#FEF3C7","badge_text":"#92400E","accent":"#F59E0B","top":"#FCD34D"},
    "red":    {"bg":"#FEF4F4","border":"#F5B8B8","badge_bg":"#FEE2E2","badge_text":"#991B1B","accent":"#EF4444","top":"#FCA5A5"},
}
TAG_COLOR = {
    "985":  ("bg:#F0EDF8","color:#5B21B6"),
    "211":  ("bg:#EEF2F8","color:#2D4A7A"),
    "双非": ("bg:#EEF2F8","color:#475569"),
    "职校": ("bg:#FEF5EC","color:#B45309"),
    "自学": ("bg:#EEF6EE","color:#1A5C2A"),
}
DEGREE_COLOR = {
    "本科": ("bg:#EEF2F8","color:#2D4A7A"),
    "硕士": ("bg:#F3EFF8","color:#5B35A0"),
    "博士": ("bg:#F8EEF5","color:#8B2088"),
    "大专": ("bg:#FEF5EC","color:#B45309"),
    "高中": ("bg:#EEF6EE","color:#1A5C2A"),
}

def _tag(tag: str) -> str:
    bg, color = TAG_COLOR.get(tag, ("bg:#f3f4f6","color:#4b5563"))
    return (f'<span style="{bg};{color};border-radius:999px;'
            f'padding:2px 8px;font-size:12px;font-weight:600;">{tag}</span>')

def _degree_tag(degree: str) -> str:
    bg, color = DEGREE_COLOR.get(degree, ("bg:#f3f4f6","color:#4b5563"))
    return (f'<span style="{bg};{color};border-radius:999px;'
            f'padding:2px 8px;font-size:12px;font-weight:600;">{degree}</span>')

def _badge(result: str) -> str:
    c = COLOR_MAP[result_color(result)]
    return (f'<span style="background:{c["badge_bg"]};color:{c["badge_text"]};'
            f'border-radius:999px;padding:3px 12px;font-size:12px;font-weight:700;">'
            f'{result}</span>')

def _bars(scores: dict, dims: list) -> str:
    rows = []
    for d in dims:
        v = scores.get(d["id"], 0)
        if v >= 80:
            bar_color = "linear-gradient(to right,#4ADE80,#22C55E)"
            num_color = "#166534"
        elif v >= 65:
            bar_color = "linear-gradient(to right,#86EFAC,#4ADE80)"
            num_color = "#1A5C2A"
        elif v >= 50:
            bar_color = "linear-gradient(to right,#FCD34D,#F59E0B)"
            num_color = "#92400E"
        else:
            bar_color = "linear-gradient(to right,#FCA5A5,#F87171)"
            num_color = "#991B1B"
        rows.append(f"""
<div style="display:grid;grid-template-columns:8rem 1fr 2.2rem;gap:8px;
            align-items:center;margin-bottom:8px;">
  <span style="font-size:12px;color:#475569;white-space:nowrap;">
    {d["label"]}<span style="color:#C4BCB2;font-size:11px;margin-left:3px;">{d["weight"]}%</span>
  </span>
  <div style="background:#EEF2F8;border-radius:999px;height:6px;overflow:hidden;">
    <div style="width:{v}%;height:6px;background:{bar_color};
                border-radius:999px;transition:width .6s cubic-bezier(0,0,.2,1);"></div>
  </div>
  <span style="font-family:'SF Mono',ui-monospace,monospace;font-size:12px;
               font-weight:700;color:{num_color};text-align:right;">{v}</span>
</div>""")
    return "".join(rows)

def _get_final(cid: str, ai_result: str):
    ov = st.session_state.overrides.get(cid)
    if ov and ov.get("result"):
        return ov["result"], True
    return ai_result, False


def _role_badge(role: str) -> str:
    """渲染视角标签：HR视角 / 候选人视角"""
    cfg = {
        "HR 视角":   ("#EEF2F8", "#2D4A7A", "#C8D4E8", "👔"),
        "候选人视角": ("#EEF6EE", "#1A5C2A", "#A7D9B3", "🎓"),
    }
    bg, tc, border, icon = cfg.get(role, ("#EEF2F8", "#475569", "#C8D8EA", "👤"))
    return (
        f'<span style="background:{bg};color:{tc};border:1px solid {border};'
        f'border-radius:999px;padding:3px 12px;font-size:12px;font-weight:600;">'
        f'{icon} {role}</span>'
    )


def _preset_mode_banner() -> str:
    """当无 API Key 时显示的预设数据模式顶部提示条。"""
    return """
<div style="background:#fffbeb;border:1.5px solid #fde68a;border-radius:12px;
            padding:12px 18px;margin-bottom:16px;
            display:flex;align-items:center;gap:10px;font-size:13px;color:#92400e;">
  <span style="font-size:18px;">📋</span>
  <div>
    <strong>预设数据模式</strong> — 未配置 API Key，以下展示内容均为预先编排的演示数据。<br/>
    <span style="font-size:12px;color:#b45309;">配置 OPENROUTER_API_KEY 后可切换为 Claude 真实评分模式。</span>
  </div>
</div>"""


# ─── 弹窗（Dialogs） ──────────────────────────────────────────────────────────
@st.dialog("📋 规则公示", width="small")
def _public_page_dialog(dims: list, fp: str, locked_at: str, job_label: str):
    st.caption(f"腾讯 · {job_label} · 2026届秋招")
    st.markdown(
        f'<div style="background:#f9fafb;border:1px solid #e5e7eb;border-radius:10px;padding:12px 14px;margin-bottom:12px">'
        f'<p style="font-size:11px;color:#9ca3af;text-transform:uppercase;letter-spacing:.06em;margin:0 0 4px">Rule Hash · 规则指纹</p>'
        f'<p style="font-family:monospace;font-size:18px;font-weight:700;color:#111;letter-spacing:.15em;margin:0">{fp}</p>'
        f'<p style="font-size:11px;color:#9ca3af;margin:6px 0 0">候选人可对比投递确认邮件中的指纹，一致则规则未被修改</p>'
        f'</div>',
        unsafe_allow_html=True,
    )
    rows = "".join(
        f'<tr><td style="padding:8px 12px;border-bottom:1px solid #f3f4f6;font-size:13px;color:#374151">{d["label"]}</td>'
        f'<td style="padding:8px 12px;border-bottom:1px solid #f3f4f6;font-size:13px;color:#6b7280;text-align:right">{d["weight"]}%</td></tr>'
        for d in dims
    )
    st.markdown(
        f'<table style="width:100%;border-collapse:collapse;border:1px solid #e5e7eb;border-radius:8px;overflow:hidden;margin-bottom:10px">'
        f'<thead><tr>'
        f'<th style="padding:8px 12px;background:#f9fafb;font-size:11px;color:#9ca3af;text-align:left;font-weight:600;text-transform:uppercase;letter-spacing:.05em">维度</th>'
        f'<th style="padding:8px 12px;background:#f9fafb;font-size:11px;color:#9ca3af;text-align:right;font-weight:600;text-transform:uppercase;letter-spacing:.05em">权重</th>'
        f'</tr></thead><tbody>{rows}</tbody></table>',
        unsafe_allow_html=True,
    )
    # 锁定时间 + 状态徽章
    if locked_at:
        st.markdown(
            f'<div style="font-size:12px;color:#9ca3af;margin-bottom:6px;">'
            f'锁定时间：<span style="color:#374151;font-weight:500;">{locked_at}</span>'
            f'&nbsp;&nbsp;'
            f'<span style="display:inline-block;background:#f0fdf4;color:#16a34a;'
            f'border:1px solid #bbf7d0;border-radius:20px;font-size:11px;'
            f'padding:2px 10px;font-weight:600;">已锁定 · 不可修改</span>'
            f'</div>',
            unsafe_allow_html=True,
        )
    # 只读说明
    st.markdown(
        '<div style="background:#fffbeb;border:1px solid #fde68a;border-radius:8px;'
        'padding:10px 14px;font-size:12px;color:#92400e;margin-bottom:10px;">'
        '⚠ 本页面为只读公示，规则自锁定后不可更改。'
        '如对评估结果有异议，请通过候选人系统提交申诉。'
        '</div>',
        unsafe_allow_html=True,
    )
    html = build_public_page_html(dims, fp, locked_at, job_label)
    st.download_button("⬇ 下载完整公示页 HTML", data=html,
                       file_name="rule_public_page.html", mime="text/html")


@st.dialog("📋 岗位 JD", width="small")
def _jd_dialog(label: str, jd: str):
    st.caption(label)
    st.code(jd, language=None)


@st.dialog("📄 原始简历", width="small")
def _resume_dialog(cand: dict):
    resume = cand["resume"]
    st.markdown(
        f"**{cand['name']}** &nbsp;·&nbsp; {cand['school']} &nbsp;·&nbsp; "
        f"{cand['major']} &nbsp;·&nbsp; {cand['tag']}"
    )
    st.caption(f"GPA {resume.get('gpa','—')} · {resume.get('period','')}")
    st.divider()
    for exp in resume.get("experiences", []):
        c_et, c_ep = st.columns([3, 1])
        with c_et:
            st.markdown(f"**{exp['title']}**")
            st.caption(exp["org"])
        with c_ep:
            st.caption(exp["period"])
        for b in exp.get("bullets", []):
            st.markdown(f"&nbsp;&nbsp;· {b}")
        st.markdown("")
    st.markdown(f"🛠 **技能** {resume.get('skills','')}")
    aw = resume.get("awards", "")
    if aw and aw != "无":
        st.markdown(f"🏆 **奖项** {aw}")


# ─── Header ───────────────────────────────────────────────────────────────────
def render_header():
    badges_html = ""
    for _jk, _js in st.session_state.locked_jobs.items():
        badges_html += (
            f'<span style="background:#111827;color:#fff;border-radius:999px;'
            f'padding:3px 10px;font-size:12px;margin-left:8px;">'
            f'🔒 {_js["label"]}</span>'
        )
    if not has_api_key():
        badges_html += (
            '<span style="background:#fef3c7;color:#92400e;border-radius:999px;'
            'padding:3px 10px;font-size:12px;margin-left:6px;">⚠ 预设数据模式</span>'
        )

    st.html(f"""
<div style="display:flex;align-items:center;justify-content:space-between;gap:12px;
            padding:0 0 20px;border-bottom:1px solid #DDE5F0;margin-bottom:20px;">
  <div style="display:flex;align-items:center;gap:13px;">
    <div style="width:36px;height:36px;flex-shrink:0;background:#1A1714;
                border-radius:10px;display:flex;align-items:center;justify-content:center;">
      <span style="color:#FEFCF9;font-weight:900;font-size:15px;letter-spacing:-.5px;">智</span>
    </div>
    <div>
      <div style="font-weight:800;font-size:17px;color:#1A1714;letter-spacing:-.03em;
                  line-height:1.1;">智筛 AI</div>
      <div style="font-size:11px;color:#94A9BC;letter-spacing:.04em;margin-top:1px;">
        TRUSTWORTHY SCREENING</div>
    </div>
  </div>
  <div style="display:flex;align-items:center;gap:6px;flex-wrap:wrap;justify-content:flex-end;">
    {badges_html}
  </div>
</div>
""")


# ─── Page 1：规则构建 ─────────────────────────────────────────────────────────
def render_rule_builder():
    locked_jobs = st.session_state.locked_jobs

    # ══ 已锁定岗位卡片区 ════════════════════════════════════════════════════════
    if locked_jobs:
        for jk_l, js in locked_jobs.items():
            preset_l = JOB_PRESETS[jk_l]
            jl_l = js["label"]
            fp_l = js["fingerprint"]
            at_l = js["locked_at"]
            dims_l = js["dims"]
            dim_chips = "".join(
                f'<span style="background:rgba(255,255,255,.10);border:1px solid rgba(255,255,255,.15);'
                f'border-radius:8px;padding:3px 10px;font-size:12px;color:#e5e7eb;'
                f'font-weight:500;margin-right:6px;margin-bottom:6px;display:inline-block;">'
                f'{d["label"]} <span style="color:#6ee7b7;font-weight:700;">{d["weight"]}%</span></span>'
                for d in dims_l
            )
            st.markdown(f"""
<div style="background:linear-gradient(160deg,#1C1B18 0%,#2D2825 100%);
            border-radius:24px;padding:24px 26px;color:#FFFFFF;margin-bottom:0;
            box-shadow:6px 6px 20px rgba(30,41,59,.18),-2px -2px 8px rgba(255,255,255,.06);">
  <div style="display:flex;align-items:center;gap:10px;margin-bottom:4px;">
    <span style="font-size:16px;">🔒</span>
    <span style="font-size:15px;font-weight:700;letter-spacing:-.01em;">{jl_l} · 规则已锁定 · 不可修改</span>
  </div>
  <p style="font-size:12px;color:#C8C4BE;margin:0 0 18px;">锁定时间：{at_l}</p>
  <div style="background:rgba(110,231,183,.08);border:1px solid rgba(110,231,183,.2);
              border-radius:12px;padding:16px 18px;margin-bottom:16px;">
    <p style="font-size:11px;color:#C8C4BE;margin:0 0 8px;text-transform:uppercase;
               letter-spacing:.06em;font-weight:600;">RULE HASH · 规则指纹</p>
    <span style="font-family:'SF Mono',ui-monospace,monospace;font-size:26px;
                 color:#6ee7b7;font-weight:900;letter-spacing:.2em;">{fp_l}</span>
    <p style="font-size:11.5px;color:#C8C4BE;margin:8px 0 0;line-height:1.5;">
      规则内容改变则指纹随之改变 · 候选人可使用相同 JD 独立验证
    </p>
  </div>
  <div style="font-size:12px;color:#C8C4BE;margin-bottom:12px;display:flex;align-items:center;gap:6px;">
    <span>🔗</span>
    <span>规则已同步公示页，候选人收到的投递确认邮件含本指纹</span>
  </div>
  <div style="display:flex;flex-wrap:wrap;">{dim_chips}</div>
</div>
""", unsafe_allow_html=True)

            st.markdown('<div style="margin-top:-10px;"></div>', unsafe_allow_html=True)
            _ca, _cb, _cc = st.columns([1, 1, 1], vertical_alignment="center")
            with _ca:
                if st.button(f"📋 查看岗位 JD", key=f"jd_btn_{jk_l}",
                             use_container_width=True):
                    _jd_dialog(jl_l, preset_l["jd"])
            with _cb:
                if st.button("📄 查看规则公示页", key=f"open_pub_{jk_l}",
                             use_container_width=True):
                    _public_page_dialog(dims_l, fp_l, at_l, jl_l)
            with _cc:
                if st.button("🗑 清除规则", key=f"reset_job_{jk_l}",
                             use_container_width=True):
                    del st.session_state.locked_jobs[jk_l]
                    if st.session_state.active_job == jk_l:
                        st.session_state.active_job = None
                    st.session_state.selected_job  = None
                    st.session_state.editing_dims  = None
                    st.rerun()
            st.markdown('<div style="height:10px;"></div>', unsafe_allow_html=True)

        if len(locked_jobs) >= len(JOB_PRESETS):
            st.html('<div style="background:#f0fdf4;border:1px solid #86efac;border-radius:12px;'
                    'padding:14px 18px;font-size:13px;color:#166534;text-align:center;margin-top:4px;">'
                    '✅ 所有岗位规则均已锁定，前往「📊 筛选工作台」按岗位切换处理。</div>')
            return

        st.markdown("---")

    # ══ 规则构建 UI ══════════════════════════════════════════════════════════
    st.html(f"""
<div style="margin-bottom:20px;">
  <div style="display:flex;align-items:center;gap:10px;margin-bottom:6px;">
    <h2 style="font-size:22px;font-weight:800;color:#111827;margin:0;">规则构建</h2>
    {_role_badge("HR 视角")}
  </div>
  <p style="font-size:14px;color:#6b7280;margin:0;">
    选择招募岗位，AI 自动加载评估维度，确认后一键锁定并生成公示指纹
  </p>
</div>""")

    # 岗位选择（单击即加载）
    st.html('<p style="font-size:14px;font-weight:600;color:#374151;margin:0 0 10px;">选择招募岗位</p>')

    def _load_job(key):
        p = JOB_PRESETS[key]
        st.session_state.selected_job = key
        # ── AI 提取：每条任职要求 → 一个维度 ──────────────────────────────────
        extracted = None
        if has_api_key():
            with st.spinner("AI 正在从 JD 任职要求提取评估维度…"):
                extracted, _err = extract_dims_from_jd(p["jd"], p["label"])
        dims = extracted if extracted else copy.deepcopy(p["dims"])
        st.session_state.editing_dims = dims
        for d in dims:
            st.session_state[f"w_{d['id']}"] = d["weight"]
        if extracted:
            st.session_state["dims_from_ai"] = True
        else:
            st.session_state["dims_from_ai"] = False
        st.rerun()

    c1, c2 = st.columns(2)
    with c1:
        pm = JOB_PRESETS["pm"]
        pm_sel = st.session_state.selected_job == "pm"
        pm_done = "pm" in locked_jobs
        if st.button(
            f"🎯  {pm['label']}" + (" ✓ 已锁定" if pm_done else ""),
            key="sel_pm",
            use_container_width=True,
            type="primary" if pm_sel else "secondary",
            disabled=pm_done,
        ):
            _load_job("pm")
        st.caption(pm["desc"])
    with c2:
        dev = JOB_PRESETS["dev"]
        dev_sel = st.session_state.selected_job == "dev"
        dev_done = "dev" in locked_jobs
        if st.button(
            f"⚙️  {dev['label']}" + (" ✓ 已锁定" if dev_done else ""),
            key="sel_dev",
            use_container_width=True,
            type="primary" if dev_sel else "secondary",
            disabled=dev_done,
        ):
            _load_job("dev")
        st.caption(dev["desc"])

    jk = st.session_state.selected_job
    if not jk:
        st.markdown('<p style="font-size:13px;color:#9ca3af;margin-top:10px;">👆 请先选择岗位，系统自动加载对应的评估维度</p>', unsafe_allow_html=True)
        return

    preset    = JOB_PRESETS[jk]
    edit_dims = st.session_state.editing_dims or copy.deepcopy(preset["dims"])
    st.session_state.editing_dims = edit_dims

    dims_from_ai = st.session_state.get("dims_from_ai", False)
    if dims_from_ai:
        st.html(f"""
<div style="display:flex;align-items:center;gap:8px;
            background:#F0F4FA;border:1px solid #C8D8EA;border-radius:10px;
            padding:10px 14px;margin:16px 0 8px;font-size:13px;color:#3D3A36;">
  <span style="font-size:15px;">🤖</span>
  <span>AI 已从「<strong>{preset["label"]}」JD 任职要求</strong>提取维度（每条要求对应一个维度），可调整权重后锁定</span>
</div>""")
    else:
        st.html(f"""
<div style="display:flex;align-items:center;gap:8px;
            background:#f0fdf4;border:1px solid #86efac;border-radius:10px;
            padding:10px 14px;margin:16px 0 8px;font-size:13px;color:#166534;">
  <span style="font-size:15px;">✅</span>
  <span>已加载「<strong>{preset["label"]}</strong>」预设评估维度，可调整权重后锁定</span>
</div>""")

    if st.button("📋 查看岗位 JD", key="jd_btn_rule_builder"):
        _jd_dialog(preset["label"], preset["jd"])

    # 业务需求方参与说明
    st.html("""
<div style="background:#EFF4FF;border:1px solid #C7D9FF;border-radius:12px;
            padding:12px 16px;margin:10px 0 16px;font-size:13px;color:#1E3A8A;
            display:flex;gap:10px;align-items:flex-start;">
  <span style="font-size:16px;flex-shrink:0;">💼</span>
  <span>
    <strong>此步骤由 HR 与业务需求方共同完成</strong>——业务方决定哪个能力维度更重要，
    权重反映的是岗位的真实能力优先级。<br/>
    <span style="color:#3B5FC0;">
    业务方希望优先筛选「有能力的人」，这套维度体系直接测量岗位所需能力，
    比学历标签给出更准确的信号。
    </span>
  </span>
</div>""")

    # 维度权重卡
    _bar_colors = ["#6366f1", "#06b6d4", "#10b981", "#f59e0b", "#f43f5e", "#8b5cf6", "#0ea5e9"]
    with st.container(border=True):
        new_dims = []
        total = 0
        # 先读一轮当前值，用于画色块条
        _cur_weights = [st.session_state.get(f"w_{d['id']}", d["weight"]) for d in edit_dims]

        # 色块条
        _bars_html = "".join(
            f'<div style="flex:{w};background:{_bar_colors[i % len(_bar_colors)]};height:10px;'
            f'{"border-radius:6px 0 0 6px;" if i == 0 else ""}'
            f'{"border-radius:0 6px 6px 0;" if i == len(edit_dims)-1 else ""}"></div>'
            for i, (d, w) in enumerate(zip(edit_dims, _cur_weights))
        )
        st.html(f'<div style="display:flex;gap:2px;margin-bottom:14px;">{_bars_html}</div>')

        # 数字输入框：与色块对应，每维度一列
        inp_cols = st.columns(len(edit_dims))
        for i, (col, d) in enumerate(zip(inp_cols, edit_dims)):
            with col:
                st.html(
                    f'<div style="display:flex;align-items:center;gap:5px;margin-bottom:2px;">'
                    f'<span style="width:10px;height:10px;border-radius:3px;flex-shrink:0;'
                    f'background:{_bar_colors[i % len(_bar_colors)]};display:inline-block;"></span>'
                    f'<span style="font-size:12px;font-weight:600;color:#374151;'
                    f'white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">{d["label"]}</span>'
                    f'</div>'
                )
                w = st.number_input(
                    d["label"], min_value=5, max_value=60, step=5,
                    value=st.session_state.get(f"w_{d['id']}", d["weight"]),
                    key=f"w_{d['id']}", label_visibility="collapsed",
                )
                new_dims.append({**d, "weight": w})
                total += w
        st.session_state.editing_dims = new_dims

        if total == 100:
            st.markdown(f'<span style="background:#dcfce7;color:#166534;border-radius:999px;padding:3px 12px;font-size:13px;font-weight:600;">✅ 总计 {total}%</span>', unsafe_allow_html=True)
        else:
            st.markdown(f'<span style="background:#fef3c7;color:#92400e;border-radius:999px;padding:3px 12px;font-size:13px;font-weight:600;">⚠ 总计 {total}%，需调整至 100%</span>', unsafe_allow_html=True)

    # 锁定按钮
    st.markdown('<br/>', unsafe_allow_html=True)
    st.markdown('<p style="font-size:13px;color:#6b7280;">点击「锁定规则并发布」后规则 <strong>不可修改</strong>，系统将生成规则指纹并同步公示页。</p>', unsafe_allow_html=True)

    if st.button("🔒 锁定规则并发布", type="primary", disabled=(total != 100), key="lock_btn"):
        fp  = rule_fingerprint(new_dims)
        at  = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        rid = save_rule(jk, preset["label"], new_dims, fp, at)
        st.session_state.locked_jobs[jk] = {
            "dims":        new_dims,
            "fingerprint": fp,
            "locked_at":   at,
            "rule_id":     rid,
            "label":       preset["label"],
        }
        st.session_state.active_job   = jk
        st.session_state.selected_job = None
        st.session_state.editing_dims = None
        st.rerun()


# ─── Page 2：筛选工作台 ───────────────────────────────────────────────────────
def render_screening():
    locked_jobs = st.session_state.locked_jobs
    results     = st.session_state.screening_results

    if not locked_jobs:
        st.html("""
<div style="background:white;border:1px solid #e5e7eb;border-radius:16px;
            padding:56px 40px;text-align:center;
            box-shadow:0 1px 4px rgba(0,0,0,.06);">
  <div style="font-size:32px;margin-bottom:12px;">🔒</div>
  <div style="font-size:15px;font-weight:600;color:#374151;margin-bottom:6px;">规则尚未锁定</div>
  <div style="font-size:13px;color:#9ca3af;">请先在「🏗 规则构建」页完成规则锁定，再来筛选</div>
</div>""")
        return

    # ── 多岗位切换 ──────────────────────────────────────────────────────────
    if len(locked_jobs) > 1:
        st.html('<p style="font-size:13px;font-weight:600;color:#374151;margin:0 0 8px;">选择筛选岗位</p>')
        _job_cols = st.columns(len(locked_jobs))
        for _i, (_jk, _js) in enumerate(locked_jobs.items()):
            with _job_cols[_i]:
                _active = st.session_state.active_job == _jk
                if st.button(
                    ("▶ " if _active else "") + _js["label"],
                    key=f"sw_job_{_jk}",
                    type="primary" if _active else "secondary",
                    use_container_width=True,
                ):
                    st.session_state.active_job     = _jk
                    st.session_state.selected_cands = []
                    st.rerun()

    # ── 确保 active_job 有效 ─────────────────────────────────────────────
    if not st.session_state.active_job or st.session_state.active_job not in locked_jobs:
        st.session_state.active_job = list(locked_jobs.keys())[0]

    jk      = st.session_state.active_job
    js      = locked_jobs[jk]
    dims    = js["dims"]
    rule_id = js["rule_id"]
    preset  = JOB_PRESETS[jk]
    job_c   = [c for c in CANDIDATES if c["job"] == jk]

    st.html(f"""
{"" if has_api_key() else _preset_mode_banner()}
<div style="margin-bottom:16px;">
  <div style="display:flex;align-items:center;gap:10px;margin-bottom:6px;">
    <h2 style="font-size:22px;font-weight:800;color:#111827;margin:0;">筛选工作台</h2>
    {_role_badge("HR 视角")}
  </div>
  <p style="font-size:14px;color:#6b7280;margin:0;">
    AI 按锁定规则逐条评分 · 每条结论追溯维度 ·
    <span style="background:#EEF2F8;color:#1A1714;border-radius:999px;
                 padding:1px 8px;font-size:12px;font-weight:600;">{preset["label"]}</span>
  </p>
</div>""")

    # ── 候选人选择区 ──────────────────────────────────────────────────────────
    with st.container(border=True):
        col_t, col_all = st.columns([4, 1])
        with col_t:
            st.markdown('<span style="font-size:14px;font-weight:600;color:#374151;">选择待筛简历</span>', unsafe_allow_html=True)
        with col_all:
            all_ids = [c["id"] for c in job_c]
            cur_sel = st.session_state.selected_cands
            if st.button("全选" if set(cur_sel) != set(all_ids) else "取消全选", key="tog_all"):
                if set(cur_sel) == set(all_ids):
                    # 取消全选
                    st.session_state.selected_cands = []
                    for cid in all_ids:
                        st.session_state[f"chk_{cid}"] = False
                else:
                    # 全选：同步更新各 checkbox 的 widget state
                    st.session_state.selected_cands = all_ids[:]
                    for cid in all_ids:
                        st.session_state[f"chk_{cid}"] = True
                st.rerun()

        cols2 = st.columns(2)
        for i, c in enumerate(job_c):
            with cols2[i % 2]:
                chk = st.checkbox(
                    f"{c['name']} · {c['school']} · {c.get('degree','本科')} · {c['tag']}",
                    value=c["id"] in st.session_state.selected_cands,
                    key=f"chk_{c['id']}",
                )
                if chk and c["id"] not in st.session_state.selected_cands:
                    st.session_state.selected_cands.append(c["id"])
                elif not chk and c["id"] in st.session_state.selected_cands:
                    st.session_state.selected_cands.remove(c["id"])

        mode = "🤖 Claude 真实评分" if has_api_key() else "📋 预设数据模式（未配置 API Key）"
        st.markdown(f'<p style="font-size:12px;color:#9ca3af;margin-top:4px;">{mode}</p>', unsafe_allow_html=True)

        if st.button("🚀 开始筛选", type="primary",
                     disabled=not st.session_state.selected_cands, key="run"):
            sel_c = [c for c in job_c if c["id"] in st.session_state.selected_cands]
            _bar_slot = st.empty()
            def _bar(text: str, pct: float):
                filled = round(pct * 28)
                dots = "●" * filled + "○" * (28 - filled)
                _bar_slot.html(f"""
<div style="background:#1A1714;border-radius:10px;padding:11px 18px;
            display:flex;align-items:center;gap:12px;">
  <span style="font-family:'SF Mono',ui-monospace,monospace;font-size:11px;
               color:#475569;letter-spacing:.04em;flex-shrink:0;">{dots}</span>
  <span style="font-size:13px;font-weight:500;color:#FEFCF9;white-space:nowrap;">{text}</span>
</div>""")
            _bar("AI 评分中…", 0)
            for idx, cand in enumerate(sel_c):
                _bar(f"正在评分：{cand['name']}（{idx+1}/{len(sel_c)}）", idx / len(sel_c))
                llm_r = screen_candidate_with_llm(cand, dims, preset["jd"]) if has_api_key() else None
                if llm_r:
                    scores, reasons, ai_r, src = llm_r["scores"], llm_r["reasons"], llm_r["ai_result"], "ai"
                else:
                    # Preset mode：将 data.py 中的预设分数按位置映射到当前锁定的 dim IDs
                    # 避免自定义 dim IDs 与预设 score keys 不一致导致候选人视图全显示 0
                    _p_dims    = JOB_PRESETS[cand["job"]]["dims"]
                    _p_scores  = cand["scores"]
                    _p_reasons = cand.get("reasons", {})
                    scores, reasons = {}, {}
                    for _i, _ld in enumerate(dims):
                        if _ld["id"] in _p_scores:          # 完全匹配
                            scores[_ld["id"]]  = _p_scores[_ld["id"]]
                            reasons[_ld["id"]] = _p_reasons.get(_ld["id"], "")
                        elif _i < len(_p_dims):             # 按位置回退
                            _pd = _p_dims[_i]
                            scores[_ld["id"]]  = _p_scores.get(_pd["id"], 50)
                            reasons[_ld["id"]] = _p_reasons.get(_pd["id"], "")
                        else:
                            scores[_ld["id"]]  = 50
                            reasons[_ld["id"]] = ""
                    ai_r, src = cand["result"], "preset"
                st.session_state.screening_results[cand["id"]] = {
                    "scores": scores, "reasons": reasons,
                    "ai_result": ai_r, "source": src,
                }
                save_screening_result(cand["id"], rule_id, scores, reasons, ai_r, src)
                time.sleep(0.3)
            _bar("✓ 评分完成", 1.0)
            time.sleep(0.5)
            st.rerun()

    if not results:
        st.html("""
<div style="border:1.5px dashed #C8C4BC;border-radius:24px;
            padding:64px 32px;text-align:center;margin-top:16px;">
  <div style="width:52px;height:52px;background:#EFF0EC;border-radius:16px;
              display:flex;align-items:center;justify-content:center;
              margin:0 auto 16px;font-size:22px;">🚀</div>
  <div style="font-size:15px;font-weight:700;color:#1A1714;letter-spacing:-.01em;margin-bottom:8px;">
    选择候选人，点击「开始筛选」
  </div>
  <div style="font-size:13px;color:#94A9BC;line-height:1.8;max-width:320px;margin:0 auto;">
    AI 按锁定规则逐份评分<br/>每条结论可追溯到具体维度证据
  </div>
</div>""")
        return

    # ── 汇总栏（只统计当前岗位的候选人，不跨岗累积）────────────────────────
    all_finals = [_get_final(c["id"], results[c["id"]]["ai_result"])[0]
                  for c in job_c if c["id"] in results]
    n = len(all_finals)
    s_n = sum(1 for r in all_finals if r == "强推进面试")
    p_n = sum(1 for r in all_finals if r == "待定")
    rej = sum(1 for r in all_finals if r == "不推进")
    auto = round(((s_n + rej) / n) * 100) if n else 0

    # ── Be.run 风格 bento 统计区 ───────────────────────────────────────────────
    s_pct = round(s_n / n * 100) if n else 0
    p_pct = round(p_n / n * 100) if n else 0
    r_pct = 100 - s_pct - p_pct

    _s_blob = max(50, min(120, int(s_n / max(n, 1) * 230)))
    _p_blob = max(50, min(120, int(p_n / max(n, 1) * 230)))
    _r_blob = max(50, min(120, int(rej  / max(n, 1) * 230)))

    _ring_deg   = round(auto * 3.6)
    _ring_color = "#2563EB" if auto >= 80 else "#F59E0B" if auto >= 60 else "#EF4444"
    _ring_label = ("✓ 目标达成" if auto >= 80 and n >= 20
                   else f"{s_n + rej}/{n} 份已决策" if auto >= 80
                   else "目标 ≥ 80%")

    st.html(f"""
<div style="display:grid;grid-template-columns:1.55fr 1fr;gap:14px;margin-bottom:28px;">

  <!-- ▌ 左：候选人分布 (light card) -->
  <div style="background:#FFFFFF;border:1px solid #DDE5F0;border-radius:20px;
              padding:24px 26px;box-shadow:0 2px 14px rgba(30,41,59,.07);">
    <div style="font-size:10px;font-weight:700;color:#94A9BC;text-transform:uppercase;
                letter-spacing:.1em;margin-bottom:16px;">本批筛选 · {n} 份</div>

    <!-- blob 背景 + 数值叠加 -->
    <div style="position:relative;height:90px;margin-bottom:18px;">
      <div style="position:absolute;width:{_s_blob}px;height:{_s_blob}px;
                  background:rgba(74,222,128,.20);border-radius:50%;
                  filter:blur(22px);top:50%;left:9%;transform:translateY(-50%);"></div>
      <div style="position:absolute;width:{_p_blob}px;height:{_p_blob}px;
                  background:rgba(252,211,77,.22);border-radius:50%;
                  filter:blur(18px);top:50%;left:42%;transform:translateY(-50%);"></div>
      <div style="position:absolute;width:{_r_blob}px;height:{_r_blob}px;
                  background:rgba(248,113,113,.20);border-radius:50%;
                  filter:blur(18px);top:50%;left:70%;transform:translateY(-50%);"></div>
      <div style="position:relative;z-index:1;display:flex;height:100%;align-items:center;">
        <div style="flex:1;text-align:center;">
          <div style="font-size:40px;font-weight:900;color:#166534;letter-spacing:-.05em;
                      font-variant-numeric:tabular-nums;line-height:1;">{s_n}</div>
          <div style="font-size:11px;font-weight:600;color:#4ADE80;margin-top:4px;">强推进面试</div>
        </div>
        <div style="flex:1;text-align:center;">
          <div style="font-size:40px;font-weight:900;color:#92400E;letter-spacing:-.05em;
                      font-variant-numeric:tabular-nums;line-height:1;">{p_n}</div>
          <div style="font-size:11px;font-weight:600;color:#F59E0B;margin-top:4px;">待定</div>
        </div>
        <div style="flex:1;text-align:center;">
          <div style="font-size:40px;font-weight:900;color:#991B1B;letter-spacing:-.05em;
                      font-variant-numeric:tabular-nums;line-height:1;">{rej}</div>
          <div style="font-size:11px;font-weight:600;color:#EF4444;margin-top:4px;">不推进</div>
        </div>
      </div>
    </div>

    <!-- 比例条 -->
    <div style="background:#EEF2F8;border-radius:999px;height:5px;overflow:hidden;">
      <div style="display:flex;height:100%;">
        <div style="width:{s_pct}%;background:linear-gradient(to right,#86EFAC,#4ADE80);
                    border-radius:999px 0 0 999px;min-width:{2 if s_n else 0}px;"></div>
        <div style="width:{p_pct}%;background:#F59E0B;
                    min-width:{2 if p_n else 0}px;"></div>
        <div style="flex:1;background:#F87171;border-radius:0 999px 999px 0;"></div>
      </div>
    </div>
    <div style="display:flex;justify-content:space-around;margin-top:9px;">
      <span style="font-size:11px;color:#94A9BC;">强推进 {s_pct}%</span>
      <span style="font-size:11px;color:#94A9BC;">待定 {p_pct}%</span>
      <span style="font-size:11px;color:#94A9BC;">不推进 {r_pct}%</span>
    </div>
  </div>

  <!-- ▌ 右：AI 处理率 (light card) -->
  <div style="background:#FFFFFF;border:1px solid #DDE5F0;border-radius:20px;padding:24px;
              box-shadow:0 2px 14px rgba(30,41,59,.07);">
    <div style="font-size:10px;font-weight:700;color:#94A9BC;text-transform:uppercase;
                letter-spacing:.1em;margin-bottom:20px;">AI 自动处理率</div>
    <div style="display:flex;align-items:center;gap:20px;">
      <!-- conic-gradient donut ring -->
      <div style="width:82px;height:82px;border-radius:50%;flex-shrink:0;
                  background:conic-gradient({_ring_color} {_ring_deg}deg,#EEF2F8 0deg);
                  display:flex;align-items:center;justify-content:center;">
        <div style="width:58px;height:58px;background:#FFFFFF;border-radius:50%;"></div>
      </div>
      <div>
        <div style="font-size:46px;font-weight:900;color:#1E293B;letter-spacing:-.05em;
                    font-variant-numeric:tabular-nums;line-height:1;">{auto}<span
             style="font-size:14px;font-weight:400;color:#94A9BC;margin-left:2px;">%</span></div>
        <div style="font-size:12px;color:{_ring_color};font-weight:600;margin-top:7px;">{_ring_label}</div>
        <div style="font-size:11px;color:#475569;margin-top:3px;">{s_n + rej}/{n} 份已决策</div>
      </div>
    </div>
    <div style="font-size:10.5px;color:#94A9BC;margin-top:16px;padding-top:12px;
                border-top:1px solid #DDE5F0;line-height:1.6;">
      (强推 {s_n} + 不推进 {rej}) ÷ {n} 份 · 待定 {p_n} 份需人工复核
    </div>
  </div>

</div>""")

    # ── 漏斗预估：基于当前强推率推算全量 12000 份简历的到面人数 ─────────────────
    if n > 0:
        # 计划招聘人数（可调节）
        _, _nc = st.columns([5, 1])
        with _nc:
            hiring_target = st.number_input(
                "计划招聘人数",
                min_value=1, max_value=5000,
                value=st.session_state.hiring_target,
                step=1,
                key="hiring_target_input",
                help="用于计算「到面录取比」= 预计进入面试人数 / 计划招聘人数",
            )
            st.session_state.hiring_target = hiring_target

        proj_interviews = round(12000 * s_n / n)
        ratio_val       = proj_interviews / hiring_target if hiring_target else 0
        ratio_str       = f"{ratio_val:.1f}:1"
        ratio_ok        = ratio_val <= 8
        ratio_bg        = "#f0fdf4" if ratio_ok else "#fef2f2"
        ratio_border    = "#86efac" if ratio_ok else "#fecaca"
        ratio_color     = "#166534" if ratio_ok else "#991b1b"
        ratio_icon      = "✅" if ratio_ok else "⚠"
        ratio_note      = "达标 ≤8:1" if ratio_ok else "偏高，可上调强推阈值"
        st.html(f"""
<div style="background:#FFFFFF;border:1px solid #DDE5F0;border-radius:20px;
            padding:18px 24px;margin-bottom:22px;
            box-shadow:4px 4px 10px rgba(30,41,59,.06),-2px -2px 6px rgba(255,255,255,.80);
            display:flex;align-items:center;gap:24px;flex-wrap:wrap;">
  <div style="font-size:10.5px;font-weight:700;color:#94A9BC;text-transform:uppercase;
              letter-spacing:.08em;white-space:nowrap;">全量推算</div>
  <div style="display:flex;align-items:baseline;gap:6px;">
    <span style="font-size:26px;font-weight:800;color:#1A1714;letter-spacing:-.03em;
                 font-variant-numeric:tabular-nums;">{proj_interviews}</span>
    <span style="font-size:13px;color:#94A9BC;">人预计进入面试 / 12,000 份</span>
  </div>
  <div style="width:1px;height:28px;background:#DDE5F0;flex-shrink:0;"></div>
  <div style="display:flex;align-items:center;gap:8px;">
    <span style="font-size:13px;color:#475569;">到面录取比</span>
    <span style="background:{ratio_bg};border:1px solid {ratio_border};color:{ratio_color};
                 border-radius:999px;padding:3px 12px;font-size:13px;font-weight:700;">
      {ratio_icon} {ratio_str}</span>
    <span style="font-size:12px;color:{ratio_color};font-weight:500;">{ratio_note}</span>
  </div>
  <div style="font-size:11px;color:#C4BCB2;margin-left:auto;text-align:right;line-height:1.6;">
    目标 ≤ 8:1 · 招聘 {hiring_target} 人<br/>基于本批 {n} 份样本估算
  </div>
</div>""")

    # ── 核心论据 Callout：非精英候选人超越精英时主动高亮 ─────────────────────
    _elite_tags = {"985", "211"}
    _scored = [
        (c, weighted_score(results[c["id"]]["scores"], dims))
        for c in job_c if c["id"] in results
    ]
    _scored.sort(key=lambda x: x[1], reverse=True)
    _elite_scores   = [s for c, s in _scored if c["tag"] in _elite_tags]
    _non_elite_top  = [(c, s) for c, s in _scored if c["tag"] not in _elite_tags]
    if _elite_scores and _non_elite_top:
        _max_elite   = max(_elite_scores)
        _top_ne_cand, _top_ne_score = _non_elite_top[0]
        _beaten_count = sum(1 for s in _elite_scores if _top_ne_score > s)
        if _beaten_count > 0:
            _final_ne, _ = _get_final(_top_ne_cand["id"],
                                       results[_top_ne_cand["id"]]["ai_result"])
            if _final_ne == "强推进面试":
                st.html(f"""
<div style="background:linear-gradient(135deg,#1A1714 0%,#2D2825 100%);
            border-radius:16px;padding:18px 22px;margin-bottom:16px;
            border:1px solid rgba(74,222,128,.20);
            box-shadow:0 4px 20px rgba(30,41,59,.28);">
  <div style="display:flex;align-items:flex-start;gap:14px;">
    <span style="font-size:28px;flex-shrink:0;">⚡</span>
    <div>
      <div style="font-size:14px;font-weight:800;color:#6ee7b7;margin-bottom:6px;
                  letter-spacing:-.01em;">院校隔离生效 · 核心论据</div>
      <div style="font-size:13px;color:#e5e7eb;line-height:1.7;">
        <strong style="color:#fff;">{_top_ne_cand["name"]}</strong>
        <span style="background:rgba(255,255,255,.1);border-radius:999px;
                     padding:1px 8px;font-size:11px;color:#d1d5db;margin:0 6px;">
          {_top_ne_cand["school"]} · {_top_ne_cand["tag"]}</span>
        综合得分 <strong style="color:#6ee7b7;font-size:16px;">{_top_ne_score}</strong> 分，
        超过 <strong style="color:#fff;">{_beaten_count}</strong> 位 985/211 候选人
      </div>
      <div style="font-size:12px;color:#C8C4BE;margin-top:8px;line-height:1.6;">
        系统在技术层面已移除院校名称，评分完全基于简历中可观察的能力事实。
        双非候选人凭实力排名更高——这是本方案化解「院校歧视 vs 能力优先」冲突的核心证明。
      </div>
    </div>
  </div>
</div>""")

    # ── 候选人结果卡片（按综合得分从高到低排列）─────────────────────────────
    job_c_sorted = sorted(
        [c for c in job_c if c["id"] in results],
        key=lambda c: weighted_score(results[c["id"]]["scores"], dims),
        reverse=True,
    )

    # ── 批量导出 ─────────────────────────────────────────────────────────────
    if job_c_sorted:
        import csv, io as _io
        _bulk_buf = _io.StringIO()
        _bw = csv.writer(_bulk_buf)
        _bw.writerow(["候选人", "院校", "标签", "岗位", "AI建议", "最终结果",
                      "HR覆盖", "加权总分", "规则指纹"]
                     + [f"{d['label']}得分" for d in dims]
                     + [f"{d['label']}理由" for d in dims])
        for _c in job_c_sorted:
            _r = results[_c["id"]]
            _fin, _ov = _get_final(_c["id"], _r["ai_result"])
            _ov_note = st.session_state.overrides.get(_c["id"], {}).get("note", "")
            _bw.writerow(
                [_c["name"], _c["school"], _c["tag"], js["label"],
                 _r["ai_result"], _fin, _ov_note,
                 weighted_score(_r["scores"], dims), js["fingerprint"]]
                + [_r["scores"].get(d["id"], "") for d in dims]
                + [_r["reasons"].get(d["id"], "") for d in dims]
            )
        _dl_col, _ = st.columns([2, 8])
        with _dl_col:
            st.download_button(
                "⬇ 导出全部评分卡",
                data=_bulk_buf.getvalue().encode("utf-8-sig"),
                file_name=f"评分卡_全部_{js['label']}.csv",
                mime="text/csv",
                key="dl_bulk",
                use_container_width=True,
            )

    for cand in job_c_sorted:
        cid = cand["id"]
        if cid not in results:
            continue

        r          = results[cid]
        final, ov  = _get_final(cid, r["ai_result"])
        color      = result_color(final)
        cm         = COLOR_MAP[color]
        score      = weighted_score(r["scores"], dims)
        src_label  = "🤖 Claude AI" if r.get("source") == "ai" else "📋 预设数据"
        ov_data    = st.session_state.overrides.get(cid, {})

        ov_note_html = ""
        if ov:
            ov_note_html = f"""
<div style="background:#fffbeb;border:1px solid #fde68a;border-radius:8px;
            padding:8px 12px;font-size:12px;color:#92400e;margin-top:8px;">
  ⚠ HR 已覆盖：原 AI 建议「{r['ai_result']}」→「{final}」
  {"<br/>覆盖原因：" + ov_data.get("note","") if ov_data.get("note") else ""}
</div>"""

        # 主卡片 HTML — flat shadow + left accent strip (Be.run 风格)
        _flat_card = "0 2px 14px rgba(30,41,59,.07),0 1px 3px rgba(30,41,59,.04)"
        _flat_hover = "0 10px 32px rgba(30,41,59,.13),0 3px 8px rgba(30,41,59,.06)"
        st.html(f"""
<div style="background:#FFFFFF;border-radius:20px;overflow:hidden;
            box-shadow:{_flat_card};
            transition:box-shadow .28s cubic-bezier(0.34,1.56,0.64,1),
                       transform .28s cubic-bezier(0.34,1.56,0.64,1);"
     onmouseenter="this.style.boxShadow='{_flat_hover}';this.style.transform='translateY(-3px)'"
     onmouseleave="this.style.boxShadow='{_flat_card}';this.style.transform='translateY(0)'">
  <div style="display:flex;height:100%;">
    <div style="width:5px;flex-shrink:0;background:{cm['accent']};"></div>
    <div style="flex:1;padding:22px 24px;border:1px solid #DDE5F0;border-left:none;
                border-radius:0 20px 20px 0;">
      <div style="display:flex;align-items:flex-start;justify-content:space-between;gap:20px;">
        <div style="flex:1;min-width:0;">
          <div style="display:flex;align-items:center;gap:7px;flex-wrap:wrap;margin-bottom:7px;">
            <span style="font-size:15px;font-weight:700;color:#1A1714;letter-spacing:-.02em;">{cand["name"]}</span>
            <span style="background:#F0F4FA;border:1px solid #DDE5F0;color:#475569;
                         border-radius:999px;padding:2px 9px;font-size:12px;font-weight:500;">{cand["school"]}</span>
            {_degree_tag(cand.get("degree","本科"))}
            {_tag(cand["tag"])}
          </div>
          <p style="font-size:13px;color:#475569;line-height:1.68;margin:0 0 6px;">{cand["summary"]}</p>
          <span style="font-size:11px;color:#C4BCB2;letter-spacing:.02em;">{src_label}</span>
          {ov_note_html}
        </div>
        <div style="text-align:right;flex-shrink:0;padding-left:12px;">
          {_badge(final)}
          <div style="font-size:42px;font-weight:900;color:#1A1714;margin-top:8px;
                      line-height:1;letter-spacing:-.05em;font-variant-numeric:tabular-nums;">
            {score}<span style="font-size:13px;font-weight:400;color:#94A9BC;
                               letter-spacing:.02em;margin-left:1px;">分</span>
          </div>
        </div>
      </div>
      <div style="margin-top:18px;padding-top:16px;border-top:1px solid #EEF2F8;">
        {_bars(r["scores"], dims)}
      </div>
    </div>
  </div>
</div>
""")

        # ── 操作行 ────────────────────────────────────────────────────────────
        exp_key = f"exp_{cid}"
        is_expanded = st.session_state.get(exp_key, False)
        btn_cols = st.columns([1, 1, 1, 1])  # 展开理由 + 原始简历 + 导出评分卡 + 空白

        with btn_cols[0]:
            exp_txt = "▲ 收起理由" if is_expanded else "▼ 展开理由"
            if st.button(exp_txt, key=f"btn_exp_{cid}", use_container_width=True):
                st.session_state[exp_key] = not is_expanded
                st.rerun()
        with btn_cols[1]:
            if st.button("📄 原始简历", key=f"btn_res_{cid}", use_container_width=True):
                _resume_dialog(cand)
        with btn_cols[2]:
            import csv, io
            _csv_buf = io.StringIO()
            _w = csv.writer(_csv_buf)
            _w.writerow(["字段", "值"])
            _w.writerow(["候选人", cand["name"]])
            _w.writerow(["院校", cand["school"]])
            _w.writerow(["标签", cand["tag"]])
            _w.writerow(["岗位", js["label"]])
            _w.writerow(["规则指纹", js["fingerprint"]])
            _w.writerow(["规则锁定时间", js.get("locked_at", "")])
            _w.writerow(["AI 建议", r["ai_result"]])
            _w.writerow(["最终结果", final])
            if ov:
                _w.writerow(["HR 覆盖原因", ov_data.get("note", "")])
            _w.writerow(["加权总分", score])
            _w.writerow([])
            _w.writerow(["维度", "权重(%)", "得分", "AI 评分理由"])
            for _d in dims:
                _w.writerow([
                    _d["label"],
                    _d["weight"],
                    r["scores"].get(_d["id"], ""),
                    r["reasons"].get(_d["id"], ""),
                ])
            st.download_button(
                "⬇ 导出评分卡",
                data=_csv_buf.getvalue().encode("utf-8-sig"),
                file_name=f"评分卡_{cand['name']}_{js['label']}.csv",
                mime="text/csv",
                key=f"dl_card_{cid}",
                use_container_width=True,
            )
        if is_expanded:
            reasons_html = "".join(
                f"""<div style="padding:12px 0;border-bottom:1px solid #EEF2F8;">
  <div style="display:flex;align-items:baseline;gap:8px;margin-bottom:5px;">
    <span style="font-size:11px;font-weight:700;color:#1A1714;letter-spacing:.04em;
                 text-transform:uppercase;">{d["label"]}</span>
    <span style="font-size:11px;color:#C4BCB2;">权重 {d["weight"]}%</span>
  </div>
  <div style="font-size:13px;color:#475569;line-height:1.72;">{r["reasons"].get(d["id"],"")}</div>
</div>"""
                for d in dims
            )
            st.html(f"""
<div style="background:#FEFCF9;border:1px solid #DDE5F0;
            border-radius:12px;padding:4px 18px 4px;margin-top:2px;">
  <p style="font-size:10.5px;font-weight:700;color:#94A9BC;text-transform:uppercase;
             letter-spacing:.08em;margin:14px 0 0;">AI 评分依据 · 逐维度</p>
  {reasons_html}
</div>
""")
            # ── HR 覆盖区域 ────────────────────────────────────────────────────
            cur_ov    = ov_data.get("result", "")
            pending_ov = st.session_state.get(f"ov_pending_{cid}", cur_ov)

            st.html("""
<div style="margin-top:16px;padding-top:14px;border-top:1px solid #f0f0f0;">
  <div style="display:flex;align-items:center;gap:8px;margin-bottom:4px;">
    <span style="font-size:13px;font-weight:700;color:#374151;">HR 覆盖 AI 建议</span>
    <span style="font-size:11px;background:#fef3c7;color:#92400e;border-radius:999px;
                 padding:2px 8px;font-weight:500;">操作将写入审计日志，留存可查</span>
  </div>
</div>""")

            # 三个等宽按钮
            ov_opts = ["强推进面试", "待定", "不推进"]
            ov_c1, ov_c2, ov_c3 = st.columns(3)
            for col, opt in zip([ov_c1, ov_c2, ov_c3], ov_opts):
                with col:
                    active = (pending_ov == opt) or (not pending_ov and cur_ov == opt)
                    if st.button(
                        ("✓ " if active else "") + opt,
                        key=f"ov_{opt}_{cid}",
                        type="primary" if active else "secondary",
                        use_container_width=True,
                    ):
                        if active and not cur_ov:
                            # 取消待选（已选但未保存）
                            st.session_state.pop(f"ov_pending_{cid}", None)
                        else:
                            st.session_state[f"ov_pending_{cid}"] = opt
                        st.rerun()

            # 覆盖原因输入框：只要选了某个结果就显示（含已保存状态）
            effective_target = pending_ov or cur_ov
            if effective_target:
                st.html(f"""
<div style="margin-top:10px;">
  <span style="font-size:12px;font-weight:600;color:#374151;">覆盖原因</span>
  <span style="font-size:11px;color:#ef4444;margin-left:4px;font-weight:600;">* 必填</span>
  <span style="font-size:11px;color:#9ca3af;margin-left:6px;">· 将与操作记录一同写入审计日志</span>
</div>""")
                ov_note = st.text_area(
                    "覆盖原因",
                    value=ov_data.get("note", ""),
                    key=f"ov_note_{cid}",
                    placeholder=f"请说明将结果调整为「{effective_target}」的原因，例如：候选人有额外实习经历未在简历体现，面试官面谈后评估更高…",
                    height=88,
                    label_visibility="collapsed",
                )

                s_col, c_col, _ = st.columns([2, 2, 6])
                with s_col:
                    if st.button("💾 保存覆盖", key=f"ov_save_{cid}", type="primary",
                                 use_container_width=True):
                        if not ov_note.strip():
                            st.error("覆盖原因不能为空，请填写后保存")
                        else:
                            st.session_state.overrides[cid] = {
                                "result": effective_target, "note": ov_note
                            }
                            save_hr_override(cid, rule_id, r["ai_result"],
                                             effective_target, ov_note)
                            st.session_state.pop(f"ov_pending_{cid}", None)
                            st.toast(f"✅ 已覆盖为「{effective_target}」，审计记录已保存")
                            st.rerun()
                with c_col:
                    if cur_ov and st.button("↩ 撤销覆盖", key=f"ov_cancel_{cid}",
                                            use_container_width=True):
                        st.session_state.overrides.pop(cid, None)
                        st.session_state.pop(f"ov_pending_{cid}", None)
                        st.toast("已撤销 HR 覆盖，恢复 AI 建议", icon="↩")
                        st.rerun()

        # 卡片间隔
        st.markdown('<div style="height:16px;"></div>', unsafe_allow_html=True)

    # ── HR 申诉管理面板 + 审计日志 ───────────────────────────────────────────
    st.markdown('<div style="height:24px;"></div>', unsafe_allow_html=True)

    # 申诉数量徽标
    all_appeals  = get_all_appeals()
    appeal_count = len([a for a in all_appeals if a.get("status", "pending") == "pending"])
    appeal_badge = (
        f'<span style="background:#ef4444;color:white;border-radius:999px;'
        f'padding:1px 7px;font-size:11px;font-weight:700;margin-left:6px;">{appeal_count}</span>'
        if appeal_count else ""
    )
    st.html(f"""
<div style="display:flex;align-items:center;gap:10px;margin-bottom:8px;">
  <span style="font-size:14px;font-weight:700;color:#374151;">📬 申诉管理</span>
  {appeal_badge}
  <span style="font-size:12px;color:#9ca3af;">· 候选人提交后在此复核，结果写入审计日志</span>
</div>""")

    with st.expander(
        f"{'🔴 ' + str(appeal_count) + ' 条待处理申诉' if appeal_count else '📭 暂无待处理申诉'} — 点击展开",
        expanded=bool(appeal_count)
    ):
        if not all_appeals:
            st.html("""
<div style="text-align:center;padding:32px;color:#9ca3af;font-size:13px;">
  📭 暂无候选人提交申诉
</div>""")
        else:
            st.html(f"""
<div style="font-size:13px;color:#6b7280;margin-bottom:12px;line-height:1.6;">
  共 <strong style="color:#111827;">{appeal_count}</strong> 条申诉，
  已结构化拆分为「维度 + 补充证据」格式，便于针对性复核。
  复核基准为规则锁定版本（指纹不变），<strong>请仅处理有新证据的申诉</strong>。
</div>""")
            for ap in all_appeals:
                ap_id      = ap["id"]
                cid        = ap["candidate_id"]
                cname      = ap["candidate_name"]
                ap_text    = ap["appeal_text"]
                status     = ap.get("status", "pending")
                submitted  = ap.get("submitted_at", "")[:16]
                cand_info  = CANDIDATES_MAP.get(cid)
                school_tag = f"{cand_info['school']} · {cand_info['tag']}" if cand_info else ""

                # 解析 ap_text：[label] evidence 格式
                dim_items = []
                for line in ap_text.split("\n"):
                    line = line.strip()
                    if line.startswith("[") and "]" in line:
                        bracket_end = line.index("]")
                        lbl = line[1:bracket_end]
                        ev  = line[bracket_end+1:].strip()
                        dim_items.append((lbl, ev))

                dim_html = "".join(
                    f"""<div style="background:#f9fafb;border:1px solid #f0f0f0;
                                    border-radius:8px;padding:10px 14px;margin-bottom:6px;">
  <div style="font-size:12px;font-weight:700;color:#374151;margin-bottom:4px;">
    {lbl}
  </div>
  <div style="font-size:12px;color:#4b5563;line-height:1.6;">{ev or "（未填写）"}</div>
</div>"""
                    for lbl, ev in dim_items
                ) if dim_items else f'<div style="font-size:12px;color:#9ca3af;">{ap_text}</div>'

                status_cfg = {
                    "pending":  ("#fef3c7", "#92400e", "#fde68a", "待处理"),
                    "reviewed": ("#f0fdf4", "#166534", "#86efac", "已复核"),
                    "dismissed":("#fef2f2", "#991b1b", "#fecaca", "已驳回"),
                }
                s_bg, s_tc, s_border, s_txt = status_cfg.get(
                    status, ("#f9fafb","#374151","#e5e7eb","未知"))

                st.html(f"""
<div style="background:white;border:1px solid #e5e7eb;border-radius:14px;
            padding:16px 18px;margin-bottom:4px;box-shadow:0 1px 4px rgba(0,0,0,.05);">
  <div style="display:flex;align-items:flex-start;justify-content:space-between;
              gap:16px;margin-bottom:10px;">
    <div>
      <span style="font-size:14px;font-weight:700;color:#111827;">{cname}</span>
      <span style="font-size:12px;color:#9ca3af;margin-left:8px;">{school_tag}</span>
    </div>
    <div style="display:flex;align-items:center;gap:8px;flex-shrink:0;">
      <span style="background:{s_bg};color:{s_tc};border:1px solid {s_border};
                   border-radius:999px;padding:2px 10px;font-size:11px;font-weight:600;">
        {s_txt}</span>
      <span style="font-size:11px;color:#c4c9d4;">{submitted}</span>
    </div>
  </div>
  <div style="font-size:11px;font-weight:600;color:#9ca3af;text-transform:uppercase;
              letter-spacing:.06em;margin-bottom:8px;">质疑维度 · 补充证据</div>
  {dim_html}
</div>""")

                if status == "pending":
                    a_col, b_col, c_col, _ = st.columns([2, 2, 2, 4])
                    with a_col:
                        if st.button("✅ 维持原判", key=f"ap_rev_{ap_id}",
                                     use_container_width=True, type="primary"):
                            update_appeal_status(ap_id, "reviewed")
                            st.toast(f"✅ {cname} 的申诉已复核，维持原结论")
                            st.session_state.pop(f"ap_accept_{ap_id}", None)
                            st.rerun()
                    with b_col:
                        if st.button("🔄 采纳申诉", key=f"ap_acc_{ap_id}",
                                     use_container_width=True):
                            st.session_state[f"ap_accept_{ap_id}"] = True
                    with c_col:
                        if st.button("❌ 驳回申诉", key=f"ap_dis_{ap_id}",
                                     use_container_width=True):
                            update_appeal_status(ap_id, "dismissed")
                            st.toast(f"已驳回 {cname} 的申诉")
                            st.session_state.pop(f"ap_accept_{ap_id}", None)
                            st.rerun()

                    if st.session_state.get(f"ap_accept_{ap_id}"):
                        ai_result = st.session_state.screening_results.get(cid, {}).get("ai_result", "不推进")
                        with st.container():
                            st.markdown(
                                '<div style="background:#f0fdf4;border:1px solid #86efac;'
                                'border-radius:10px;padding:12px 14px;margin-top:8px;">',
                                unsafe_allow_html=True)
                            new_result = st.selectbox(
                                "调整为",
                                [r for r in ["强推进面试", "待定", "不推进"] if r != ai_result],
                                key=f"ap_new_result_{ap_id}",
                            )
                            acc_note = st.text_input(
                                "采纳原因（将记入审计日志）",
                                placeholder="例：候选人提供了未在原简历体现的项目链接，经核实符合岗位要求",
                                key=f"ap_acc_note_{ap_id}",
                            )
                            confirm_col, cancel_col, _ = st.columns([2, 2, 6])
                            with confirm_col:
                                if st.button("💾 确认采纳", key=f"ap_acc_confirm_{ap_id}",
                                             type="primary", use_container_width=True):
                                    if not acc_note.strip():
                                        st.error("请填写采纳原因")
                                    else:
                                        st.session_state.overrides[cid] = {
                                            "result": new_result, "note": acc_note
                                        }
                                        save_hr_override(cid, rule_id, ai_result,
                                                         new_result, acc_note)
                                        update_appeal_status(ap_id, "reviewed")
                                        st.session_state.pop(f"ap_accept_{ap_id}", None)
                                        st.toast(f"✅ 已采纳 {cname} 的申诉，结论调整为「{new_result}」")
                                        st.rerun()
                            with cancel_col:
                                if st.button("取消", key=f"ap_acc_cancel_{ap_id}",
                                             use_container_width=True):
                                    st.session_state.pop(f"ap_accept_{ap_id}", None)
                                    st.rerun()
                            st.markdown('</div>', unsafe_allow_html=True)
                else:
                    st.markdown(
                        f'<div style="font-size:12px;color:#9ca3af;padding:4px 0;">'
                        f'此申诉已处理完毕（{s_txt}）</div>',
                        unsafe_allow_html=True
                    )
                st.markdown('<div style="height:8px;"></div>', unsafe_allow_html=True)

    # ── HR 操作审计日志 ───────────────────────────────────────────────────────
    st.markdown('<div style="height:16px;"></div>', unsafe_allow_html=True)
    overrides_log = get_hr_overrides(rule_id) if rule_id else []
    with st.expander(
        f"🗂 HR 操作审计日志 · 共 {len(overrides_log)} 条{'（只读）' if overrides_log else ' — 暂无覆盖操作'}",
        expanded=False,
    ):
        if not overrides_log:
            st.html("""
<div style="text-align:center;padding:24px;color:#9ca3af;font-size:13px;">
  ℹ 尚未发生 HR 覆盖操作。覆盖 AI 建议后记录将在此留存，不可删除。
</div>""")
        else:
            st.html(f"""
<div style="font-size:12px;color:#6b7280;margin-bottom:10px;line-height:1.6;">
  以下记录为本规则版本下所有 HR 覆盖操作，<strong style="color:#374151;">不可修改，仅供审计参考</strong>。
  合规审查时可截图或导出此页面。
</div>""")
            for row in overrides_log:
                cand_info = CANDIDATES_MAP.get(row["candidate_id"])
                cname_log = cand_info["name"] if cand_info else row["candidate_id"]
                orig_c  = result_color(row["original_result"])
                over_c  = result_color(row["override_result"])
                orig_bg = COLOR_MAP[orig_c]["badge_bg"]
                orig_tc = COLOR_MAP[orig_c]["badge_text"]
                over_bg = COLOR_MAP[over_c]["badge_bg"]
                over_tc = COLOR_MAP[over_c]["badge_text"]
                st.html(f"""
<div style="background:#f9fafb;border:1px solid #e5e7eb;border-radius:10px;
            padding:12px 16px;margin-bottom:6px;font-size:12px;">
  <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:6px;">
    <span style="font-weight:700;color:#111827;">{cname_log}</span>
    <span style="background:{orig_bg};color:{orig_tc};border-radius:999px;
                 padding:1px 8px;font-size:11px;">{row["original_result"]}</span>
    <span style="color:#9ca3af;">→</span>
    <span style="background:{over_bg};color:{over_tc};border-radius:999px;
                 padding:1px 8px;font-size:11px;">{row["override_result"]}</span>
    <span style="color:#c4c9d4;margin-left:auto;font-size:11px;">{row.get("created_at","")[:16]}</span>
  </div>
  <div style="color:#4b5563;line-height:1.6;">
    <strong style="color:#374151;">覆盖原因：</strong>{row["override_note"]}
  </div>
</div>""")

        # ── 申诉处理记录 ─────────────────────────────────────────────────────
        reviewed_appeals = [a for a in all_appeals if a.get("status") != "pending"]
        if reviewed_appeals:
            st.html("""
<div style="font-size:12px;font-weight:700;color:#374151;margin:18px 0 8px;
            padding-top:14px;border-top:1px solid #e5e7eb;">
  📬 申诉处理记录
</div>""")
            _s_label = {"reviewed": ("✅ 已采纳", "#f0fdf4", "#166534"),
                        "dismissed": ("🚫 已驳回", "#fef2f2", "#991b1b")}
            for ap in reviewed_appeals:
                _sl, _sbg, _stc = _s_label.get(ap["status"], ("—", "#f9fafb", "#374151"))
                st.html(f"""
<div style="background:#f9fafb;border:1px solid #e5e7eb;border-radius:10px;
            padding:12px 16px;margin-bottom:6px;font-size:12px;">
  <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;">
    <span style="font-weight:700;color:#111827;">{ap["candidate_name"]}</span>
    <span style="background:{_sbg};color:{_stc};border-radius:999px;
                 padding:1px 8px;font-size:11px;font-weight:600;">{_sl}</span>
    <span style="color:#c4c9d4;margin-left:auto;font-size:11px;">{ap.get("submitted_at","")[:16]}</span>
  </div>
</div>""")


# ─── 候选人视图结论文案（对候选人友好，不用 HR 术语）────────────────────────
_CV_RESULT = {
    "强推进面试": ("✅", "恭喜！您已进入面试流程",     "#166534", "#f0fdf4", "#dcfce7", "#16a34a"),
    "待定":      ("⏳", "已收到您的申请，HR 复核中",       "#92400e", "#fffbeb", "#fef3c7", "#d97706"),
    "不推进":    ("❌", "很遗憾，本次未入选",            "#991b1b", "#fef2f2", "#fee2e2", "#dc2626"),
}

# ─── Page 3：候选人视图 ───────────────────────────────────────────────────────
def render_candidate_view():
    locked_jobs = st.session_state.locked_jobs
    results     = st.session_state.screening_results
    sel         = st.session_state.get("cv_selected", "")
    cand        = CANDIDATES_MAP.get(sel) if sel else None

    # ══ 状态 1：登录页（未输入有效 ID）══════════════════════════════════════════
    if not cand:
        st.html(f"""
<div style="margin-bottom:8px;">
  <div style="display:flex;align-items:center;gap:10px;">
    <h2 style="font-size:22px;font-weight:800;color:#111827;margin:0;">候选人视图</h2>
    {_role_badge("候选人视角")}
  </div>
</div>""")
        # 居中登录卡
        _, _mid, _ = st.columns([1, 2, 1])
        with _mid:
            st.html("""
<div style="background:white;border:1px solid #e5e7eb;border-radius:20px;
            padding:40px 32px 28px;text-align:center;margin-top:24px;
            box-shadow:0 4px 20px rgba(0,0,0,.08);">
  <div style="width:52px;height:52px;border-radius:16px;margin:0 auto 16px;
              background:#1A1714;
              display:flex;align-items:center;justify-content:center;">
    <span style="color:white;font-size:22px;">🎓</span>
  </div>
  <div style="font-size:18px;font-weight:800;color:#111827;margin-bottom:6px;">
    腾讯 2026 届秋招
  </div>
  <div style="font-size:13px;color:#9ca3af;margin-bottom:24px;line-height:1.6;">
    请输入您的应聘者编号<br/>查看本次简历筛选结果
  </div>
</div>""")
            _id_in = st.text_input(
                "编号", placeholder="输入应聘编号，如 A / B / C",
                key="cv_login_id", label_visibility="collapsed", max_chars=2,
            )
            if st.button("查看我的结果 →", type="primary", use_container_width=True,
                         key="cv_login_btn"):
                _clean = _id_in.strip().upper()
                if _clean in CANDIDATES_MAP:
                    st.session_state.cv_selected = _clean
                    st.session_state[f"ao_{_clean}"] = False
                    st.rerun()
                else:
                    st.error("未找到该编号，请确认后重试")
        return

    # ══ 状态 2：结果页 ══════════════════════════════════════════════════════════
    # 顶部：视角标签 + 返回按钮
    _th, _tb = st.columns([6, 1])
    with _th:
        st.html(f"""
<div style="display:flex;align-items:center;gap:10px;margin-bottom:4px;">
  <h2 style="font-size:22px;font-weight:800;color:#111827;margin:0;">候选人视图</h2>
  {_role_badge("候选人视角")}
</div>""")
    with _tb:
        if st.button("← 重新查询", key="cv_back"):
            st.session_state.cv_selected = ""
            st.rerun()

    if sel in results:
        r = results[sel]; ai_r = r["ai_result"]
        scores = r["scores"]; reasons = r.get("reasons", cand.get("reasons", {}))
    else:
        ai_r = cand["result"]; scores = cand["scores"]; reasons = cand.get("reasons", {})

    final, is_ov = _get_final(sel, ai_r)
    color        = result_color(final)
    cm           = COLOR_MAP[color]

    # 使用对应岗位已锁定的维度（保证与 HR 视图一致），否则回退预设
    _cand_js     = locked_jobs.get(cand["job"])
    display_dims = _cand_js["dims"]        if _cand_js else JOB_PRESETS[cand["job"]]["dims"]
    display_fp   = _cand_js["fingerprint"] if _cand_js else rule_fingerprint(display_dims)
    display_at   = _cand_js["locked_at"]   if _cand_js else ""
    jl           = JOB_PRESETS[cand["job"]]["label"]

    # ── 演示说明（卡片上方）──────────────────────────────────────────────────
    NOTES = {
        "A": "王芳（复旦 985 · 本科），有完整产品主导经历和数据分析能力，强推进。展示系统对强势候选人同样公平评估。",
        "B": "陈志远（深圳大学 · 双非 · 本科），项目主导经验与复旦王芳相当，同样强推进。核心论点：双非本科凭实力 = 985。",
        "C": "张浩然（北大 985 · 硕士），数据工具能力强，但两段实习均为执行支持角色（数据报表维护、科研助理），未主导过产品从立项到上线的完整环节，项目经验维度评分偏弱，综合得分落入待定区间。说明：硕士学历不等于产品能力。",
        "D": "李思琪（浙大 985 · 博士），SCI 论文 3 篇，但零产品经历，不推进。最强反直觉案例：985 博士被系统拒绝。",
        "E": "刘晓晨（职校 · 大专），能力确实不达标，不推进。关键：系统不因职校背景歧视，但也不因此降低评分标准。",
        "F": "吴佳琪（杭电 · 双非 · 本科），开源贡献和实习经验过硬，强推进。双非本科在技术维度完胜多位 985。",
        "G": "赵明远（南大 985 · 硕士），协作与表达是亮点，但字节跳动实习以配置修改和接口联调为主、核心逻辑由 mentor 完成；技术与算法「基本符合」、问题解决「有待提升」，加权总分不达标，不推进。名校学历 ≠ 独立工程能力。",
        "H": "林浩宇（华科 985 · 本科），课程 CRUD 项目为主，实习为测试岗，无独立后端项目，不推进。关键：985 光环无法弥补工程能力空白。",
        "I": "周晓敏（清华 985 · 博士 · ACM 金牌），但方向是控制理论，零后端工程经验，不推进。最大反转：清华博士+竞赛金牌被系统拒绝，因为与岗位不匹配。",
        "J": "郑凯文（无大学学历 · 高中 · 自学），4 年自学后端，GitHub 开源项目 800+ stars，2 年全职工作经验，强推进。终极论点：系统只看岗位相关能力，无学历者凭实力击败清华博士。",
    }
    if sel in NOTES:
        st.html(f"""
<details style="margin-bottom:12px;">
  <summary style="cursor:pointer;list-style:none;display:flex;align-items:center;gap:6px;
                  background:#f8fafc;border:1px solid #e2e8f0;border-radius:10px;
                  padding:8px 14px;font-size:12px;font-weight:600;color:#475569;
                  user-select:none;">
    <span style="background:#374151;color:#fff;border-radius:4px;
                 padding:1px 6px;font-size:10px;letter-spacing:.04em;margin-right:2px;">
      HR 演示视角
    </span>
    点击展开演示说明 · 候选人不可见
  </summary>
  <div style="background:#F0F4FA;
              border:1px solid #C8D8EA;border-radius:0 0 10px 10px;
              padding:12px 18px;font-size:13px;color:#3D3A36;line-height:1.65;">
    💡 {NOTES[sel]}
  </div>
</details>""")

    # 维度通过/未通过行（阈值与进度条颜色对齐：≥65 蓝/绿=符合，50–64 黄=基本符合，<50 红=有待提升）
    # 兜底：若当前 dim ID 在 scores 里查不到（历史数据 key 不匹配），按位置回退到预设分数
    _preset_dims_cv   = JOB_PRESETS[cand["job"]]["dims"]
    _preset_scores_cv = cand["scores"]
    dim_rows = ""
    for _di, d in enumerate(display_dims):
        if d["id"] in scores and scores[d["id"]] > 0:
            s = scores[d["id"]]
        elif _di < len(_preset_dims_cv):                    # 按位置回退
            s = _preset_scores_cv.get(_preset_dims_cv[_di]["id"], 50)
        else:
            s = 50
        if s >= 65:
            bg_ = "#f0fdf4"; tc_ = "#166534"; tag_ = "✅ 符合要求"
        elif s >= 50:
            bg_ = "#fffbeb"; tc_ = "#92400e"; tag_ = "📋 基本符合"
        else:
            bg_ = "#fef2f2"; tc_ = "#991b1b"; tag_ = "⚠ 有待提升"
        dim_rows += f"""
<div style="display:flex;align-items:center;justify-content:space-between;
            padding:12px 0;border-bottom:1px solid #f3f4f6;">
  <div>
    <span style="font-size:14px;font-weight:500;color:#111827;">{d["label"]}</span>
    <span style="font-size:12px;color:#9ca3af;margin-left:8px;">权重 {d["weight"]}%</span>
  </div>
  <span style="background:{bg_};color:{tc_};border-radius:999px;
               padding:3px 12px;font-size:12px;font-weight:600;">{tag_}</span>
</div>"""

    # 结果大图标 + 文字配置（使用候选人友好文案）
    r_icon, r_label, r_text_c, r_bg, r_border_c, r_accent = _CV_RESULT.get(
        final, ("❓", final, "#374151", "#f9fafb", "#e5e7eb", "#6b7280")
    )
    ov_note_cv = (
        f'<div style="margin-top:8px;font-size:12px;color:#d97706;font-weight:500;">'
        f'ⓘ 经 HR 复核调整</div>'
    ) if is_ov else ""

    st.html(f"""
<div style="border:2px solid {r_border_c};border-radius:20px;overflow:hidden;
            box-shadow:0 6px 24px rgba(0,0,0,.10);">
  <!-- Banner：结果为视觉主角 -->
  <div style="background:{r_bg};padding:28px 28px 24px;text-align:center;
              border-bottom:1px solid {r_border_c};">
    <p style="font-size:12px;color:#6b7280;margin:0 0 14px;font-weight:500;letter-spacing:.02em;">
      腾讯 · {jl} · 2026届秋招</p>
    <!-- 结果大字 -->
    <div style="font-size:32px;font-weight:900;color:{r_text_c};
                letter-spacing:-.01em;line-height:1.1;margin-bottom:10px;">
      {r_icon}&nbsp;{r_label}
    </div>
    <h3 style="font-size:16px;font-weight:600;color:#374151;margin:0;">
      您好，{cand["name"]}
    </h3>
    {ov_note_cv}
  </div>

  <!-- Body -->
  <div style="background:white;padding:22px 26px;">
    <!-- 维度结果 -->
    <p style="font-size:11px;font-weight:700;color:#9ca3af;text-transform:uppercase;
               letter-spacing:.07em;margin:0 0 6px;">评估维度结果</p>
    {dim_rows}

    <!-- 规则指纹 -->
    <div style="background:#F0F4FA;border:1px solid #C8D8EA;border-radius:12px;
                padding:14px 18px;margin-top:18px;">
      <p style="font-size:11px;font-weight:700;color:#475569;text-transform:uppercase;
                 letter-spacing:.06em;margin:0 0 8px;">本次评估适用规则版本</p>
      <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;">
        <span style="font-family:'SF Mono',ui-monospace,monospace;
                     background:white;border:1px solid #C8D8EA;border-radius:8px;
                     padding:5px 14px;font-size:16px;font-weight:800;
                     letter-spacing:.15em;color:#3D3A36;">
          {display_fp}
        </span>
        <span style="font-size:12px;color:#6b7280;">投递时已发送至您的邮箱</span>
      </div>
      <p style="font-size:12px;color:#6b7280;margin:8px 0 0;line-height:1.5;">
        与邮件指纹一致 → 规则自投递后<strong>未被修改</strong>，评估过程可信
      </p>
    </div>

    <!-- 说明 -->
    <div style="background:#f9fafb;border-radius:10px;padding:12px 16px;margin-top:14px;
                font-size:12.5px;color:#6b7280;line-height:1.65;border:1px solid #f0f0f0;">
      ℹ 评估结果基于公开发布的岗位规则，各维度分数不对外显示。
      如对结果有异议，可在下方提交申诉。
    </div>
  </div>
</div>
""")

    # 公示页按钮
    st.markdown('<div style="height:8px;"></div>', unsafe_allow_html=True)
    if st.button("🔗 查看规则公示页", key=f"pub_cv_{sel}"):
        if display_fp:
            _public_page_dialog(display_dims, display_fp, display_at, jl)
        else:
            st.toast("请先在规则构建页锁定规则", icon="⚠️")

    # ── 申诉系统 ─────────────────────────────────────────────────────────────
    st.markdown('<div style="height:14px;"></div>', unsafe_allow_html=True)
    ao_key  = f"ao_{sel}"
    ap_done = sel in st.session_state.appeal_submitted

    if ap_done:
        # ── 已提交：查询真实处理状态 ──────────────────────────────────────
        revealed = st.session_state.get(f"ap_revealed_{sel}", [])

        # 从数据库拿最新一条该候选人的申诉状态
        _all_ap   = get_all_appeals()
        _my_ap    = next((a for a in _all_ap if a["candidate_id"] == sel), None)
        _ap_status = _my_ap["status"] if _my_ap else "pending"

        if _ap_status == "pending":
            st.html("""
<div style="background:#f0fdf4;border:1.5px solid #86efac;border-radius:14px;
            padding:16px 20px;margin-bottom:12px;
            box-shadow:0 2px 8px rgba(16,185,129,.08);">
  <div style="font-size:14px;font-weight:700;color:#166534;margin-bottom:6px;">
    ✅ 申诉已受理 · 处理中
  </div>
  <div style="font-size:13px;color:#15803d;line-height:1.65;">
    校招运营团队将在 <strong>5 个工作日</strong>内处理您的申诉。<br/>
    复核基准为您提交时所对应的 <strong>锁定规则版本（指纹不变）</strong>，
    如需补充材料，将通过投递邮箱联系您。
  </div>
</div>""")

        elif _ap_status == "reviewed":
            # HR 复核通过 → 检查是否有 HR 覆盖（结果是否实际变更）
            _ov = st.session_state.overrides.get(sel, {})
            _changed = bool(_ov.get("result")) and _ov["result"] != final
            if _changed:
                st.html(f"""
<div style="background:#f0fdf4;border:1.5px solid #16a34a;border-radius:14px;
            padding:18px 22px;margin-bottom:12px;
            box-shadow:0 4px 16px rgba(16,185,129,.12);">
  <div style="font-size:15px;font-weight:800;color:#166534;margin-bottom:8px;">
    🎉 申诉复核完成 · 结论已调整
  </div>
  <div style="font-size:13px;color:#15803d;line-height:1.7;">
    经校招团队人工复核，您的评估结论已由
    <strong>「{_ov["result"]}」</strong> 更新。<br/>
    如有后续安排，我们将通过您的投递邮箱与您联系。
  </div>
</div>""")
            else:
                st.html("""
<div style="background:#F0F4FA;border:1.5px solid #C8D8EA;border-radius:14px;
            padding:16px 20px;margin-bottom:12px;">
  <div style="font-size:14px;font-weight:700;color:#1A1714;margin-bottom:6px;">
    📋 申诉复核完成 · 维持原结论
  </div>
  <div style="font-size:13px;color:#475569;line-height:1.65;">
    校招团队已对您申诉的维度进行人工复核，基于现有材料，<strong>原评估结论不变</strong>。<br/>
    如有新的可核实证据（项目链接、证书等），可通过投递邮箱补充后再次申请。
  </div>
</div>""")

        elif _ap_status == "dismissed":
            st.html("""
<div style="background:#fef2f2;border:1.5px solid #fca5a5;border-radius:14px;
            padding:16px 20px;margin-bottom:12px;">
  <div style="font-size:14px;font-weight:700;color:#991b1b;margin-bottom:6px;">
    ❌ 申诉未通过受理
  </div>
  <div style="font-size:13px;color:#b91c1c;line-height:1.65;">
    您提交的申诉材料未满足复核标准（缺乏可核实的具体证据），本次申诉不予受理。<br/>
    如您有新的证明材料（项目链接、量化成果、证书等），
    可通过投递邮箱重新提交，校招团队将再次评估。
  </div>
</div>""")

    elif st.session_state.get(ao_key):
        # ── 申诉表单：结构化填写 ─────────────────────────────────────────
        st.html("""
<div style="background:white;border:1.5px solid #e5e7eb;border-radius:16px;
            padding:20px 22px;box-shadow:0 2px 10px rgba(0,0,0,.06);">
  <div style="font-size:15px;font-weight:700;color:#111827;margin-bottom:6px;">
    申请评估复核
  </div>
  <div style="font-size:13px;color:#6b7280;line-height:1.65;margin-bottom:16px;
              padding-bottom:14px;border-bottom:1px solid #f0f0f0;">
    请指定您认为评估有误的维度，并说明 AI 可能遗漏的具体证据。
  </div>
</div>""")

        dim_label_to_id = {d["label"]: d["id"] for d in display_dims}
        selected_labels = st.multiselect(
            "您认为哪些维度的评估存在偏差？",
            options=[d["label"] for d in display_dims],
            key=f"ap_dims_{sel}",
            placeholder="选择维度（可多选）",
        )

        # 申诉内容质量校验
        _VAGUE_PATTERNS = [
            "不公平", "觉得", "感觉", "应该", "就是不对", "不对", "很好",
            "很强", "很棒", "挺好", "还不错", "比较好", "有点", "有些",
        ]
        _MIN_CHARS = 30  # 每条补充说明至少 30 字

        def _check_evidence(text: str) -> str | None:
            """返回错误提示，None 表示通过。"""
            stripped = text.strip()
            if len(stripped) < _MIN_CHARS:
                return f"内容太短（{len(stripped)} 字），请至少补充 {_MIN_CHARS} 字的具体证据"
            vague_hits = [p for p in _VAGUE_PATTERNS if p in stripped]
            # 只有纯主观表达（无任何数字/项目/链接等具体信息）才拦截
            has_concrete = any(c.isdigit() for c in stripped) or any(
                kw in stripped for kw in ["项目", "实习", "GitHub", "github",
                                           "代码", "论文", "比赛", "奖", "作品",
                                           "链接", "经历", "负责", "开发", "实现",
                                           "完成", "数据", "分析", "报告"]
            )
            if vague_hits and not has_concrete:
                return f"「{'、'.join(vague_hits[:2])}」属于主观表述，请补充可核实的具体事实（项目名称、量化结果、链接等）"
            return None

        ap_evidence: dict[str, str] = {}
        # 上次提交失败的错误（仅在点击提交后才显示）
        submit_errors: dict[str, str] = st.session_state.get(f"ap_errs_{sel}", {})

        for label in selected_labels:
            dim_id = dim_label_to_id[label]
            ev = st.text_area(
                f"关于「{label}」的补充说明",
                key=f"ap_ev_{sel}_{dim_id}",
                placeholder=(
                    "请提供可核实的具体证据，例如：\n"
                    "· 项目名称 + 你负责的具体模块 + 量化结果\n"
                    "· GitHub / 作品集链接\n"
                    "· 相关比赛奖项或证书名称\n"
                    "（至少 30 字；「我觉得不公平」等主观表述将被拦截）"
                ),
                height=100,
            )
            ap_evidence[dim_id] = ev
            # 只显示上次提交失败留下的错误
            if dim_id in submit_errors:
                st.html(f"""
<div style="background:#fef2f2;border:1px solid #fecaca;border-radius:8px;
            padding:7px 12px;font-size:12px;color:#991b1b;margin-top:-4px;margin-bottom:4px;">
  🚫 {submit_errors[dim_id]}
</div>""")

        can_submit = (
            len(selected_labels) > 0
            and all(v.strip() for v in ap_evidence.values())
        )

        ca, sb = st.columns(2)
        with ca:
            if st.button("取消", key=f"ap_cancel_{sel}", use_container_width=True):
                st.session_state[ao_key] = False
                st.session_state.pop(f"ap_errs_{sel}", None)
                st.rerun()
        with sb:
            if st.button("提交申诉", type="primary", disabled=not can_submit,
                         key=f"ap_sub_{sel}", use_container_width=True):
                # 提交时统一校验
                errors = {
                    dim_label_to_id[lbl]: _check_evidence(ap_evidence[dim_label_to_id[lbl]])
                    for lbl in selected_labels
                    if _check_evidence(ap_evidence[dim_label_to_id[lbl]])
                }
                if errors:
                    st.session_state[f"ap_errs_{sel}"] = errors
                    st.rerun()
                else:
                    st.session_state.pop(f"ap_errs_{sel}", None)
                    ap_text = "\n".join(
                        f"[{lbl}] {ap_evidence[dim_label_to_id[lbl]]}"
                        for lbl in selected_labels
                    )
                    save_appeal(sel, cand["name"], ap_text)
                    st.session_state.appeal_submitted.add(sel)
                    st.session_state[f"ap_revealed_{sel}"] = [
                        dim_label_to_id[l] for l in selected_labels
                    ]
                    st.session_state[ao_key] = False
                    st.rerun()

    else:
        # ── 入口按钮 ──────────────────────────────────────────────────────
        if st.button("对评估结果有异议，申请复核 →", key=f"ao_btn_{sel}"):
            st.session_state[ao_key] = True
            st.rerun()



# ─── Page 5：候选人规则验证 ──────────────────────────────────────────────────
def render_verification():
    st.html(f"""
<div style="margin-bottom:16px;">
  <div style="display:flex;align-items:center;gap:10px;margin-bottom:6px;">
    <h2 style="font-size:22px;font-weight:800;color:#111827;margin:0;">候选人规则验证</h2>
    {_role_badge("候选人视角")}
  </div>
  <p style="font-size:14px;color:#6b7280;margin:0;">
    粘贴收到的岗位 JD → AI 提取评估维度 → 调整至与 HR 一致的权重 → 生成指纹 → 与邮件对比
  </p>
</div>""")

    # 原理说明
    st.html("""
<div style="background:#F0F4FA;border:1px solid #C8D8EA;border-radius:12px;
            padding:16px 18px;font-size:13px;color:#3D3A36;line-height:1.7;margin-bottom:16px;">
  <strong>🔍 验证原理</strong><br/>
  规则指纹（Hash）由「<strong>维度名称 + 权重</strong>」列表计算得出。
  由于评估维度与 JD 任职要求<strong>一一对应</strong>，只要你手上有相同的 JD 原文，
  用相同的 AI 提取后得到的维度名称应完全一致。<br/>
  将权重调整为与 HR 公示的权重相同后，生成的指纹若与邮件中的一致，
  即可证明规则<strong>自发布后未被修改</strong>。<br/><br/>
  <strong>📌 本系统使用模型</strong>：<code>claude-3.5-haiku</code>（经由 OpenRouter）。
  候选人可在 <a href="https://openrouter.ai" target="_blank" style="color:#2D4A7A;text-decoration:underline;">openrouter.ai</a>
  选择同款模型，粘贴相同 JD 原文，所提取的维度名称应与公示页完全一致。
</div>""")

    if not has_api_key():
        # ── 离线演示模式：选择预设岗位，跳过 AI 提取 ──────────────────────
        st.html("""
<div style="background:#fffbeb;border:1.5px solid #fde68a;border-radius:12px;
            padding:12px 18px;margin:8px 0 16px;
            display:flex;align-items:center;gap:10px;font-size:13px;color:#92400e;">
  <span style="font-size:18px;">📋</span>
  <div>
    <strong>离线演示模式</strong> — 未配置 API Key，AI 提取功能不可用。<br/>
    <span style="font-size:12px;color:#b45309;">选择预设岗位可完整体验维度权重调整与规则指纹验证。</span>
  </div>
</div>""")
        st.html('<p style="font-size:14px;font-weight:600;color:#374151;margin:0 0 8px;">① 选择预设岗位（替代 JD 文本输入）</p>')
        _oc1, _oc2 = st.columns(2)
        with _oc1:
            if st.button("🎯 产品经理岗", key="offline_pm", use_container_width=True):
                st.session_state["verify_dims"] = copy.deepcopy(JOB_PRESETS["pm"]["dims"])
                st.session_state["offline_job"] = "pm"
                for _d in JOB_PRESETS["pm"]["dims"]:
                    st.session_state[f"vw_{_d['id']}"] = _d["weight"]
                st.rerun()
        with _oc2:
            if st.button("⚙️ 后端开发岗", key="offline_dev", use_container_width=True):
                st.session_state["verify_dims"] = copy.deepcopy(JOB_PRESETS["dev"]["dims"])
                st.session_state["offline_job"] = "dev"
                for _d in JOB_PRESETS["dev"]["dims"]:
                    st.session_state[f"vw_{_d['id']}"] = _d["weight"]
                st.rerun()

        _off_job = st.session_state.get("offline_job")
        if _off_job:
            _off_preset = JOB_PRESETS[_off_job]
            st.html(f"""
<div style="background:#f0fdf4;border:1px solid #86efac;border-radius:10px;
            padding:10px 14px;margin:8px 0;font-size:13px;color:#166534;">
  ✅ 已加载「{_off_preset["label"]}」预设维度（共 {len(_off_preset["dims"])} 个）
  — 验证维度名称与权重的 Hash 计算过程同线上完全一致
</div>""")
            if st.button("📋 查看岗位 JD", key="jd_btn_verify"):
                _jd_dialog(_off_preset["label"], _off_preset["jd"])
    else:
        # ── 在线模式：JD 文本输入 + AI 提取 ────────────────────────────
        st.html('<p style="font-size:14px;font-weight:600;color:#374151;margin:0 0 6px;">① 粘贴岗位 JD（需包含「任职要求」部分）</p>')
        jd_input = st.text_area(
            "JD 文本",
            key="verify_jd",
            height=200,
            placeholder="将招聘 JD 全文粘贴至此，系统将自动识别「任职要求」部分……",
            label_visibility="collapsed",
        )

        if st.button("🤖 AI 提取评估维度", key="verify_extract",
                     disabled=not jd_input.strip(), type="primary"):
            with st.spinner("AI 正在从任职要求中提取评估维度…"):
                dims, err = extract_dims_from_jd(jd_input.strip(), "待验证岗位")
            if dims:
                st.session_state["verify_dims"] = dims
                for d in dims:
                    st.session_state[f"vw_{d['id']}"] = d["weight"]
                st.rerun()
            else:
                st.error(f"维度提取失败：{err}")

    verify_dims = st.session_state.get("verify_dims")
    if not verify_dims:
        if not has_api_key():
            st.html('<p style="font-size:13px;color:#9ca3af;margin-top:8px;">👆 请先选择上方预设岗位</p>')
        return

    st.markdown('<div style="height:8px;"></div>', unsafe_allow_html=True)

    # ── 一键加载锁定规则权重 ──────────────────────────────────────────────────
    _off_job = st.session_state.get("offline_job")
    _locked  = st.session_state.get("locked_jobs", {})
    if _off_job and _off_job in _locked:
        _locked_dims = _locked[_off_job]["dims"]
        _locked_fp   = _locked[_off_job]["fingerprint"]
        _col_load, _col_info = st.columns([1, 2])
        with _col_load:
            if st.button("🔒 一键加载已锁定规则权重", key="load_locked_weights",
                         use_container_width=True, type="primary"):
                for _d in _locked_dims:
                    st.session_state[f"vw_{_d['id']}"] = _d["weight"]
                st.rerun()
        with _col_info:
            st.html(f'<p style="font-size:12px;color:#2563EB;margin:10px 0 0;">'
                    f'HR 已锁定规则指纹：<code style="font-weight:700;">{_locked_fp}</code>'
                    f'，加载权重后验证指纹是否一致</p>')
    st.markdown('<div style="height:4px;"></div>', unsafe_allow_html=True)

    # Step 2：展示维度 & 调整权重
    st.html('<p style="font-size:14px;font-weight:600;color:#374151;margin:0 0 6px;">② 确认维度名称，并调整权重至与 HR 公示的一致</p>')

    dim_rows_html = "".join(
        f"""<div style="display:flex;align-items:center;justify-content:space-between;
                        padding:9px 0;border-bottom:1px solid #f3f4f6;">
  <span style="font-size:13px;font-weight:500;color:#111827;">
    {i+1}. {d['label']}
  </span>
  <span style="font-size:11px;color:#9ca3af;">（与 JD 第{i+1}条任职要求对应）</span>
</div>"""
        for i, d in enumerate(verify_dims)
    )
    st.html(f"""
<div style="background:white;border:1px solid #e5e7eb;border-radius:12px;
            padding:12px 16px;margin-bottom:12px;
            box-shadow:0 1px 3px rgba(0,0,0,.05);">
  <p style="font-size:11px;font-weight:600;color:#9ca3af;text-transform:uppercase;
             letter-spacing:.06em;margin:0 0 4px;">AI 提取的维度名称（来自 JD 任职要求原文）</p>
  {dim_rows_html}
</div>""")

    with st.container(border=True):
        st.markdown('<span style="font-size:13px;font-weight:600;color:#374151;">权重设置</span>',
                    unsafe_allow_html=True)
        new_dims = []
        total = 0
        for d in verify_dims:
            w = st.slider(
                d["label"], min_value=5, max_value=60,
                value=st.session_state.get(f"vw_{d['id']}", d["weight"]),
                step=5, key=f"vw_{d['id']}", format="%d%%",
            )
            new_dims.append({**d, "weight": w})
            total += w

        if total == 100:
            st.html('<span style="background:#dcfce7;color:#166534;border-radius:999px;'
                    'padding:3px 12px;font-size:13px;font-weight:600;">✅ 总计 100%</span>')
        else:
            st.html(f'<span style="background:#fef3c7;color:#92400e;border-radius:999px;'
                    f'padding:3px 12px;font-size:13px;font-weight:600;">⚠ 总计 {total}%，需调整至 100%</span>')

    # Step 3：生成指纹
    st.markdown('<div style="height:8px;"></div>', unsafe_allow_html=True)
    st.html('<p style="font-size:14px;font-weight:600;color:#374151;margin:0 0 6px;">③ 生成规则指纹，与邮件中的指纹对比</p>')

    if total == 100:
        fp = rule_fingerprint(new_dims)
        st.html(f"""
<div style="background:#111827;border-radius:16px;padding:24px 28px;color:white;">
  <p style="font-size:11px;color:#9ca3af;text-transform:uppercase;
             letter-spacing:.06em;margin:0 0 10px;">生成的规则指纹</p>
  <div style="font-family:monospace;font-size:36px;font-weight:900;
              color:#6ee7b7;letter-spacing:.2em;margin-bottom:14px;">{fp}</div>
  <div style="background:rgba(255,255,255,.07);border-radius:10px;padding:12px 14px;
              font-size:12px;color:#9ca3af;line-height:1.7;">
    将此指纹与你收到的邮件中的指纹对比：<br/>
    <span style="color:#6ee7b7;font-weight:600;">✓ 一致</span>
    → 规则自发布后未被修改，评估过程可信<br/>
    <span style="color:#f87171;font-weight:600;">✗ 不一致</span>
    → 权重可能未调整到位，或维度名称存在差异（见下方排查提示）
  </div>
</div>""")

        # 排查说明
        st.markdown('<div style="height:10px;"></div>', unsafe_allow_html=True)
        with st.expander("指纹不一致？查看排查步骤", expanded=False):
            st.markdown("""
**可能原因及排查方法：**

1. **权重不一致** — 查看公司发布的规则公示页，确认每个维度的权重数值后重新设置
2. **维度名称细微差异** — AI 每次提取时措辞可能略有不同。
   对比上方提取到的维度名称与公示页中的维度名称，若有出入，以公示页为准
3. **JD 版本不同** — 请使用投递时收到的原始 JD 文本，而非岗位招聘页的当前版本

> 指纹算法：FNV-1a Hash，输入为「维度名称 + 权重」的 JSON 序列，与系统完全一致
""")
    else:
        st.html("""
<div style="background:#f9fafb;border:2px dashed #e5e7eb;border-radius:16px;
            padding:32px;text-align:center;color:#9ca3af;font-size:14px;">
  将权重总计调整为 100% 后，指纹将在此显示
</div>""")

    # 重置
    st.markdown('<div style="height:12px;"></div>', unsafe_allow_html=True)
    if st.button("🔄 重新输入 JD", key="verify_reset"):
        st.session_state.pop("verify_dims", None)
        st.session_state.pop("verify_jd", None)
        st.rerun()


# ─── 渲染入口 ─────────────────────────────────────────────────────────────────
render_header()

_pending_appeals = len([a for a in get_all_appeals()
                        if a.get("status", "pending") == "pending"])
_appeal_tab_label = f"📊 筛选工作台{' 🔴' if _pending_appeals else ''}"

tab1, tab2, tab3, tab4 = st.tabs([
    "🏗 规则构建",
    _appeal_tab_label,
    "👤 候选人视图",
    "🔍 规则验证",
])

with tab1:
    render_rule_builder()
with tab2:
    render_screening()
with tab3:
    render_candidate_view()
with tab4:
    render_verification()

# ── 申诉输入框实时字数计数器（JS注入父文档）─────────────────────────────────────
st.components.v1.html("""
<script>
(function() {
  var MIN = 30;
  var doc = window.parent ? window.parent.document : document;

  function attachCounters() {
    doc.querySelectorAll('[data-testid="stTextArea"]').forEach(function(wrapper) {
      var label = wrapper.querySelector('label');
      if (!label || !label.textContent.includes('补充说明')) return;
      if (wrapper.querySelector('.ap-char-counter')) return;

      var ta = wrapper.querySelector('textarea');
      if (!ta) return;

      var counter = doc.createElement('div');
      counter.className = 'ap-char-counter';
      counter.style.cssText = [
        'font-size:11px', 'text-align:right', 'margin-top:4px',
        'margin-bottom:6px', 'padding-right:2px', 'font-variant-numeric:tabular-nums'
      ].join(';');
      wrapper.appendChild(counter);

      function update() {
        var n = ta.value.trim().length;
        counter.textContent = n + ' / ' + MIN + ' 字';
        counter.style.color = n >= MIN ? '#16a34a' : n > 0 ? '#d97706' : '#9ca3af';
        counter.style.fontWeight = n >= MIN ? '600' : '400';
      }
      ta.addEventListener('input', update);
      update();
    });
  }

  attachCounters();
  new MutationObserver(attachCounters).observe(doc.body, { childList: true, subtree: true });
})();
</script>
""", height=0)

# ── 悬浮置顶按钮 ────────────────────────────────────────────────────────────────
# 原理：通过 window.frameElement 拿到 iframe 自身在父文档中的 DOM 节点，
# 然后把 Streamlit 的 element-container 改为 position:fixed，
# 使 iframe 脱离页面流、固定在屏幕右下角——从而按钮始终可见。
st.components.v1.html("""
<style>
  html,body{margin:0;padding:0;background:transparent;overflow:hidden;}
</style>
<button
  id="top-btn"
  onmouseenter="this.style.transform='scale(1.1)'"
  onmouseleave="this.style.transform='scale(1)'"
  title="回到顶部"
  style="width:48px;height:48px;border-radius:50%;
         background:#1A1714;
         color:#FEFCF9;border:none;cursor:pointer;
         font-size:24px;font-weight:700;line-height:1;
         box-shadow:0 4px 20px rgba(30,41,59,.38),0 1px 4px rgba(0,0,0,.14);
         display:flex;align-items:center;justify-content:center;
         transition:transform .28s cubic-bezier(0.34,1.56,0.64,1);
         margin:4px;">&#8679;</button>
<script>
(function fix(){
  var me = window.frameElement;   // 我们自己的 <iframe> 元素
  if (!me) return;

  /* 向上找 Streamlit 的 element-container（通常在 iframe 上 2 层）*/
  var el = me;
  for (var i = 0; i < 6; i++) {
    el = el.parentElement;
    if (!el) break;
    if (el.classList && el.classList.contains('element-container')) break;
  }
  var target = el || me.parentElement;

  /* 把这个容器改为 position:fixed，钉在右下角 */
  var props = {
    position : 'fixed',
    bottom   : '36px',
    right    : '36px',
    width    : '56px',
    height   : '56px',
    zIndex   : '2147483647',
    margin   : '0',
    padding  : '0',
    overflow : 'visible',
  };
  for (var p in props) {
    target.style.setProperty(
      p.replace(/([A-Z])/g, '-$1').toLowerCase(),
      props[p],
      'important'
    );
  }
  /* iframe 本身也缩成和容器一样大 */
  me.style.setProperty('width',  '56px', 'important');
  me.style.setProperty('height', '56px', 'important');
  me.style.setProperty('border', 'none', 'important');
  me.style.setProperty('background', 'transparent', 'important');

  /* ── 点击：遍历所有可能的 Streamlit 滚动容器，找到真正在滚的那个 ── */
  document.getElementById('top-btn').addEventListener('click', function() {
    var pdoc = window.parent.document;
    var candidates = [
      pdoc.querySelector('[data-testid="stMain"]'),
      pdoc.querySelector('[data-testid="stAppViewContainer"]'),
      pdoc.querySelector('.main'),
      pdoc.querySelector('.stApp'),
      pdoc.documentElement,
      pdoc.body,
      window.parent,
    ];
    candidates.forEach(function(el) {
      if (!el) return;
      try {
        // 只滚动 scrollTop > 0 的元素（真正在滚的那个）
        var top = el.scrollTop !== undefined ? el.scrollTop : el.scrollY;
        if (top > 0) {
          if (typeof el.scrollTo === 'function') {
            el.scrollTo({ top: 0, behavior: 'smooth' });
          } else {
            el.scrollTop = 0;
          }
        }
      } catch(e) {}
    });
  });
})();
</script>
""", height=56)

# ── Tab 跳转：rerun 后注入 JS 点击目标 Tab ───────────────────────────────────
_goto = st.session_state.get("goto_tab", -1)
if _goto >= 0:
    st.session_state.goto_tab = -1   # 立即重置，避免循环触发
    st.components.v1.html(f"""
<script>
  // 等 Streamlit 渲染完 Tab DOM 再点击
  (function click(attempt) {{
    var tabs = window.parent.document.querySelectorAll('[data-baseweb="tab"]');
    if (tabs.length > {_goto}) {{
      tabs[{_goto}].click();
    }} else if (attempt < 20) {{
      setTimeout(function() {{ click(attempt + 1); }}, 80);
    }}
  }})(0);
</script>
""", height=0)
