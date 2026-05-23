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
from llm import screen_candidate_with_llm, has_api_key

# ─── 页面基础配置 ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="智筛 AI · 可信简历筛选系统",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ─── 全局 CSS（对齐 demo.html 的 Tailwind 风格） ──────────────────────────────
st.markdown("""
<style>
/* ── 基础 ── */
html,body,[class*="css"]{
  font-family:-apple-system,"PingFang SC",BlinkMacSystemFont,"Segoe UI",sans-serif!important;
}
.stApp{background:#f9fafb!important;}
.stMainBlockContainer,.block-container{
  max-width:860px!important;
  margin:0 auto!important;
  padding:0 20px 60px!important;
}

/* ── 隐藏 Streamlit 默认 chrome ── */
#MainMenu,footer,.stDeployButton{display:none!important;}
[data-testid="stToolbar"]{display:none!important;}
header[data-testid="stHeader"]{background:white!important;border-bottom:1px solid #e5e7eb!important;}

/* ── Tabs：对齐原版导航栏 ── */
.stTabs [data-baseweb="tab-list"]{
  background:white!important;
  border-bottom:1px solid #e5e7eb!important;
  padding:0!important;gap:0!important;
}
.stTabs [data-baseweb="tab"]{
  background:transparent!important;
  color:#6b7280!important;
  font-size:13px!important;font-weight:500!important;
  padding:10px 16px!important;
  border-radius:0!important;margin:0!important;
}
.stTabs [aria-selected="true"]{color:#2563eb!important;}
.stTabs [data-baseweb="tab-highlight"]{
  background:#2563eb!important;height:2px!important;
}
.stTabs [data-baseweb="tab-border"]{display:none!important;}
.stTabs [data-baseweb="tab-panel"]{padding:28px 0 0!important;}

/* ── 主按钮（深色）── */
.stButton>button[kind="primary"]{
  background:#111827!important;color:white!important;
  border:none!important;border-radius:10px!important;
  font-size:14px!important;font-weight:600!important;
  padding:10px 22px!important;
}
.stButton>button[kind="primary"]:hover:not(:disabled){background:#374151!important;}

/* ── 次按钮 ── */
.stButton>button{
  border-radius:8px!important;font-size:13px!important;
  font-weight:500!important;padding:6px 12px!important;
  border:1px solid #e5e7eb!important;
  color:#374151!important;background:white!important;
  box-shadow:none!important;
}
.stButton>button:hover:not(:disabled){
  border-color:#9ca3af!important;background:#f9fafb!important;
}
.stButton>button:disabled{opacity:.35!important;}

/* ── Slider ── */
[data-testid="stSlider"] [role="slider"]{background:#3b82f6!important;}
[data-testid="stSlider"] [data-testid="stSliderThumbValue"]{
  background:#111827!important;color:white!important;
  font-family:monospace!important;font-size:11px!important;
  border-radius:4px!important;
}
/* track 高亮 */
[data-testid="stSlider"] > div > div > div > div{
  background:#3b82f6!important;
}

/* ── Input / Textarea ── */
.stTextInput input,.stTextArea textarea{
  border-radius:8px!important;border:1px solid #e5e7eb!important;
  font-size:13px!important;color:#374151!important;
}
.stTextInput input:focus,.stTextArea textarea:focus{
  border-color:#93c5fd!important;
  box-shadow:0 0 0 3px rgba(59,130,246,.1)!important;
  outline:none!important;
}
/* hide labels we don't need */
.stTextArea label,.stTextInput label{
  font-size:12px!important;color:#6b7280!important;
}

/* ── Selectbox ── */
.stSelectbox>div>div{
  border-radius:8px!important;border:1px solid #e5e7eb!important;
  font-size:13px!important;
}
.stSelectbox label{font-size:12px!important;color:#6b7280!important;}

/* ── Checkbox ── */
.stCheckbox label{font-size:14px!important;color:#374151!important;}

/* ── Metrics ── */
[data-testid="metric-container"]{
  background:white!important;border:1px solid #e5e7eb!important;
  border-radius:12px!important;padding:14px 18px!important;
}
[data-testid="stMetricValue"]{font-size:22px!important;font-weight:800!important;color:#111827!important;}
[data-testid="stMetricLabel"]{font-size:12px!important;color:#6b7280!important;font-weight:500!important;}

/* ── Alerts ── */
.stAlert{border-radius:10px!important;font-size:13px!important;}

/* ── Expander ── */
.stExpander{border:1px solid #e5e7eb!important;border-radius:10px!important;background:white!important;}
.stExpander summary{font-size:13px!important;font-weight:600!important;color:#374151!important;}

/* ── Container border ── */
div[data-testid="stVerticalBlockBorderWrapper"]{border-radius:12px!important;}

/* ── 压缩 Streamlit 默认间距 ── */
.element-container{margin-bottom:4px!important;}
div[data-testid="stVerticalBlock"]>div{gap:4px!important;}
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
}

def _tag(tag: str) -> str:
    bg, color = TAG_COLOR.get(tag, ("bg:#f3f4f6","color:#4b5563"))
    return (f'<span style="{bg};{color};border-radius:999px;'
            f'padding:2px 8px;font-size:12px;font-weight:600;">{tag}</span>')

def _badge(result: str) -> str:
    c = COLOR_MAP[result_color(result)]
    return (f'<span style="background:{c["badge_bg"]};color:{c["badge_text"]};'
            f'border-radius:999px;padding:3px 12px;font-size:12px;font-weight:700;">'
            f'{result}</span>')

def _bars(scores: dict, dims: list) -> str:
    rows = []
    for d in dims:
        v = scores.get(d["id"], 0)
        c = "#10b981" if v >= 80 else "#3b82f6" if v >= 65 else "#ef4444"
        rows.append(f"""
<div style="display:grid;grid-template-columns:7.5rem 1fr;gap:8px;
            align-items:center;margin-bottom:6px;">
  <span style="font-size:12px;color:#6b7280;white-space:nowrap;">
    {d["label"]}（{d["weight"]}%）
  </span>
  <div style="display:flex;align-items:center;gap:8px;">
    <div style="flex:1;background:#f3f4f6;border-radius:999px;height:6px;overflow:hidden;">
      <div style="width:{v}%;height:6px;background:{c};border-radius:999px;"></div>
    </div>
    <span style="font-family:monospace;font-size:12px;color:#9ca3af;
                 width:22px;text-align:right;">{v}</span>
  </div>
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

    st.markdown(f"""
<div style="background:white;border-bottom:1px solid #e5e7eb;
            padding:12px 0 12px;margin-bottom:0;">
  <div style="max-width:860px;margin:0 auto;padding:0 20px;
              display:flex;align-items:center;justify-content:space-between;">
    <div style="display:flex;align-items:center;gap:10px;">
      <div style="width:30px;height:30px;background:#111827;border-radius:8px;
                  display:flex;align-items:center;justify-content:center;">
        <span style="color:white;font-weight:800;font-size:13px;">智</span>
      </div>
      <span style="font-weight:800;font-size:17px;color:#111827;">智筛 AI</span>
      <span style="font-size:13px;color:#9ca3af;">· 可信简历筛选系统</span>
    </div>
    <div style="display:flex;align-items:center;">{badges_html}</div>
  </div>
</div>
""", unsafe_allow_html=True)


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
        dim_rows = "".join(
            f'<span style="background:rgba(255,255,255,.08);border-radius:6px;'
            f'padding:2px 8px;font-size:12px;color:#d1d5db;margin-right:6px;">'
            f'{d["label"]} {d["weight"]}%</span>'
            for d in dims
        )
        st.markdown(f"""
<div style="background:#111827;border-radius:16px;padding:20px;color:white;margin-top:8px;">
  <div style="display:flex;align-items:center;gap:8px;font-size:14px;font-weight:600;margin-bottom:6px;">
    <span>🔒</span> 规则已锁定 · 不可修改
  </div>
  <p style="font-size:12px;color:#9ca3af;margin:0 0 14px;">锁定时间：{at}</p>

  <div style="background:rgba(255,255,255,.07);border-radius:10px;padding:14px 16px;margin-bottom:14px;">
    <p style="font-size:11px;color:#9ca3af;margin:0 0 6px;text-transform:uppercase;letter-spacing:.05em;">
      规则指纹（Rule Hash）
    </p>
    <div style="display:flex;align-items:center;justify-content:space-between;">
      <span style="font-family:monospace;font-size:20px;color:#6ee7b7;
                   font-weight:800;letter-spacing:.15em;">{fp}</span>
    </div>
    <p style="font-size:11px;color:#6b7280;margin:6px 0 0;">
      规则内容改变时指纹随之改变，候选人可独立验证
    </p>
  </div>

  <div style="display:flex;align-items:center;gap:6px;font-size:12px;color:#93c5fd;margin-bottom:6px;">
    <span>🔗</span> 规则已同步公示页，所有投递候选人将收到规则快照邮件，含本指纹
  </div>
  <div style="margin-top:10px;">{dim_rows}</div>
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
                # Switch tab — 通过 query param 无法直接切，提示用户
                st.success("请点击上方「📊 筛选工作台」标签页")

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
    st.markdown('<h2 style="font-size:20px;font-weight:700;color:#111827;margin-bottom:4px;">规则构建</h2>', unsafe_allow_html=True)
    st.markdown('<p style="font-size:14px;color:#6b7280;margin-bottom:20px;">选择招募岗位，AI 自动加载评估维度，确认后锁定发布</p>', unsafe_allow_html=True)

    # 岗位卡片
    st.markdown('<p style="font-size:14px;font-weight:500;color:#374151;margin-bottom:8px;">选择招募岗位</p>', unsafe_allow_html=True)

    def _job_card(key, accent):
        p = JOB_PRESETS[key]
        sel = st.session_state.selected_job == key
        border = f"2px solid {accent}" if sel else "2px solid #e5e7eb"
        bg     = "#eff6ff" if (sel and key=="pm") else ("#f5f3ff" if (sel and key=="dev") else "white")
        name_c = accent if sel else "#111827"
        return f"""
<div style="border:{border};background:{bg};border-radius:12px;
            padding:14px 16px;cursor:pointer;transition:all .15s;">
  <div style="font-size:14px;font-weight:700;color:{name_c};">{p["label"]}</div>
  <div style="font-size:12px;color:#9ca3af;margin-top:2px;">{p["desc"]}</div>
</div>"""

    c1, c2 = st.columns(2)
    with c1:
        st.markdown(_job_card("pm","#3b82f6"), unsafe_allow_html=True)
        if st.button("选择产品经理岗", key="sel_pm", use_container_width=True):
            p = JOB_PRESETS["pm"]
            st.session_state.selected_job  = "pm"
            st.session_state.editing_dims  = copy.deepcopy(p["dims"])
            for d in p["dims"]:
                st.session_state[f"w_{d['id']}"] = d["weight"]
            st.rerun()
    with c2:
        st.markdown(_job_card("dev","#8b5cf6"), unsafe_allow_html=True)
        if st.button("选择后端开发岗", key="sel_dev", use_container_width=True):
            p = JOB_PRESETS["dev"]
            st.session_state.selected_job  = "dev"
            st.session_state.editing_dims  = copy.deepcopy(p["dims"])
            for d in p["dims"]:
                st.session_state[f"w_{d['id']}"] = d["weight"]
            st.rerun()

    jk = st.session_state.selected_job
    if not jk:
        st.markdown('<p style="font-size:13px;color:#9ca3af;margin-top:10px;">👆 请先选择岗位，系统自动加载对应的评估维度</p>', unsafe_allow_html=True)
        return

    preset    = JOB_PRESETS[jk]
    edit_dims = st.session_state.editing_dims or copy.deepcopy(preset["dims"])
    st.session_state.editing_dims = edit_dims

    st.markdown(f"""
<div style="display:flex;align-items:center;gap:6px;color:#059669;
            font-size:13px;margin:14px 0 6px;">
  <span>✅</span>
  <span>已加载「{preset["label"]}」评估维度</span>
</div>""", unsafe_allow_html=True)

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
        st.markdown("""
<div style="background:white;border:1px solid #e5e7eb;border-radius:12px;
            padding:40px;text-align:center;color:#6b7280;font-size:14px;">
  🔒 请先在「🏗 规则构建」页完成规则锁定，再来筛选
</div>""", unsafe_allow_html=True)
        return

    preset  = JOB_PRESETS[jk]
    job_c   = [c for c in CANDIDATES if c["job"] == jk]

    st.markdown(f'<h2 style="font-size:20px;font-weight:700;color:#111827;margin-bottom:4px;">筛选工作台</h2>', unsafe_allow_html=True)
    st.markdown(f'<p style="font-size:14px;color:#6b7280;margin-bottom:16px;">AI 按锁定规则逐条评分并给出可追溯理由 · {preset["label"]}</p>', unsafe_allow_html=True)

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
                    f"{c['name']} · {c['school']} · {c['tag']}",
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

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("本次筛选", f"{n} 份")
    c2.metric("强推进", s_n)
    c3.metric("待定", p_n)
    c4.metric("不推进", rej)
    c5.metric("AI 自动处理率", f"{auto}%")

    st.markdown("<br/>", unsafe_allow_html=True)

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

        # 主卡片 HTML（用 st.html 避免 markdown 解析器干扰 flex 布局）
        st.html(f"""
<div style="background:{cm['bg']};border:1px solid {cm['border']};
            border-radius:12px;padding:16px;margin-bottom:0;">
  <div style="display:flex;align-items:flex-start;justify-content:space-between;gap:16px;">
    <div style="flex:1;min-width:0;">
      <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:6px;">
        <span style="font-size:15px;font-weight:700;color:#111827;">{cand["name"]}</span>
        <span style="background:white;border:1px solid #e5e7eb;color:#374151;
                     border-radius:999px;padding:2px 8px;font-size:12px;">{cand["school"]}</span>
        {_tag(cand["tag"])}
        <span style="font-size:11px;color:#9ca3af;">{src_label}</span>
      </div>
      <p style="font-size:13px;color:#6b7280;line-height:1.55;margin:0;">{cand["summary"]}</p>
      {ov_note_html}
    </div>
    <div style="text-align:right;flex-shrink:0;">
      {_badge(final)}
      <div style="font-size:30px;font-weight:900;color:#111827;margin-top:6px;line-height:1;">
        {score}<span style="font-size:14px;font-weight:400;color:#9ca3af;"> 分</span>
      </div>
    </div>
  </div>
  <div style="margin-top:14px;">{_bars(r["scores"], dims)}</div>
</div>
""")

        # ── 操作行：内联小按钮，贴近原版 HTML 风格 ──────────────────────────────
        exp_key = f"exp_{cid}"
        res_key = f"res_{cid}"
        is_expanded = st.session_state.get(exp_key, False)
        pool_label = ""
        if final == "不推进":
            pool_label = "✓ 已在备选池" if cid in pool_ids else "＋ 加入备选池"

        btn_row_cols = st.columns([1, 1, 1, 4])
        with btn_row_cols[0]:
            exp_txt = "收起详细理由 ▲" if is_expanded else "展开详细理由 ▼"
            if st.button(exp_txt, key=f"btn_exp_{cid}"):
                st.session_state[exp_key] = not is_expanded
                st.rerun()
        with btn_row_cols[1]:
            if st.button("查看原始简历", key=f"btn_res_{cid}"):
                st.session_state[res_key] = not st.session_state.get(res_key, False)
                st.rerun()
        with btn_row_cols[2]:
            if pool_label == "＋ 加入备选池":
                if st.button(pool_label, key=f"btn_pool_{cid}"):
                    add_to_pool_db(cid, preset["label"])
                    _sync_pool()
                    st.rerun()
            elif pool_label:
                st.markdown(f'<span style="font-size:12px;color:#d97706;">✓ 已在备选池</span>', unsafe_allow_html=True)

        # ── 展开：理由（原版白底 dashed 分隔）+ HR 覆盖（三按钮横排）──────────────
        if is_expanded:
            reasons_html = "".join(
                f"""<div style="display:flex;gap:12px;padding:8px 0;
                              border-bottom:1px solid #f3f4f6;">
  <span style="font-size:12px;font-weight:600;color:#374151;
               width:72px;flex-shrink:0;padding-top:1px;">{d["label"]}</span>
  <span style="font-size:12px;color:#4b5563;line-height:1.6;">
    {r["reasons"].get(d["id"],"")}</span>
</div>"""
                for d in dims
            )
            st.html(f"""
<div style="background:rgba(255,255,255,.65);border:1px dashed #e5e7eb;
            border-radius:0 0 10px 10px;padding:14px 16px;margin-top:-4px;">
  <p style="font-size:11px;font-weight:600;color:#9ca3af;text-transform:uppercase;
             letter-spacing:.06em;margin-bottom:6px;">AI 评分理由（按维度）</p>
  {reasons_html}
</div>
""")
            # HR 覆盖：三个小圆角按钮横排（对齐原版）
            st.markdown('<p style="font-size:12px;font-weight:600;color:#374151;margin:8px 0 4px;">HR 覆盖 AI 建议</p>', unsafe_allow_html=True)
            st.caption("覆盖操作会写入审计日志，留存可查。")
            cur_ov = ov_data.get("result", "")
            ov_opts = ["强推进面试", "待定", "不推进"]
            ov_cols = st.columns([1, 1, 1, 3])
            new_ov = cur_ov
            for i, opt in enumerate(ov_opts):
                with ov_cols[i]:
                    active = cur_ov == opt
                    btn_style = "primary" if active else "secondary"
                    if st.button(opt, key=f"ov_{opt}_{cid}", type=btn_style if active else "secondary"):
                        new_ov = opt if opt != cur_ov else ""
                        if new_ov:
                            st.session_state[f"ov_pending_{cid}"] = new_ov
                        else:
                            st.session_state.pop(f"ov_pending_{cid}", None)
            # 如果有待选，显示原因输入框
            pending_ov = st.session_state.get(f"ov_pending_{cid}", cur_ov)
            if pending_ov or cur_ov:
                ov_note = st.text_input(
                    "覆盖原因（必填，将留存记录）",
                    value=ov_data.get("note", ""),
                    key=f"ov_note_{cid}",
                    placeholder="请说明覆盖原因…"
                )
                save_cols = st.columns([1, 4])
                with save_cols[0]:
                    if st.button("保存", key=f"ov_save_{cid}", type="primary"):
                        effective_ov = pending_ov or cur_ov
                        if not ov_note.strip():
                            st.error("覆盖原因不能为空")
                        else:
                            st.session_state.overrides[cid] = {"result": effective_ov, "note": ov_note}
                            save_hr_override(cid, rule_id, r["ai_result"], effective_ov, ov_note)
                            st.session_state.pop(f"ov_pending_{cid}", None)
                            st.toast(f"✅ 已覆盖为「{effective_ov}」，记录已保存")
                            st.rerun()
                with save_cols[1]:
                    if cur_ov and st.button("取消覆盖", key=f"ov_cancel_{cid}"):
                        st.session_state.overrides.pop(cid, None)
                        st.session_state.pop(f"ov_pending_{cid}", None)
                        st.toast("已取消覆盖", icon="↩")
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
        st.markdown('<div style="height:12px;"></div>', unsafe_allow_html=True)


# ─── Page 3：候选人视图 ───────────────────────────────────────────────────────
def render_candidate_view():
    dims    = st.session_state.locked_dims
    fp      = st.session_state.fingerprint
    at      = st.session_state.locked_at
    results = st.session_state.screening_results

    st.markdown('<h2 style="font-size:20px;font-weight:700;color:#111827;margin-bottom:4px;">候选人视图</h2>', unsafe_allow_html=True)
    st.markdown('<p style="font-size:14px;color:#6b7280;margin-bottom:16px;">候选人登录后看到的页面（模拟）· 维度结论可见，分数不对外显示</p>', unsafe_allow_html=True)

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
        r = results[sel]; ai_r = r["ai_result"]; scores = r["scores"]
    else:
        ai_r = cand["result"]; scores = cand["scores"]

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

    ov_html = f'<p style="font-size:12px;color:#d97706;margin:4px 0 0;">HR 已调整</p>' if is_ov else ""

    st.html(f"""
<div style="border:2px solid {cm['border']};border-radius:16px;overflow:hidden;">
  <!-- Banner -->
  <div style="background:{cm['bg']};padding:20px 24px;
              display:flex;align-items:flex-start;justify-content:space-between;">
    <div>
      <p style="font-size:12px;color:#6b7280;margin:0 0 4px;">腾讯 · {jl} · 2026届秋招</p>
      <h3 style="font-size:20px;font-weight:800;color:#111827;margin:0;">您好，{cand["name"]}</h3>
    </div>
    <div style="text-align:right;">
      {_badge(final)}
      {ov_html}
    </div>
  </div>

  <!-- Body -->
  <div style="background:white;padding:20px 24px;">
    <!-- 维度结果 -->
    <p style="font-size:11px;font-weight:600;color:#9ca3af;text-transform:uppercase;
               letter-spacing:.06em;margin-bottom:4px;">评估维度结果</p>
    {dim_rows}

    <!-- 规则指纹 -->
    <div style="border:1px solid #e5e7eb;border-radius:10px;padding:14px 16px;margin-top:16px;">
      <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:6px;">
        <span style="font-size:13px;font-weight:600;color:#374151;">本次评估适用规则版本</span>
      </div>
      <div style="display:flex;align-items:center;gap:10px;">
        <span style="font-family:monospace;background:#f3f4f6;border-radius:6px;
                     padding:3px 10px;font-size:14px;font-weight:700;letter-spacing:.12em;">
          {display_fp}
        </span>
        <span style="font-size:12px;color:#9ca3af;">投递时已发送至您的邮箱</span>
      </div>
      <p style="font-size:12px;color:#9ca3af;margin:6px 0 0;">
        如指纹与邮件中一致，说明规则在您投递后未被修改。
      </p>
    </div>

    <!-- 说明 -->
    <div style="background:#f9fafb;border-radius:8px;padding:12px 14px;margin-top:14px;
                font-size:12px;color:#6b7280;line-height:1.6;">
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

    # 申诉
    st.markdown('<div style="height:8px;"></div>', unsafe_allow_html=True)
    if sel in st.session_state.appeal_submitted:
        st.success("✅ 申诉已提交，预计 5 个工作日内处理完毕。", icon="✅")
    else:
        ao_key = f"ao_{sel}"
        if not st.session_state.get(ao_key):
            if st.button("我对结果有异议，申请复核 →", key=f"ao_btn_{sel}"):
                st.session_state[ao_key] = True
                st.rerun()
        else:
            with st.container(border=True):
                st.markdown('<p style="font-size:14px;font-weight:600;color:#374151;">提交申诉</p>', unsafe_allow_html=True)
                st.caption("请说明异议理由，申诉将在 5 个工作日内处理。申诉基准为公开规则，无效申诉将大幅减少。")
                ap_text = st.text_area("申诉说明", key=f"ap_txt_{sel}",
                                        placeholder="请描述您认为评估不准确的具体原因…",
                                        height=96, label_visibility="collapsed")
                ca, sb = st.columns(2)
                with ca:
                    if st.button("取消", key=f"ap_cancel_{sel}"):
                        st.session_state[ao_key] = False
                        st.rerun()
                with sb:
                    if st.button("提交申诉", type="primary", disabled=not ap_text.strip(),
                                 key=f"ap_sub_{sel}"):
                        save_appeal(sel, cand["name"], ap_text)
                        st.session_state.appeal_submitted.add(sel)
                        st.session_state[ao_key] = False
                        st.rerun()

    # 演示说明
    NOTES = {
        "A": "王芳来自复旦（985），有主导项目和数据分析经验，强推进面试。说明系统对强 985 候选人同样公平。",
        "B": "陈志远来自深圳大学（双非），凭项目主导经验得分与复旦王芳相当，同样强推进。核心对比：双非 ≠ 低能力。",
        "D": "李思琪来自浙大（985），但无产品主导经历，按规则不推进。印证系统不因学历放行，985 也要凭实力。",
        "E": "刘晓晨来自广东工业大学（双非），项目和技能均不达标，同样不推进。系统不因双非而降低标准。",
        "F": "吴佳琪来自杭州电子科技大学（双非），有完整后端项目和开源贡献，技术维度得分高，强推进。",
        "G": "赵明远来自南京大学（985），四项维度均衡优秀，技术与项目经验充分，强推进面试。",
        "I": "周晓敏来自西安交通大学（985），缺乏后端工程经验，与岗位不匹配，按规则不推进。",
    }
    if sel in NOTES:
        st.markdown('<div style="height:12px;"></div>', unsafe_allow_html=True)
        st.html(f"""
<div style="background:#eff6ff;border:1px solid #bfdbfe;border-radius:12px;
            padding:14px 16px;font-size:13px;color:#1e40af;line-height:1.6;">
  💡 <strong>演示说明</strong> — {NOTES[sel]}
</div>""")


# ─── Page 4：简历备选池 ───────────────────────────────────────────────────────
def render_pool_view():
    pool = st.session_state.pool

    st.markdown('<h2 style="font-size:20px;font-weight:700;color:#111827;margin-bottom:4px;">简历备选池</h2>', unsafe_allow_html=True)
    st.markdown('<p style="font-size:14px;color:#6b7280;margin-bottom:16px;">跨岗位备选简历，供其他 HR 参考复用</p>', unsafe_allow_html=True)

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


# ─── 渲染入口 ─────────────────────────────────────────────────────────────────
render_header()

tab1, tab2, tab3, tab4 = st.tabs([
    "🏗 规则构建",
    "📊 筛选工作台",
    "👤 候选人视图",
    "📦 简历备选池",
])

with tab1:
    render_rule_builder()
with tab2:
    render_screening()
with tab3:
    render_candidate_view()
with tab4:
    render_pool_view()
