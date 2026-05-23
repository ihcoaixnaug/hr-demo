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
    save_hr_override,
    add_to_pool_db, remove_from_pool_db, get_pool_db,
    save_appeal,
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
</style>
""", unsafe_allow_html=True)


# ─── Session State 初始化 ─────────────────────────────────────────────────────
def _init():
    defs = {
        "selected_job":      None,
        "rule_locked":       False,
        "locked_dims":       None,
        "fingerprint":       "",
        "locked_at":         "",
        "rule_id":           None,
        "editing_dims":      None,
        "screening_results": {},
        "overrides":         {},
        "pool":              [],
        "appeal_submitted":  set(),
        "public_html":       "",
        "selected_cands":    [],
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
  <span style="font-size:12px;color:#6b7280;white-space:nowrap;overflow:hidden;
               text-overflow:ellipsis;">
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


# ─── Header ───────────────────────────────────────────────────────────────────
def render_header():
    badges_html = ""
    if st.session_state.rule_locked:
        jk = st.session_state.selected_job
        jl = JOB_PRESETS[jk]["label"] if jk else "自定义"
        badges_html += (
            f'<span style="background:#111827;color:#fff;border-radius:999px;'
            f'padding:3px 10px;font-size:12px;margin-left:8px;">'
            f'🔒 {jl} · 规则已锁定</span>'
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
    locked = st.session_state.rule_locked

    # ══ 已锁定态 ══════════════════════════════════════════════════════════════
    if locked:
        dims      = st.session_state.locked_dims
        fp        = st.session_state.fingerprint
        at        = st.session_state.locked_at
        jk        = st.session_state.selected_job
        jl        = JOB_PRESETS[jk]["label"] if jk else "自定义岗位"

        # 当前岗位小条
        st.markdown(f"""
<div style="background:white;border:1px solid #e5e7eb;border-radius:12px;
            padding:12px 16px;display:flex;align-items:center;gap:10px;margin-bottom:12px;">
  <div style="width:8px;height:8px;border-radius:999px;background:#3b82f6;"></div>
  <span style="font-size:14px;font-weight:600;color:#111827;">{jl}</span>
  <span style="font-size:13px;color:#9ca3af;">当前筛选岗位</span>
</div>
""", unsafe_allow_html=True)

        # 维度卡片
        with st.container(border=True):
            col_t, col_total = st.columns([4, 1])
            with col_t:
                st.markdown('<span style="font-size:14px;font-weight:600;color:#374151;">评估维度与权重</span>', unsafe_allow_html=True)
            with col_total:
                st.markdown('<span style="background:#dcfce7;color:#166534;border-radius:999px;padding:2px 10px;font-size:12px;font-weight:600;">总计 100%</span>', unsafe_allow_html=True)
            for d in dims:
                c1, c2 = st.columns([5, 1])
                with c1:
                    st.markdown(f'<span style="font-size:14px;color:#374151;">{d["label"]}</span>', unsafe_allow_html=True)
                    st.progress(d["weight"] / 100)
                with c2:
                    st.markdown(f'<div style="font-family:monospace;font-size:14px;color:#6b7280;text-align:right;margin-top:18px;">{d["weight"]}%</div>', unsafe_allow_html=True)

        # 深色锁定卡
        dim_chips = "".join(
            f'<span style="background:rgba(255,255,255,.10);border:1px solid rgba(255,255,255,.15);'
            f'border-radius:8px;padding:3px 10px;font-size:12px;color:#e5e7eb;'
            f'font-weight:500;margin-right:6px;margin-bottom:6px;display:inline-block;">'
            f'{d["label"]} <span style="color:#6ee7b7;font-weight:700;">{d["weight"]}%</span></span>'
            for d in dims
        )
        st.markdown(f"""
