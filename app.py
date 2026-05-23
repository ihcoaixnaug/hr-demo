# app.py — 智筛 AI · Streamlit（精美 UI 版，对齐原 demo.html 风格）

import copy
import time
from datetime import datetime

import streamlit as st

from data import JOB_PRESETS, CANDIDATES, CANDIDATES_MAP
from utils import rule_fingerprint, weighted_score, result_color, build_public_page_html
from database import (
    init_db, save_rule,
    save_screening_result, get_screening_results,
    save_hr_override, get_hr_overrides,
    add_to_pool_db, remove_from_pool_db, get_pool_db,
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
/* ══ 基础重置 ══════════════════════════════════════════════════════════════ */
html,body,[class*="css"]{
  font-family:-apple-system,"PingFang SC","SF Pro Text",BlinkMacSystemFont,
    "Segoe UI",sans-serif!important;
  -webkit-font-smoothing:antialiased!important;
}
.stApp{background:#f0f2f5!important;}
.stMainBlockContainer,.block-container{
  max-width:900px!important;
  margin:0 auto!important;
  padding:20px 20px 100px!important;
}

/* ══ 隐藏 Streamlit chrome ══════════════════════════════════════════════════ */
#MainMenu,footer,.stDeployButton{display:none!important;}
[data-testid="stToolbar"]{display:none!important;}
header[data-testid="stHeader"]{display:none!important;}

/* ══ Tab 导航 ══════════════════════════════════════════════════════════════ */
.stTabs [data-baseweb="tab-list"]{
  background:white!important;
  border:1px solid #e5e7eb!important;
  border-radius:14px!important;
  padding:5px!important;
  gap:2px!important;
  box-shadow:0 1px 4px rgba(0,0,0,.07),0 0 0 0 transparent!important;
  margin-bottom:6px!important;
  display:flex!important;
  width:100%!important;
}
.stTabs [data-baseweb="tab"]{
  background:transparent!important;
  color:#6b7280!important;
  font-size:13px!important;
  font-weight:500!important;
  padding:7px 14px!important;
  border-radius:10px!important;
  margin:0!important;
  transition:all .18s ease!important;
  white-space:nowrap!important;
  flex:1!important;
  justify-content:center!important;
  display:flex!important;
}
.stTabs [aria-selected="true"]{
  color:#1d4ed8!important;
  background:linear-gradient(135deg,#eff6ff,#e0eaff)!important;
  font-weight:700!important;
  box-shadow:0 1px 3px rgba(59,130,246,.18)!important;
}
.stTabs [data-baseweb="tab-highlight"]{display:none!important;}
.stTabs [data-baseweb="tab-border"]{display:none!important;}
.stTabs [data-baseweb="tab-panel"]{padding:14px 0 0!important;}

/* ══ Primary 按钮 ══════════════════════════════════════════════════════════ */
.stButton>button[kind="primary"]{
  background:linear-gradient(135deg,#2563eb 0%,#1e1b4b 100%)!important;
  color:white!important;
  border:none!important;
  border-radius:10px!important;
  font-size:14px!important;
  font-weight:600!important;
  padding:10px 24px!important;
  letter-spacing:.01em!important;
  box-shadow:0 2px 10px rgba(37,99,235,.30),0 1px 2px rgba(0,0,0,.12)!important;
  transition:all .18s ease!important;
  white-space:nowrap!important;
}
.stButton>button[kind="primary"]:hover:not(:disabled){
  background:linear-gradient(135deg,#1d4ed8 0%,#312e81 100%)!important;
  box-shadow:0 4px 16px rgba(37,99,235,.40),0 2px 4px rgba(0,0,0,.14)!important;
  transform:translateY(-1px)!important;
}
.stButton>button[kind="primary"]:active:not(:disabled){
  transform:translateY(0)!important;
  box-shadow:0 1px 4px rgba(37,99,235,.25)!important;
}

/* ══ Secondary / 默认按钮 ══════════════════════════════════════════════════ */
.stButton>button{
  border-radius:8px!important;
  font-size:13px!important;
  font-weight:500!important;
  padding:7px 14px!important;
  border:1px solid #e2e8f0!important;
  color:#374151!important;
  background:white!important;
  box-shadow:0 1px 2px rgba(0,0,0,.06)!important;
  transition:all .15s ease!important;
  white-space:nowrap!important;
  overflow:visible!important;
}
.stButton>button:hover:not(:disabled){
  border-color:#93c5fd!important;
  background:#f5f8ff!important;
  color:#1d4ed8!important;
  box-shadow:0 2px 8px rgba(59,130,246,.15)!important;
  transform:translateY(-1px)!important;
}
.stButton>button:active:not(:disabled){transform:translateY(0)!important;}
.stButton>button:disabled{opacity:.38!important;cursor:not-allowed!important;}

/* ══ Slider ══════════════════════════════════════════════════════════════ */
[data-testid="stSlider"] [role="slider"]{
  background:#2563eb!important;
  box-shadow:0 0 0 3px rgba(37,99,235,.18)!important;
}
[data-testid="stSlider"] [data-testid="stSliderThumbValue"]{
  background:#1d4ed8!important;color:white!important;
  font-family:monospace!important;font-size:11px!important;
  border-radius:5px!important;
  box-shadow:0 2px 6px rgba(29,78,216,.3)!important;
}
[data-testid="stSlider"] > div > div > div > div{
  background:linear-gradient(to right,#3b82f6,#2563eb)!important;
  border-radius:999px!important;
}
[data-testid="stSlider"] label{font-size:13px!important;font-weight:500!important;color:#374151!important;}

/* ══ Input / Textarea ══════════════════════════════════════════════════════ */
.stTextInput input,.stTextArea textarea{
  border-radius:10px!important;
  border:1.5px solid #e5e7eb!important;
  font-size:13.5px!important;
  color:#1f2937!important;
  background:white!important;
  box-shadow:0 1px 3px rgba(0,0,0,.05)!important;
  transition:border-color .15s,box-shadow .15s!important;
}
.stTextInput input:focus,.stTextArea textarea:focus{
  border-color:#60a5fa!important;
  box-shadow:0 0 0 3px rgba(59,130,246,.14)!important;
  outline:none!important;
}
.stTextArea label,.stTextInput label{
  font-size:12px!important;color:#6b7280!important;font-weight:500!important;
}

/* ══ Checkbox ══════════════════════════════════════════════════════════════ */
.stCheckbox label{font-size:13.5px!important;color:#374151!important;}
.stCheckbox [data-testid="stCheckbox"]:hover label{color:#1d4ed8!important;}

/* ══ Metric 卡片 ══════════════════════════════════════════════════════════ */
[data-testid="metric-container"]{
  background:white!important;
  border:1px solid #e5e7eb!important;
  border-radius:14px!important;
  padding:18px 20px!important;
  box-shadow:0 2px 8px rgba(0,0,0,.06),0 0 0 0 transparent!important;
  transition:box-shadow .2s!important;
}
[data-testid="metric-container"]:hover{
  box-shadow:0 4px 14px rgba(0,0,0,.10)!important;
}
[data-testid="stMetricValue"]{
  font-size:26px!important;font-weight:800!important;
  color:#111827!important;letter-spacing:-.02em!important;
}
[data-testid="stMetricLabel"]{
  font-size:11.5px!important;color:#9ca3af!important;
  font-weight:500!important;text-transform:uppercase!important;
  letter-spacing:.04em!important;
}

/* ══ Alerts ══════════════════════════════════════════════════════════════ */
.stAlert{border-radius:12px!important;font-size:13px!important;}

/* ══ Expander ══════════════════════════════════════════════════════════════ */
.stExpander{
  border:1px solid #e5e7eb!important;
  border-radius:14px!important;
  background:white!important;
  box-shadow:0 1px 4px rgba(0,0,0,.06)!important;
  overflow:hidden!important;
}
.stExpander summary{
  font-size:13px!important;font-weight:600!important;color:#374151!important;
  padding:12px 16px!important;
}
.stExpander summary:hover{background:#f9fafb!important;}

/* ══ Border container ══════════════════════════════════════════════════════ */
div[data-testid="stVerticalBlockBorderWrapper"]{
  border-radius:16px!important;
  box-shadow:0 1px 4px rgba(0,0,0,.07)!important;
  border:1px solid #e5e7eb!important;
  background:white!important;
}

/* ══ Progress bar ══════════════════════════════════════════════════════════ */
[data-testid="stProgress"] > div > div{
  background:linear-gradient(to right,#3b82f6,#2563eb)!important;
  border-radius:999px!important;
}

/* ══ 全局间距 ══════════════════════════════════════════════════════════════ */
.element-container{margin-bottom:4px!important;}
div[data-testid="stVerticalBlock"]>div{gap:6px!important;}

/* ══ 候选人卡片操作按钮行：确保文字不截断 ═══════════════════════════════════ */
.cand-action-btn .stButton>button{
  font-size:12.5px!important;
  padding:6px 10px!important;
  min-width:0!important;
  width:100%!important;
}

/* ══ Divider ══════════════════════════════════════════════════════════════ */
hr{border:none!important;border-top:1px solid #f0f0f0!important;margin:8px 0!important;}

/* ══ Caption ══════════════════════════════════════════════════════════════ */
.stCaption,.stCaption p{
  font-size:12px!important;color:#9ca3af!important;line-height:1.5!important;
}

/* ══ 隐藏 textarea 的 ⌘+Enter 提示 ══════════════════════════════════════ */
[data-testid="InputInstructions"]{display:none!important;}
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
        "pool":              [],
        "appeal_submitted":  set(),
        "public_html":       "",
        "hiring_target":     120,
        "goto_tab":          -1,
        "cv_selected":       "B",
    }
    for k, v in defs.items():
        if k not in st.session_state:
            st.session_state[k] = v

_init()
init_db()

def _sync_pool():
    st.session_state.pool = get_pool_db()
_sync_pool()


# ─── HTML 辅助函数 ────────────────────────────────────────────────────────────

COLOR_MAP = {
    "green":  {"bg":"#f0fdf4","border":"#86efac","badge_bg":"#dcfce7","badge_text":"#166534"},
    "yellow": {"bg":"#fffbeb","border":"#fde68a","badge_bg":"#fef3c7","badge_text":"#92400e"},
    "red":    {"bg":"#fef2f2","border":"#fecaca","badge_bg":"#fee2e2","badge_text":"#991b1b"},
}
TAG_COLOR = {
    "985":  ("bg:#ede9fe","color:#5b21b6"),
    "211":  ("bg:#dbeafe","color:#1e40af"),
    "双非": ("bg:#f3f4f6","color:#4b5563"),
    "职校": ("bg:#fff7ed","color:#c2410c"),
    "自学": ("bg:#f0fdf4","color:#166534"),
}
DEGREE_COLOR = {
    "本科": ("bg:#eff6ff","color:#1d4ed8"),
    "硕士": ("bg:#faf5ff","color:#7c3aed"),
    "博士": ("bg:#fdf4ff","color:#a21caf"),
    "大专": ("bg:#fff7ed","color:#b45309"),
    "高中": ("bg:#f0fdf4","color:#15803d"),
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
            bar_color = "linear-gradient(to right,#34d399,#10b981)"
            num_color = "#059669"
        elif v >= 65:
            bar_color = "linear-gradient(to right,#60a5fa,#3b82f6)"
            num_color = "#2563eb"
        elif v >= 50:
            bar_color = "linear-gradient(to right,#fbbf24,#f59e0b)"
            num_color = "#d97706"
        else:
            bar_color = "linear-gradient(to right,#f87171,#ef4444)"
            num_color = "#dc2626"
        rows.append(f"""
<div style="display:grid;grid-template-columns:8rem 1fr 2.2rem;gap:8px;
            align-items:center;margin-bottom:7px;">
  <span style="font-size:12px;color:#6b7280;white-space:nowrap;">
    {d["label"]}<span style="color:#d1d5db;font-size:11px;margin-left:3px;">{d["weight"]}%</span>
  </span>
  <div style="background:#f1f5f9;border-radius:999px;height:7px;overflow:hidden;">
    <div style="width:{v}%;height:7px;background:{bar_color};
                border-radius:999px;transition:width .5s ease;"></div>
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
    """渲染视角标签：HR视角（蓝）/ 候选人视角（绿）"""
    cfg = {
        "HR 视角":   ("#eff6ff", "#1d4ed8", "#bfdbfe", "👔"),
        "候选人视角": ("#f0fdf4", "#166534", "#86efac", "🎓"),
    }
    bg, tc, border, icon = cfg.get(role, ("#f9fafb", "#374151", "#e5e7eb", "👤"))
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


# ─── 简历弹窗（Dialog） ────────────────────────────────────────────────────────
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
    pn = len(st.session_state.pool)
    if pn:
        badges_html += (
            f'<span style="background:#f59e0b;color:#fff;border-radius:999px;'
            f'padding:3px 10px;font-size:12px;margin-left:6px;">📦 备选池 {pn}</span>'
        )
    if not has_api_key():
        badges_html += (
            '<span style="background:#fef3c7;color:#92400e;border-radius:999px;'
            'padding:3px 10px;font-size:12px;margin-left:6px;">⚠ 预设数据模式</span>'
        )

    st.html(f"""
<div style="background:white;border:1px solid #e5e7eb;border-radius:18px;
            padding:14px 22px;margin-bottom:14px;
            box-shadow:0 2px 12px rgba(0,0,0,.08);
            display:flex;align-items:center;justify-content:space-between;gap:12px;">
  <div style="display:flex;align-items:center;gap:14px;">
    <div style="width:40px;height:40px;flex-shrink:0;
                background:linear-gradient(135deg,#2563eb 0%,#1e1b4b 100%);
                border-radius:12px;
                display:flex;align-items:center;justify-content:center;
                box-shadow:0 3px 10px rgba(37,99,235,.35);">
      <span style="color:white;font-weight:900;font-size:17px;letter-spacing:-.5px;">智</span>
    </div>
    <div style="line-height:1.2;">
      <div style="font-weight:800;font-size:18px;color:#111827;letter-spacing:-.02em;">智筛 AI</div>
      <div style="font-size:12px;color:#9ca3af;margin-top:1px;">Trustworthy Resume Screening</div>
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
<div style="background:linear-gradient(160deg,#111827 0%,#1e1b4b 100%);
            border-radius:18px;padding:22px 24px;color:white;margin-bottom:0;
            box-shadow:0 4px 20px rgba(17,24,39,.35);">
  <div style="display:flex;align-items:center;gap:10px;margin-bottom:4px;">
    <span style="font-size:16px;">🔒</span>
    <span style="font-size:15px;font-weight:700;letter-spacing:-.01em;">{jl_l} · 规则已锁定 · 不可修改</span>
  </div>
  <p style="font-size:12px;color:#9ca3af;margin:0 0 18px;">锁定时间：{at_l}</p>
  <div style="background:rgba(110,231,183,.08);border:1px solid rgba(110,231,183,.2);
              border-radius:12px;padding:16px 18px;margin-bottom:16px;">
    <p style="font-size:11px;color:#6b7280;margin:0 0 8px;text-transform:uppercase;
               letter-spacing:.06em;font-weight:600;">RULE HASH · 规则指纹</p>
    <span style="font-family:'SF Mono',ui-monospace,monospace;font-size:26px;
                 color:#6ee7b7;font-weight:900;letter-spacing:.2em;">{fp_l}</span>
    <p style="font-size:11.5px;color:#6b7280;margin:8px 0 0;line-height:1.5;">
      规则内容改变则指纹随之改变 · 候选人可使用相同 JD 独立验证
    </p>
  </div>
  <div style="font-size:12px;color:#93c5fd;margin-bottom:12px;display:flex;align-items:center;gap:6px;">
    <span>🔗</span>
    <span>规则已同步公示页，候选人收到的投递确认邮件含本指纹</span>
  </div>
  <div style="display:flex;flex-wrap:wrap;">{dim_chips}</div>
</div>
""", unsafe_allow_html=True)

            st.markdown('<div style="margin-top:-10px;"></div>', unsafe_allow_html=True)
            _ca, _cb, _cc = st.columns([4, 4, 2])
            with _ca:
                with st.expander(f"📋 查看{jl_l} JD"):
                    st.code(preset_l["jd"], language=None)
            with _cb:
                st.markdown('<div style="margin-top:5px;"></div>', unsafe_allow_html=True)
                if st.button("📄 查看规则公示页", key=f"open_pub_{jk_l}"):
                    st.session_state.public_html = build_public_page_html(
                        dims_l, fp_l, at_l, jl_l)
            with _cc:
                st.markdown('<div style="margin-top:5px;"></div>', unsafe_allow_html=True)
                if st.button("🗑 清除规则", key=f"reset_job_{jk_l}"):
                    del st.session_state.locked_jobs[jk_l]
                    if st.session_state.active_job == jk_l:
                        st.session_state.active_job = None
                    st.session_state.selected_job  = None
                    st.session_state.editing_dims  = None
                    st.rerun()
            st.markdown('<div style="height:10px;"></div>', unsafe_allow_html=True)

        if st.session_state.public_html:
            with st.expander("规则公示页预览", expanded=True):
                st.download_button(
                    "⬇ 下载公示页 HTML（可发送给候选人或挂载官网）",
                    data=st.session_state.public_html,
                    file_name="rule_public_page.html", mime="text/html",
                )
                st.components.v1.html(st.session_state.public_html, height=460, scrolling=True)

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
            background:#eff6ff;border:1px solid #93c5fd;border-radius:10px;
            padding:10px 14px;margin:16px 0 8px;font-size:13px;color:#1e40af;">
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

    with st.expander("查看岗位 JD"):
        st.code(preset["jd"], language=None)

    # 维度权重卡
    st.markdown('<br/>', unsafe_allow_html=True)
    with st.container(border=True):
        new_dims = []
        total = 0
        for d in edit_dims:
            w = st.slider(
                d["label"], min_value=5, max_value=60,
                value=st.session_state.get(f"w_{d['id']}", d["weight"]),
                step=5, key=f"w_{d['id']}", format="%d%%",
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
        st.session_state.public_html  = ""
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
    <span style="background:#eff6ff;color:#1d4ed8;border-radius:999px;
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
            bar   = st.progress(0, text="AI 评分中…")
            for idx, cand in enumerate(sel_c):
                bar.progress(idx / len(sel_c), text=f"正在评分：{cand['name']}（{idx+1}/{len(sel_c)}）")
                llm_r = screen_candidate_with_llm(cand, dims, preset["jd"]) if has_api_key() else None
                if llm_r:
                    scores, reasons, ai_r, src = llm_r["scores"], llm_r["reasons"], llm_r["ai_result"], "ai"
                else:
                    scores, reasons, ai_r, src = cand["scores"], cand["reasons"], cand["result"], "preset"
                st.session_state.screening_results[cand["id"]] = {
                    "scores": scores, "reasons": reasons,
                    "ai_result": ai_r, "source": src,
                }
                save_screening_result(cand["id"], rule_id, scores, reasons, ai_r, src)
                time.sleep(0.3)
            bar.progress(1.0, text="✓ 评分完成")
            time.sleep(0.5)
            st.rerun()

    if not results:
        st.html("""
<div style="background:white;border:1px dashed #d1d5db;border-radius:16px;
            padding:48px 32px;text-align:center;margin-top:12px;">
  <div style="font-size:32px;margin-bottom:12px;">🚀</div>
  <div style="font-size:15px;font-weight:600;color:#374151;margin-bottom:6px;">
    选择候选人后点击「开始筛选」
  </div>
  <div style="font-size:13px;color:#9ca3af;line-height:1.7;">
    AI 将按锁定规则逐份评分，每条结论追溯到具体维度<br/>
    评分完成后结果卡片将在此显示
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

    st.html(f"""
<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:10px;margin-bottom:20px;">
  <div style="background:white;border:1px solid #e5e7eb;border-radius:14px;
              padding:16px 18px;box-shadow:0 2px 8px rgba(0,0,0,.06);">
    <div style="font-size:11px;font-weight:600;color:#9ca3af;text-transform:uppercase;
                letter-spacing:.05em;margin-bottom:6px;">本次筛选</div>
    <div style="font-size:28px;font-weight:800;color:#111827;letter-spacing:-.03em;">{n}<span style="font-size:14px;font-weight:500;color:#9ca3af;"> 份</span></div>
  </div>
  <div style="background:linear-gradient(135deg,#f0fdf4,#dcfce7);border:1px solid #86efac;
              border-radius:14px;padding:16px 18px;box-shadow:0 2px 8px rgba(16,185,129,.08);">
    <div style="font-size:11px;font-weight:600;color:#166534;text-transform:uppercase;
                letter-spacing:.05em;margin-bottom:6px;">强推进</div>
    <div style="font-size:28px;font-weight:800;color:#166534;letter-spacing:-.03em;">{s_n}</div>
  </div>
  <div style="background:linear-gradient(135deg,#fffbeb,#fef3c7);border:1px solid #fde68a;
              border-radius:14px;padding:16px 18px;box-shadow:0 2px 8px rgba(245,158,11,.08);">
    <div style="font-size:11px;font-weight:600;color:#92400e;text-transform:uppercase;
                letter-spacing:.05em;margin-bottom:6px;">待定</div>
    <div style="font-size:28px;font-weight:800;color:#92400e;letter-spacing:-.03em;">{p_n}</div>
  </div>
  <div style="background:linear-gradient(135deg,#fef2f2,#fee2e2);border:1px solid #fecaca;
              border-radius:14px;padding:16px 18px;box-shadow:0 2px 8px rgba(239,68,68,.08);">
    <div style="font-size:11px;font-weight:600;color:#991b1b;text-transform:uppercase;
                letter-spacing:.05em;margin-bottom:6px;">不推进</div>
    <div style="font-size:28px;font-weight:800;color:#991b1b;letter-spacing:-.03em;">{rej}</div>
  </div>
  <div style="background:linear-gradient(135deg,#eff6ff,#dbeafe);border:1px solid #93c5fd;
              border-radius:14px;padding:16px 18px;box-shadow:0 2px 8px rgba(59,130,246,.08);">
    <div style="font-size:11px;font-weight:600;color:#1e40af;text-transform:uppercase;
                letter-spacing:.05em;margin-bottom:6px;">AI 自动处理</div>
    <div style="font-size:28px;font-weight:800;color:#1e40af;letter-spacing:-.03em;">{auto}<span style="font-size:14px;font-weight:500;"> %</span></div>
  </div>
</div>""")

    # ── 漏斗预估：基于当前强推率推算全量 12000 份简历的到面人数 ─────────────────
    if n > 0:
        # 计划招聘人数（可调节）
        _fc, _nc = st.columns([5, 1])
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
        with _fc:
            # AI 自动处理说明
            st.html(f"""
<div style="font-size:12px;color:#6b7280;padding:6px 0;line-height:1.7;">
  <strong style="color:#374151;">AI 自动处理 {auto}%</strong>
  = (强推 {s_n} + 不推进 {rej}) ÷ 本批 {n} 份，无需 HR 介入；
  剩余 <strong style="color:#374151;">待定 {p_n} 份（{100-auto}%）</strong> 需人工复核。
</div>""")

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
<div style="background:white;border:1px solid #e5e7eb;border-radius:14px;
            padding:14px 20px;margin-bottom:16px;
            display:flex;align-items:center;gap:24px;flex-wrap:wrap;
            box-shadow:0 1px 4px rgba(0,0,0,.05);">
  <div style="font-size:12px;font-weight:600;color:#9ca3af;text-transform:uppercase;
              letter-spacing:.05em;white-space:nowrap;">📐 全量推算（基于本批 {n} 份）</div>
  <div style="display:flex;align-items:baseline;gap:6px;">
    <span style="font-size:24px;font-weight:800;color:#111827;">{proj_interviews}</span>
    <span style="font-size:13px;color:#6b7280;">人预计进入面试 / 12,000 份简历</span>
  </div>
  <div style="display:flex;align-items:center;gap:8px;">
    <span style="font-size:13px;color:#6b7280;">到面录取比</span>
    <span style="background:{ratio_bg};border:1px solid {ratio_border};color:{ratio_color};
                 border-radius:999px;padding:3px 12px;font-size:13px;font-weight:700;">
      {ratio_icon} {ratio_str}</span>
    <span style="font-size:12px;color:{ratio_color};">{ratio_note}</span>
  </div>
  <div style="font-size:12px;color:#c4c9d4;margin-left:auto;text-align:right;">
    目标 ≤8:1 · 招聘 {hiring_target} 人<br/>
    <span style="font-size:11px;color:#d1d5db;">基于本批 {n} 份样本估算</span>
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
<div style="background:linear-gradient(135deg,#0f172a 0%,#1e1b4b 100%);
            border-radius:16px;padding:18px 22px;margin-bottom:16px;
            border:1px solid rgba(110,231,183,.25);
            box-shadow:0 4px 20px rgba(17,24,39,.3);">
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
      <div style="font-size:12px;color:#6b7280;margin-top:8px;line-height:1.6;">
        系统在技术层面已移除院校名称，评分完全基于简历中可观察的能力事实。
        双非候选人凭实力排名更高——这是本方案化解「院校歧视 vs 能力优先」冲突的核心证明。
      </div>
    </div>
  </div>
</div>""")

    # ── 候选人结果卡片（按综合得分从高到低排列）─────────────────────────────
    pool_ids = [p["candidate_id"] for p in st.session_state.pool]
    job_c_sorted = sorted(
        [c for c in job_c if c["id"] in results],
        key=lambda c: weighted_score(results[c["id"]]["scores"], dims),
        reverse=True,
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

        # 主卡片 HTML
        st.html(f"""
<div style="background:{cm['bg']};border:1.5px solid {cm['border']};
            border-radius:16px;padding:18px 20px;margin-bottom:0;
            box-shadow:0 2px 10px rgba(0,0,0,.05);">
  <div style="display:flex;align-items:flex-start;justify-content:space-between;gap:16px;">
    <div style="flex:1;min-width:0;">
      <div style="display:flex;align-items:center;gap:7px;flex-wrap:wrap;margin-bottom:8px;">
        <span style="font-size:15px;font-weight:700;color:#111827;letter-spacing:-.01em;">{cand["name"]}</span>
        <span style="background:white;border:1px solid #e5e7eb;color:#4b5563;
                     border-radius:999px;padding:2px 9px;font-size:12px;font-weight:500;">{cand["school"]}</span>
        {_degree_tag(cand.get("degree","本科"))}
        {_tag(cand["tag"])}
      </div>
      <p style="font-size:13px;color:#6b7280;line-height:1.6;margin:0 0 4px;">{cand["summary"]}</p>
      <span style="font-size:11px;color:#c4c9d4;font-style:italic;">{src_label}</span>
      {ov_note_html}
    </div>
    <div style="text-align:right;flex-shrink:0;padding-left:8px;">
      {_badge(final)}
      <div style="font-size:34px;font-weight:900;color:#111827;margin-top:8px;
                  line-height:1;letter-spacing:-.03em;">
        {score}<span style="font-size:14px;font-weight:500;color:#9ca3af;letter-spacing:0;"> 分</span>
      </div>
    </div>
  </div>
  <div style="margin-top:16px;padding-top:14px;border-top:1px solid rgba(0,0,0,.06);">
    {_bars(r["scores"], dims)}
  </div>
</div>
""")

        # ── 操作行 ────────────────────────────────────────────────────────────
        exp_key = f"exp_{cid}"
        is_expanded = st.session_state.get(exp_key, False)
        in_pool = cid in pool_ids
        show_pool_btn = (final == "不推进")

        # 列宽按实际内容分配，确保文字不被截断
        if show_pool_btn:
            btn_cols = st.columns([5, 4, 4, 3])
        else:
            btn_cols = st.columns([5, 4, 7])

        with btn_cols[0]:
            exp_txt = "▲ 收起理由" if is_expanded else "▼ 展开理由"
            if st.button(exp_txt, key=f"btn_exp_{cid}", use_container_width=True):
                st.session_state[exp_key] = not is_expanded
                st.rerun()
        with btn_cols[1]:
            if st.button("📄 原始简历", key=f"btn_res_{cid}", use_container_width=True):
                _resume_dialog(cand)
        if show_pool_btn:
            with btn_cols[2]:
                if not in_pool:
                    if st.button("＋ 跨岗备选", key=f"btn_pool_{cid}", use_container_width=True,
                                 help="加入跨岗位备选库，供其他岗位 HR 参考复用"):
                        add_to_pool_db(cid, preset["label"])
                        _sync_pool()
                        st.rerun()
                else:
                    st.markdown('<div style="padding:7px 0;font-size:12px;color:#d97706;font-weight:500;">✓ 已入跨岗库</div>', unsafe_allow_html=True)

        # ── 展开：理由 + HR 覆盖 ──────────────────────────────────────────────
        if is_expanded:
            reasons_html = "".join(
                f"""<div style="background:#f8faff;border:1px solid #e8eeff;border-radius:8px;
                              padding:10px 14px;margin-bottom:8px;">
  <div style="font-size:11px;font-weight:700;color:#4f46e5;
              letter-spacing:.04em;margin-bottom:6px;">{d["label"]}</div>
  <div style="font-size:12.5px;color:#374151;line-height:1.7;">{r["reasons"].get(d["id"],"")}</div>
</div>"""
                for d in dims
            )
            st.html(f"""
<div style="background:white;border:1px solid #e5e7eb;
            border-radius:14px;padding:16px 18px;margin-top:6px;
            box-shadow:0 1px 4px rgba(0,0,0,.05);">
  <p style="font-size:11px;font-weight:700;color:#9ca3af;text-transform:uppercase;
             letter-spacing:.07em;margin:0 0 4px;">AI 评分理由 · 逐维度</p>
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
                    a_col, b_col, _ = st.columns([2, 2, 6])
                    with a_col:
                        if st.button("✅ 标记已复核", key=f"ap_rev_{ap_id}",
                                     use_container_width=True, type="primary"):
                            update_appeal_status(ap_id, "reviewed")
                            st.toast(f"✅ {cname} 的申诉已标记为「已复核」")
                            st.rerun()
                    with b_col:
                        if st.button("❌ 驳回申诉", key=f"ap_dis_{ap_id}",
                                     use_container_width=True):
                            update_appeal_status(ap_id, "dismissed")
                            st.toast(f"已驳回 {cname} 的申诉")
                            st.rerun()
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


# ─── 候选人视图结论文案（对候选人友好，不用 HR 术语）────────────────────────
_CV_RESULT = {
    "强推进面试": ("✅", "恭喜！您已进入面试流程",     "#166534", "#f0fdf4", "#dcfce7", "#16a34a"),
    "待定":      ("⏳", "初审通过，等待后续安排",        "#92400e", "#fffbeb", "#fef3c7", "#d97706"),
    "不推进":    ("❌", "很遗憾，本次未入选",            "#991b1b", "#fef2f2", "#fee2e2", "#dc2626"),
}

# ─── Page 3：候选人视图 ───────────────────────────────────────────────────────
def render_candidate_view():
    locked_jobs = st.session_state.locked_jobs
    results     = st.session_state.screening_results

    st.html(f"""
{"" if has_api_key() else _preset_mode_banner()}
<div style="margin-bottom:16px;">
  <div style="display:flex;align-items:center;gap:10px;margin-bottom:6px;">
    <h2 style="font-size:22px;font-weight:800;color:#111827;margin:0;">候选人视图</h2>
    {_role_badge("候选人视角")}
  </div>
  <p style="font-size:14px;color:#6b7280;margin:0;">
    候选人登录后看到的页面（模拟）·
    维度结论可见，<span style="color:#ef4444;">分数不对外显示</span>
  </p>
</div>""")

    # ── 候选人 ID 登录模拟 ────────────────────────────────────────────────────
    st.html("""
<div style="background:white;border:1px solid #e5e7eb;border-radius:14px;
            padding:14px 18px;margin-bottom:10px;
            box-shadow:0 1px 4px rgba(0,0,0,.05);">
  <p style="font-size:13px;font-weight:600;color:#374151;margin:0 0 8px;">
    🔐 请输入您的应聘者编号查看结果
  </p>
</div>""")
    _id_input = st.text_input(
        "应聘者编号",
        value=st.session_state.get("cv_selected", "B"),
        placeholder="输入编号，如 A、B … J",
        key="cv_id_input",
        label_visibility="collapsed",
        max_chars=2,
    )
    if _id_input.strip().upper() in CANDIDATES_MAP:
        _new_id = _id_input.strip().upper()
        if _new_id != st.session_state.get("cv_selected"):
            st.session_state.cv_selected = _new_id
            st.session_state[f"ao_{_new_id}"] = False
            st.rerun()

    # ── 演示快速导航（彩点 + ID，不显示姓名）────────────────────────────────
    _dot = {"强推进面试": "🟢", "待定": "🟡", "不推进": "🔴"}
    for grp_key, grp_label in [("pm","产品经理岗"), ("dev","后端开发岗")]:
        st.markdown(f'<p style="font-size:11px;color:#c4c9d4;margin-bottom:3px;">{grp_label}</p>',
                    unsafe_allow_html=True)
        grp_c    = [c for c in CANDIDATES if c["job"] == grp_key]
        btn_cols = st.columns(min(len(grp_c), 5))
        for i, c in enumerate(grp_c):
            with btn_cols[i]:
                cid   = c["id"]
                _ai_r = results[cid]["ai_result"] if cid in results else c["result"]
                _fr, _ = _get_final(cid, _ai_r)
                dot   = _dot.get(_fr, "⚪")
                is_sel = st.session_state.get("cv_selected") == cid
                if st.button(f"{dot} {cid}", key=f"cv_{cid}",
                             type="primary" if is_sel else "secondary",
                             use_container_width=True):
                    st.session_state.cv_selected = cid
                    st.session_state[f"ao_{cid}"] = False
                    st.rerun()
        st.markdown('<div style="height:4px;"></div>', unsafe_allow_html=True)

    sel  = st.session_state.get("cv_selected", "B")
    cand = CANDIDATES_MAP.get(sel)
    if not cand:
        return

    if sel in results:
        r = results[sel]; ai_r = r["ai_result"]
        scores = r["scores"]; reasons = r.get("reasons", cand.get("reasons", {}))
    else:
        ai_r = cand["result"]; scores = cand["scores"]; reasons = cand.get("reasons", {})

    final, is_ov = _get_final(sel, ai_r)
    color        = result_color(final)
    cm           = COLOR_MAP[color]

    # 使用对应岗位已锁定的维度（保证与 HR 视图一致），否则回退预设
    _cand_js   = locked_jobs.get(cand["job"])
    display_dims = _cand_js["dims"]        if _cand_js else JOB_PRESETS[cand["job"]]["dims"]
    display_fp   = _cand_js["fingerprint"] if _cand_js else rule_fingerprint(display_dims)
    display_at   = _cand_js["locked_at"]   if _cand_js else ""
    jl           = JOB_PRESETS[cand["job"]]["label"]

    # ── 演示说明（卡片上方）──────────────────────────────────────────────────
    NOTES = {
        "A": "王芳（复旦 985 · 本科），有完整产品主导经历和数据分析能力，强推进。展示系统对强势候选人同样公平评估。",
        "B": "陈志远（深圳大学 · 双非 · 本科），项目主导经验与复旦王芳相当，同样强推进。核心论点：双非本科凭实力 = 985。",
        "C": "张浩然（北大 985 · 硕士），高学历、工具能力强，但缺乏产品主导经历，评为待定。说明：硕士学历不等于产品能力。",
        "D": "李思琪（浙大 985 · 博士），SCI 论文 3 篇，但零产品经历，不推进。最强反直觉案例：985 博士被系统拒绝。",
        "E": "刘晓晨（职校 · 大专），能力确实不达标，不推进。关键：系统不因职校背景歧视，但也不因此降低评分标准。",
        "F": "吴佳琪（杭电 · 双非 · 本科），开源贡献和实习经验过硬，强推进。双非本科在技术维度完胜多位 985。",
        "G": "赵明远（南大 985 · 硕士），协作能力最突出，但技术岗权重最高的「技术与算法」维度仅 68 分，低于录用基准，不推进。名校硕士+大厂实习 ≠ 技术能力自动达标。",
        "H": "林浩宇（华科 985 · 本科），课程 CRUD 项目为主，实习为测试岗，无独立后端项目，不推进。关键：985 光环无法弥补工程能力空白。",
        "I": "周晓敏（清华 985 · 博士 · ACM 金牌），但方向是控制理论，零后端工程经验，不推进。最大反转：清华博士+竞赛金牌被系统拒绝，因为与岗位不匹配。",
        "J": "郑凯文（无大学学历 · 高中 · 自学），4 年自学后端，GitHub 开源项目 1200+ stars，2 年全职工作经验，强推进。终极论点：系统只看岗位相关能力，无学历者凭实力击败清华博士。",
    }
    if sel in NOTES:
        st.html(f"""
<div style="background:linear-gradient(135deg,#eff6ff,#f0f5ff);
            border:1px solid #bfdbfe;border-radius:14px;
            padding:12px 18px;margin-bottom:12px;
            font-size:13px;color:#1e40af;line-height:1.65;">
  <span style="font-size:14px;">💡</span>
  <strong style="margin-left:4px;">演示说明</strong> —
  {NOTES[sel]}
</div>""")

    # 维度通过/未通过行（阈值与进度条颜色对齐：≥65 蓝/绿=符合，50–64 黄=基本符合，<50 红=有待提升）
    dim_rows = ""
    for d in display_dims:
        s    = scores.get(d["id"], 0)
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
    <div style="background:#f8faff;border:1px solid #dbeafe;border-radius:12px;
                padding:14px 18px;margin-top:18px;">
      <p style="font-size:11px;font-weight:700;color:#3b82f6;text-transform:uppercase;
                 letter-spacing:.06em;margin:0 0 8px;">本次评估适用规则版本</p>
      <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;">
        <span style="font-family:'SF Mono',ui-monospace,monospace;
                     background:white;border:1px solid #bfdbfe;border-radius:8px;
                     padding:5px 14px;font-size:16px;font-weight:800;
                     letter-spacing:.15em;color:#1e40af;">
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
            st.session_state.public_html = build_public_page_html(
                display_dims, display_fp, display_at, jl)
        else:
            st.toast("请先在规则构建页锁定规则", icon="⚠️")
    if st.session_state.public_html:
        with st.expander("📄 规则公示页", expanded=False):
            st.download_button("⬇ 下载公示页 HTML", data=st.session_state.public_html,
                               file_name="rule_public_page.html", mime="text/html")
            st.components.v1.html(st.session_state.public_html, height=440, scrolling=True)

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
<div style="background:#eff6ff;border:1.5px solid #93c5fd;border-radius:14px;
            padding:16px 20px;margin-bottom:12px;">
  <div style="font-size:14px;font-weight:700;color:#1e40af;margin-bottom:6px;">
    📋 申诉复核完成 · 维持原结论
  </div>
  <div style="font-size:13px;color:#1d4ed8;line-height:1.65;">
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

        if revealed:
            st.html("""
<div style="margin-bottom:10px;">
  <span style="font-size:13px;font-weight:700;color:#374151;">📋 申诉维度 · AI 评估依据</span>
  <span style="font-size:11.5px;color:#6b7280;margin-left:8px;">
    分数不对外披露，仅展示 AI 作出判断所依据的具体理由
  </span>
</div>""")
            for dim_id in revealed:
                dim_info = next((d for d in display_dims if d["id"] == dim_id), None)
                if not dim_info:
                    continue
                rv      = reasons.get(dim_id, "暂无详细理由。")
                passed  = scores.get(dim_id, 0) >= 65   # 内部判断，不对外展示数值
                tag_txt = "✅ 符合要求" if passed else "⚠ 有待提升"
                tag_c   = "#166534"   if passed else "#991b1b"
                tag_bg  = "#f0fdf4"   if passed else "#fef2f2"
                st.html(f"""
<div style="background:white;border:1px solid #e5e7eb;border-radius:12px;
            padding:14px 18px;margin-bottom:8px;box-shadow:0 1px 4px rgba(0,0,0,.05);">
  <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:10px;">
    <span style="font-size:13px;font-weight:700;color:#374151;">
      {dim_info["label"]}
      <span style="font-size:11px;color:#9ca3af;font-weight:400;margin-left:6px;">
        权重 {dim_info["weight"]}%</span>
    </span>
    <span style="background:{tag_bg};color:{tag_c};border-radius:999px;
                 padding:3px 10px;font-size:12px;font-weight:600;">{tag_txt}</span>
  </div>
  <p style="font-size:12.5px;color:#4b5563;line-height:1.7;margin:0 0 10px;">
    <strong style="color:#374151;">AI 判断依据：</strong>{rv}</p>
  <div style="background:#f8faff;border-radius:8px;padding:9px 12px;
              font-size:12px;color:#3b82f6;line-height:1.55;">
    💬 如您认为上述依据存在遗漏，请在申诉补充材料中提供具体证明（项目链接、作品集等）
  </div>
</div>""")

            st.html("""
<div style="background:#f9fafb;border:1px solid #e5e7eb;border-radius:10px;
            padding:12px 16px;font-size:12px;color:#6b7280;line-height:1.65;margin-top:4px;">
  ℹ 具体分数不在此阶段披露。如您有新证据，可回复投递确认邮件补充，
  校招团队将在复核时一并参考，并告知最终复核结论。
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
    请指定您认为评估有误的维度，并说明 AI 可能遗漏的具体证据。<br/>
    <strong style="color:#374151;">提交后将显示该维度的详细评分理由</strong>，
    帮助您判断是否继续申诉。
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



# ─── Page 4：简历备选池 ───────────────────────────────────────────────────────
def render_pool_view():
    pool = st.session_state.pool

    st.html(f"""
<div style="margin-bottom:16px;">
  <div style="display:flex;align-items:center;gap:10px;margin-bottom:6px;">
    <h2 style="font-size:22px;font-weight:800;color:#111827;margin:0;">简历备选池</h2>
    {_role_badge("HR 视角")}
  </div>
  <p style="font-size:14px;color:#6b7280;margin:0;">跨岗位备选简历，供其他 HR 参考复用</p>
</div>""")

    if not pool:
        st.markdown("""
<div style="background:white;border:1px solid #e5e7eb;border-radius:12px;
            padding:48px;text-align:center;color:#9ca3af;font-size:14px;">
  📭 备选池暂无简历<br/>
  <span style="font-size:13px;">在筛选工作台对「不推进」候选人点击「➕ 加入备选池」即可加入</span>
</div>""", unsafe_allow_html=True)
        return

    st.markdown(f"""
<div style="background:#fffbeb;border:1px solid #fde68a;border-radius:10px;
            padding:12px 16px;font-size:13px;color:#92400e;line-height:1.6;margin-bottom:16px;">
  💡 这些候选人虽未通过本岗位筛选，但可能匹配其他部门需求。
  各岗位 HR 可在此浏览并联系感兴趣的候选人。
</div>
<div style="display:flex;align-items:center;gap:8px;margin-bottom:12px;">
  <span style="font-size:16px;font-weight:700;color:#111827;">共 {len(pool)} 份备选简历</span>
</div>""", unsafe_allow_html=True)

    for entry in pool:
        cid   = entry["candidate_id"]
        cand  = CANDIDATES_MAP.get(cid)
        if not cand:
            continue
        jl    = entry["from_job_label"]

        st.html(f"""
<div style="background:white;border:1px solid #e5e7eb;border-radius:12px;
            padding:16px;margin-bottom:8px;">
  <div style="display:flex;align-items:flex-start;justify-content:space-between;gap:16px;">
    <div style="flex:1;min-width:0;">
      <div style="display:flex;align-items:center;gap:8px;margin-bottom:6px;">
        <span style="font-size:15px;font-weight:700;color:#111827;">{cand["name"]}</span>
        <span style="background:#f3f4f6;border:1px solid #e5e7eb;color:#374151;
                     border-radius:999px;padding:2px 8px;font-size:12px;">{cand["school"]}</span>
        {_tag(cand["tag"])}
      </div>
      <p style="font-size:13px;color:#6b7280;line-height:1.5;margin:0 0 8px;">{cand["summary"]}</p>
      <div style="font-size:12px;color:#9ca3af;">
        来源岗位：<span style="color:#374151;font-weight:500;">{jl}</span>
        <span style="color:#ef4444;margin-left:6px;">· 未通过</span>
      </div>
    </div>
  </div>
</div>""")

        if st.button("移出备选池", key=f"rm_{cid}"):
            remove_from_pool_db(cid)
            _sync_pool()
            st.rerun()

        st.markdown('<div style="height:4px;"></div>', unsafe_allow_html=True)


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
<div style="background:#eff6ff;border:1px solid #93c5fd;border-radius:12px;
            padding:16px 18px;font-size:13px;color:#1e40af;line-height:1.7;margin-bottom:16px;">
  <strong>🔍 验证原理</strong><br/>
  规则指纹（Hash）由「<strong>维度名称 + 权重</strong>」列表计算得出。
  由于评估维度与 JD 任职要求<strong>一一对应</strong>，只要你手上有相同的 JD 原文，
  用相同的 AI 提取后得到的维度名称应完全一致。<br/>
  将权重调整为与 HR 公示的权重相同后，生成的指纹若与邮件中的一致，
  即可证明规则<strong>自发布后未被修改</strong>。
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
            with st.expander("查看岗位 JD（参考原文）"):
                st.code(_off_preset["jd"], language=None)
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
_appeal_tab_label = f"📊 筛选工作台{'  🔴' if _pending_appeals else ''}"

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "🏗 规则构建",
    _appeal_tab_label,
    "👤 候选人视图",
    "🔍 规则验证",
    "📦 简历备选池",
])

with tab1:
    render_rule_builder()
with tab2:
    render_screening()
with tab3:
    render_candidate_view()
with tab4:
    render_verification()
with tab5:
    render_pool_view()

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
         background:linear-gradient(135deg,#2563eb 0%,#1e1b4b 100%);
         color:white;border:none;cursor:pointer;
         font-size:24px;font-weight:700;line-height:1;
         box-shadow:0 4px 20px rgba(37,99,235,.50),0 1px 4px rgba(0,0,0,.18);
         display:flex;align-items:center;justify-content:center;
         transition:transform .18s;
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