<div style="background:linear-gradient(160deg,#111827 0%,#1e1b4b 100%);
            border-radius:18px;padding:22px 24px;color:white;margin-top:10px;
            box-shadow:0 4px 20px rgba(17,24,39,.35);">
  <div style="display:flex;align-items:center;gap:10px;margin-bottom:4px;">
    <span style="font-size:16px;">🔒</span>
    <span style="font-size:15px;font-weight:700;letter-spacing:-.01em;">规则已锁定 · 不可修改</span>
  </div>
  <p style="font-size:12px;color:#6b7280;margin:0 0 18px;">锁定时间：{at}</p>

  <div style="background:rgba(110,231,183,.08);border:1px solid rgba(110,231,183,.2);
              border-radius:12px;padding:16px 18px;margin-bottom:16px;">
    <p style="font-size:11px;color:#6b7280;margin:0 0 8px;text-transform:uppercase;
               letter-spacing:.06em;font-weight:600;">RULE HASH · 规则指纹</p>
    <span style="font-family:'SF Mono',ui-monospace,monospace;font-size:26px;
                 color:#6ee7b7;font-weight:900;letter-spacing:.2em;">{fp}</span>
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

        st.markdown("<br/>", unsafe_allow_html=True)
        c_reset, c_hint = st.columns(2)
        with c_reset:
            if st.button("🔄 重新设置规则", key="reset_rule"):
                for k in ("rule_locked","locked_dims","fingerprint","locked_at",
                          "selected_job","editing_dims","screening_results",
                          "overrides","rule_id","public_html","selected_cands"):
                    st.session_state[k] = {
                        "rule_locked": False, "locked_dims": None,
                        "fingerprint": "", "locked_at": "", "selected_job": None,
                        "editing_dims": None, "screening_results": {},
                        "overrides": {}, "rule_id": None, "public_html": "",
                        "selected_cands": [],
                    }[k]
                st.rerun()
        with c_hint:
            if st.button("📊 前往筛选工作台 →", key="goto_screen", type="primary"):
                st.session_state.goto_tab = 1   # 筛选工作台 = index 1
                st.rerun()

        # 公示页
        st.markdown("---")
        if st.button("📄 查看规则公示页", key="open_pub_locked"):
            st.session_state.public_html = build_public_page_html(dims, fp, at, jl)
        if st.session_state.public_html:
            with st.expander("规则公示页预览", expanded=True):
                st.download_button(
                    "⬇ 下载公示页 HTML（可发送给候选人或挂载官网）",
                    data=st.session_state.public_html,
                    file_name="rule_public_page.html", mime="text/html",
                )
                st.components.v1.html(st.session_state.public_html, height=460, scrolling=True)
        return

    # ══ 未锁定态 ══════════════════════════════════════════════════════════════
    st.html("""
<div style="margin-bottom:20px;">
  <h2 style="font-size:22px;font-weight:800;color:#111827;margin:0 0 4px;">规则构建</h2>
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
        if st.button(
            f"🎯  {pm['label']}",
            key="sel_pm",
            use_container_width=True,
            type="primary" if pm_sel else "secondary",
        ):
            _load_job("pm")
        st.caption(pm["desc"])
    with c2:
        dev = JOB_PRESETS["dev"]
        dev_sel = st.session_state.selected_job == "dev"
        if st.button(
            f"⚙️  {dev['label']}",
            key="sel_dev",
            use_container_width=True,
            type="primary" if dev_sel else "secondary",
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
        st.session_state.rule_locked = True
        st.session_state.locked_dims = new_dims
        st.session_state.fingerprint = fp
        st.session_state.locked_at   = at
        st.session_state.rule_id     = rid
        st.session_state.public_html = ""
        st.rerun()


# ─── Page 2：筛选工作台 ───────────────────────────────────────────────────────
def render_screening():
    dims    = st.session_state.locked_dims
    jk      = st.session_state.selected_job
    rule_id = st.session_state.rule_id
    results = st.session_state.screening_results

    if not st.session_state.rule_locked or not dims or not jk:
        st.html("""
<div style="background:white;border:1px solid #e5e7eb;border-radius:16px;
            padding:56px 40px;text-align:center;
            box-shadow:0 1px 4px rgba(0,0,0,.06);">
  <div style="font-size:32px;margin-bottom:12px;">🔒</div>
  <div style="font-size:15px;font-weight:600;color:#374151;margin-bottom:6px;">规则尚未锁定</div>
  <div style="font-size:13px;color:#9ca3af;">请先在「🏗 规则构建」页完成规则锁定，再来筛选</div>
</div>""")
        return

    preset  = JOB_PRESETS[jk]
    job_c   = [c for c in CANDIDATES if c["job"] == jk]

    st.html(f"""
<div style="margin-bottom:16px;">
  <h2 style="font-size:22px;font-weight:800;color:#111827;margin:0 0 4px;">筛选工作台</h2>
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
        return

    # ── 汇总栏 ───────────────────────────────────────────────────────────────
    all_finals = [_get_final(cid, r["ai_result"])[0] for cid, r in results.items()]
    n = len(all_finals)
    s_n = sum(1 for r in all_finals if r == "强推进面试")
    p_n = sum(1 for r in all_finals if r == "待定")
    rej = sum(1 for r in all_finals if r == "不推进")
    auto = round(((s_n + rej) / n) * 100) if n else 0

    st.html(f"""
<div style="display:grid;grid-template-columns:repeat(5,1fr);gap:10px;margin-bottom:20px;">
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

    # ── 候选人结果卡片 ────────────────────────────────────────────────────────
    pool_ids = [p["candidate_id"] for p in st.session_state.pool]

    for cand in job_c:
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
        res_key = f"res_{cid}"
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
                st.session_state[res_key] = not st.session_state.get(res_key, False)
                st.rerun()
        if show_pool_btn:
            with btn_cols[2]:
                if not in_pool:
                    if st.button("＋ 备选池", key=f"btn_pool_{cid}", use_container_width=True):
                        add_to_pool_db(cid, preset["label"])
                        _sync_pool()
                        st.rerun()
                else:
                    st.markdown('<div style="padding:7px 0;font-size:12px;color:#d97706;font-weight:500;">✓ 已在备选池</div>', unsafe_allow_html=True)

        # ── 展开：理由 + HR 覆盖 ──────────────────────────────────────────────
        if is_expanded:
            reasons_html = "".join(
                f"""<div style="display:flex;gap:14px;padding:10px 0;
                              border-bottom:1px solid #f3f4f6;align-items:flex-start;">
  <div style="flex-shrink:0;width:68px;padding-top:1px;">
    <span style="font-size:11px;font-weight:700;color:#374151;
                 background:#f8faff;border:1px solid #e0e7ff;border-radius:6px;
                 padding:2px 7px;white-space:nowrap;">{d["label"]}</span>
  </div>
  <span style="font-size:12.5px;color:#4b5563;line-height:1.65;">
    {r["reasons"].get(d["id"],"")}</span>
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

        # 简历弹窗（Expander 模拟）
        if st.session_state.get(res_key):
            resume = cand["resume"]
            with st.expander(f"📄 {cand['name']} 的原始简历", expanded=True):
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
                aw = resume.get("awards","")
                if aw and aw != "无":
                    st.markdown(f"🏆 **奖项** {aw}")

        # 卡片间隔
        st.markdown('<div style="height:16px;"></div>', unsafe_allow_html=True)


# ─── Page 3：候选人视图 ───────────────────────────────────────────────────────
def render_candidate_view():
    dims    = st.session_state.locked_dims
    fp      = st.session_state.fingerprint
    at      = st.session_state.locked_at
    results = st.session_state.screening_results

    st.html("""
<div style="margin-bottom:16px;">
  <h2 style="font-size:22px;font-weight:800;color:#111827;margin:0 0 4px;">候选人视图</h2>
  <p style="font-size:14px;color:#6b7280;margin:0;">
    候选人登录后看到的页面（模拟）·
    维度结论可见，<span style="color:#ef4444;">分数不对外显示</span>
  </p>
</div>""")

    # 候选人选择器
    for grp_key, grp_label in [("pm","产品经理岗"), ("dev","后端开发岗")]:
        st.markdown(f'<p style="font-size:12px;color:#9ca3af;margin-bottom:4px;">{grp_label}</p>', unsafe_allow_html=True)
        grp_c = [c for c in CANDIDATES if c["job"] == grp_key]
        btn_cols = st.columns(len(grp_c))
        for i, c in enumerate(grp_c):
            with btn_cols[i]:
                if st.button(c["name"], key=f"cv_{c['id']}"):
                    st.session_state.cv_selected = c["id"]
                    st.session_state[f"ao_{c['id']}"] = False
                    st.rerun()
        st.markdown('<div style="height:6px;"></div>', unsafe_allow_html=True)

    sel   = st.session_state.get("cv_selected", "B")
    cand  = CANDIDATES_MAP.get(sel)
    if not cand:
        return

    if sel in results:
        r = results[sel]; ai_r = r["ai_result"]
        scores = r["scores"]; reasons = r.get("reasons", cand.get("reasons", {}))
    else:
        ai_r = cand["result"]; scores = cand["scores"]; reasons = cand.get("reasons", {})

    final, is_ov    = _get_final(sel, ai_r)
    color           = result_color(final)
    cm              = COLOR_MAP[color]
    display_dims    = JOB_PRESETS[cand["job"]]["dims"]
    jl              = JOB_PRESETS[cand["job"]]["label"]
    display_fp      = fp if fp else rule_fingerprint(display_dims)

    # 维度通过/未通过行
    dim_rows = ""
    for d in display_dims:
        s    = scores.get(d["id"], 0)
        pass_= s >= 65
        bg_  = "#f0fdf4" if pass_ else "#fef2f2"
        tc_  = "#166534" if pass_ else "#991b1b"
        tag_ = "✅ 符合要求" if pass_ else "⚠ 有待提升"
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

    # 结果大图标 + 文字配置
    _result_cfg = {
        "强推进面试": ("✅", "#166534", "#f0fdf4", "#dcfce7", "#16a34a"),
        "待定":      ("⏳", "#92400e", "#fffbeb", "#fef3c7", "#d97706"),
        "不推进":    ("❌", "#991b1b", "#fef2f2", "#fee2e2", "#dc2626"),
    }
    r_icon, r_text_c, r_bg, r_border_c, r_accent = _result_cfg.get(
        final, ("❓", "#374151", "#f9fafb", "#e5e7eb", "#6b7280")
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
    <div style="font-size:36px;font-weight:900;color:{r_text_c};
                letter-spacing:-.01em;line-height:1.1;margin-bottom:10px;">
      {r_icon}&nbsp;{final}
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
        if dims and fp:
            st.session_state.public_html = build_public_page_html(dims, fp, at, jl)
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
        # ── 已提交：受理确认 + 有条件查分 ──────────────────────────────────
        revealed = st.session_state.get(f"ap_revealed_{sel}", [])
        st.html("""
<div style="background:#f0fdf4;border:1.5px solid #86efac;border-radius:14px;
            padding:16px 20px;margin-bottom:12px;
            box-shadow:0 2px 8px rgba(16,185,129,.08);">
  <div style="font-size:14px;font-weight:700;color:#166534;margin-bottom:6px;">
    ✅ 申诉已受理
  </div>
  <div style="font-size:13px;color:#15803d;line-height:1.65;">
    校招运营团队将在 <strong>5 个工作日</strong>内处理您的申诉。<br/>
    复核基准为您提交时所对应的 <strong>锁定规则版本（指纹不变）</strong>，
    如需补充材料，将通过投递邮箱联系您。
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

        ap_evidence: dict[str, str] = {}
        for label in selected_labels:
            dim_id = dim_label_to_id[label]
            ev = st.text_area(
                f"关于「{label}」的补充说明",
                key=f"ap_ev_{sel}_{dim_id}",
                placeholder=(
                    "请描述您认为 AI 评估中遗漏的具体证据，"
                    "例如：简历中未充分体现的项目经历、技能应用场景、量化成果等。"
                    "模糊的「我觉得不公平」将无法作为复核依据。"
                ),
                height=88,
            )
            ap_evidence[dim_id] = ev

        can_submit = (
            len(selected_labels) > 0
            and all(v.strip() for v in ap_evidence.values())
        )

        ca, sb = st.columns(2)
        with ca:
            if st.button("取消", key=f"ap_cancel_{sel}", use_container_width=True):
                st.session_state[ao_key] = False
                st.rerun()
        with sb:
            if st.button("提交申诉", type="primary", disabled=not can_submit,
                         key=f"ap_sub_{sel}", use_container_width=True):
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

    # 演示说明
    NOTES = {
        "A": "王芳（复旦 985 · 本科），有完整产品主导经历和数据分析能力，强推进。展示系统对强势候选人同样公平评估。",
        "B": "陈志远（深圳大学 · 双非 · 本科），项目主导经验与复旦王芳相当，同样强推进。核心论点：双非本科凭实力 = 985。",
        "C": "张浩然（北大 985 · 硕士），高学历、工具能力强，但缺乏产品主导经历，评为待定。说明：硕士学历不等于产品能力。",
        "D": "李思琪（浙大 985 · 博士），SCI 论文 3 篇，但零产品经历，不推进。最强反直觉案例：985 博士被系统拒绝。",
        "E": "刘晓晨（职校 · 大专），能力确实不达标，不推进。关键：系统不因职校背景歧视，但也不因此降低评分标准。",
        "F": "吴佳琪（杭电 · 双非 · 本科），开源贡献和实习经验过硬，强推进。双非本科在技术维度完胜多位 985。",
        "G": "赵明远（南大 985 · 硕士），跨职能协作能力最强，但字节实习仅停留在功能接入层，编码深度不足，评为待定。说明：名校硕士+大厂实习 ≠ 技术能力自动达标。",
        "H": "林浩宇（华科 985 · 本科），课程 CRUD 项目为主，实习为测试岗，无独立后端项目，不推进。关键：985 光环无法弥补工程能力空白。",
        "I": "周晓敏（清华 985 · 博士 · ACM 金牌），但方向是控制理论，零后端工程经验，不推进。\n最大反转：清华博士+竞赛金牌被系统拒绝，因为与岗位不匹配。",
        "J": "郑凯文（无大学学历 · 高中 · 自学），4 年自学后端，GitHub 开源项目 1200+ stars，2 年全职工作经验，强推进。\n终极论点：系统只看岗位相关能力，无学历者凭实力击败清华博士。",
    }
    if sel in NOTES:
        st.markdown('<div style="height:14px;"></div>', unsafe_allow_html=True)
        st.html(f"""
<div style="background:linear-gradient(135deg,#eff6ff,#f0f5ff);
            border:1px solid #bfdbfe;border-radius:14px;
            padding:14px 18px;font-size:13px;color:#1e40af;line-height:1.65;">
  <span style="font-size:14px;">💡</span>
  <strong style="margin-left:4px;">演示说明</strong> —
  {NOTES[sel]}
</div>""")


# ─── Page 4：简历备选池 ───────────────────────────────────────────────────────
def render_pool_view():
    pool = st.session_state.pool

    st.html("""
<div style="margin-bottom:16px;">
  <h2 style="font-size:22px;font-weight:800;color:#111827;margin:0 0 4px;">简历备选池</h2>
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
    st.html("""
<div style="margin-bottom:16px;">
  <h2 style="font-size:22px;font-weight:800;color:#111827;margin:0 0 4px;">候选人规则验证</h2>
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

    # Step 1：输入 JD
    st.html('<p style="font-size:14px;font-weight:600;color:#374151;margin:0 0 6px;">① 粘贴岗位 JD（需包含「任职要求」部分）</p>')
    jd_input = st.text_area(
        "JD 文本",
        key="verify_jd",
        height=200,
        placeholder="将招聘 JD 全文粘贴至此，系统将自动识别「任职要求」部分……",
        label_visibility="collapsed",
    )

    if not has_api_key():
        st.html("""
<div style="background:#fef3c7;border:1px solid #fde68a;border-radius:8px;
            padding:10px 14px;font-size:12px;color:#92400e;margin-top:8px;">
  ⚠ 当前未配置 API Key，无法调用 AI 提取。请配置后再使用此功能。
</div>""")
        return

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

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "🏗 规则构建",
    "📊 筛选工作台",
    "👤 候选人视图",
    "📦 简历备选池",
    "🔍 规则验证",
])

with tab1:
    render_rule_builder()
with tab2:
    render_screening()
with tab3:
    render_candidate_view()
with tab4:
    render_pool_view()
with tab5:
    render_verification()

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
