# app.py — 智筛 AI · Streamlit 主应用
#
# 运行方式：
#   streamlit run app.py
#
# API Key 配置：
#   .streamlit/secrets.toml 中写入：
#     OPENROUTER_API_KEY = "sk-or-v1-xxxxxxxxxxxx"

import copy
import json
import time
from datetime import datetime

import streamlit as st

from data import JOB_PRESETS, CANDIDATES, CANDIDATES_MAP
from utils import rule_fingerprint, weighted_score, result_color, build_public_page_html
from database import (
    init_db,
    save_rule,
    save_screening_result,
    get_screening_results,
    save_hr_override,
    get_hr_overrides,
    add_to_pool_db,
    remove_from_pool_db,
    get_pool_db,
    save_appeal,
)
from llm import screen_candidate_with_llm, has_api_key

# ─── 页面配置 ─────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="智筛 AI · 可信简历筛选系统",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ─── 全局 CSS ─────────────────────────────────────────────────────────────────

st.markdown("""
<style>
/* 全局字体 */
html, body, [class*="css"] { font-family: -apple-system, "PingFang SC", "Segoe UI", sans-serif; }

/* 候选人卡片颜色 */
.card-green  { border-left: 4px solid #10b981; background: #f0fdf4; padding: 12px 16px; border-radius: 8px; margin-bottom: 8px; }
.card-yellow { border-left: 4px solid #f59e0b; background: #fffbeb; padding: 12px 16px; border-radius: 8px; margin-bottom: 8px; }
.card-red    { border-left: 4px solid #ef4444; background: #fef2f2; padding: 12px 16px; border-radius: 8px; margin-bottom: 8px; }

/* 徽章 */
.badge-985  { background:#ede9fe; color:#5b21b6; border-radius:999px;
              padding:2px 8px; font-size:12px; font-weight:600; }
.badge-211  { background:#dbeafe; color:#1e40af; border-radius:999px;
              padding:2px 8px; font-size:12px; font-weight:600; }
.badge-other{ background:#f3f4f6; color:#4b5563; border-radius:999px;
              padding:2px 8px; font-size:12px; font-weight:600; }
.badge-green { background:#d1fae5; color:#065f46; border-radius:999px;
               padding:2px 10px; font-size:12px; font-weight:700; }
.badge-yellow{ background:#fef3c7; color:#92400e; border-radius:999px;
               padding:2px 10px; font-size:12px; font-weight:700; }
.badge-red   { background:#fee2e2; color:#991b1b; border-radius:999px;
               padding:2px 10px; font-size:12px; font-weight:700; }

/* 指纹框 */
.fp-box { background:#111; color:#6ee7b7; font-family:monospace;
          font-size:18px; letter-spacing:.15em; padding:10px 16px;
          border-radius:8px; display:inline-block; font-weight:700; }

/* HR 覆盖提示 */
.override-note { background:#fffbeb; border:1px solid #fde68a;
                 border-radius:8px; padding:8px 12px; font-size:13px; color:#92400e; }

/* 分隔线 */
.divider { border:none; border-top:1px dashed #e5e7eb; margin:12px 0; }
</style>
""", unsafe_allow_html=True)


# ─── Session State 初始化 ─────────────────────────────────────────────────────

def _init_state():
    defaults = {
        # Rule Builder
        "selected_job":     None,        # "pm" | "dev" | None
        "rule_locked":      False,
        "locked_dims":      None,        # list of dim dicts
        "fingerprint":      "",
        "locked_at":        "",
        "rule_id":          None,        # DB row id
        # 当前编辑中的维度权重（规则锁定前）
        "editing_dims":     None,
        # Screening
        "screening_results": {},         # {cand_id: {scores, reasons, ai_result, source}}
        "overrides":        {},          # {cand_id: {"result": str, "note": str, "saved": bool}}
        # Pool（从 DB 同步到 session）
        "pool":             [],          # [{"candidate_id", "from_job_label"}]
        # Appeal 提交状态
        "appeal_submitted": set(),       # candidate_id set
        # 公示页 HTML
        "public_html":      "",
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


_init_state()
init_db()

# ─── 从 DB 同步备选池到 session ───────────────────────────────────────────────
def _sync_pool():
    st.session_state.pool = get_pool_db()

_sync_pool()


# ─── 工具函数 ─────────────────────────────────────────────────────────────────

def _tag_badge(tag: str) -> str:
    cls = {"985": "badge-985", "211": "badge-211"}.get(tag, "badge-other")
    return f'<span class="{cls}">{tag}</span>'


def _result_badge(result: str) -> str:
    color = result_color(result)
    return f'<span class="badge-{color}">{result}</span>'


def _score_bar(value: int, dim_label: str, weight: int):
    """渲染一条维度分数进度条。"""
    color = "#10b981" if value >= 80 else "#3b82f6" if value >= 65 else "#ef4444"
    col_l, col_r = st.columns([3, 1])
    with col_l:
        st.markdown(
            f'<div style="font-size:12px;color:#6b7280;margin-bottom:2px;">'
            f'{dim_label}（{weight}%）</div>'
            f'<div style="background:#f3f4f6;border-radius:999px;height:6px;overflow:hidden;">'
            f'<div style="width:{value}%;height:6px;background:{color};'
            f'border-radius:999px;transition:width .4s;"></div></div>',
            unsafe_allow_html=True,
        )
    with col_r:
        st.markdown(
            f'<div style="font-family:monospace;font-size:13px;color:#9ca3af;'
            f'text-align:right;margin-top:4px;">{value}</div>',
            unsafe_allow_html=True,
        )


def _get_final_result(cand_id: str, ai_result: str) -> tuple[str, bool]:
    """返回 (最终结果, 是否已被HR覆盖)。"""
    ov = st.session_state.overrides.get(cand_id)
    if ov and ov.get("result"):
        return ov["result"], True
    return ai_result, False


# ─── Page 1：规则构建 ─────────────────────────────────────────────────────────

def render_rule_builder():
    st.markdown("## 规则构建")
    st.caption("选择招募岗位，AI 自动加载评估维度，确认后一键锁定发布")

    locked = st.session_state.rule_locked

    # ── 已锁定时展示锁定信息 ──────────────────────────────────────────────────
    if locked:
        dims      = st.session_state.locked_dims
        fp        = st.session_state.fingerprint
        locked_at = st.session_state.locked_at
        job_key   = st.session_state.selected_job
        job_label = JOB_PRESETS[job_key]["label"] if job_key else "自定义岗位"

        # 规则已锁定横幅
        st.success(f"🔒 规则已锁定 · 不可修改 — **{job_label}**", icon="✅")
        st.caption(f"锁定时间：{locked_at}")

        # 规则指纹
        st.markdown("**规则指纹（Rule Hash）**")
        st.markdown(f'<div class="fp-box">{fp}</div>', unsafe_allow_html=True)
        st.caption("规则内容改变时指纹随之改变，候选人可独立验证。")

        col_a, col_b = st.columns(2)
        with col_a:
            if st.button("📋 复制指纹", key="copy_fp"):
                st.code(fp)
                st.toast("已显示指纹，请手动复制", icon="📋")
        with col_b:
            if st.button("🔗 查看规则公示页", key="open_public"):
                html = build_public_page_html(dims, fp, locked_at, job_label)
                st.session_state.public_html = html

        if st.session_state.public_html:
            with st.expander("📄 规则公示页预览", expanded=True):
                st.download_button(
                    label="⬇ 下载公示页 HTML（可发送给候选人）",
                    data=st.session_state.public_html,
                    file_name="rule_public_page.html",
                    mime="text/html",
                )
                st.components.v1.html(
                    st.session_state.public_html, height=480, scrolling=True
                )

        st.markdown("---")

        # 展示锁定的维度
        st.markdown("**已锁定评估维度**")
        for d in dims:
            col1, col2 = st.columns([4, 1])
            with col1:
                st.markdown(
                    f'<div style="font-size:14px;color:#374151;">{d["label"]}</div>',
                    unsafe_allow_html=True,
                )
                st.progress(d["weight"] / 100)
            with col2:
                st.markdown(
                    f'<div style="font-size:14px;font-family:monospace;'
                    f'text-align:right;color:#6b7280;margin-top:6px;">'
                    f'{d["weight"]}%</div>',
                    unsafe_allow_html=True,
                )

        st.markdown("---")
        col_reset, col_go = st.columns(2)
        with col_reset:
            if st.button("🔄 重新设置规则", key="reset_rule"):
                st.session_state.rule_locked      = False
                st.session_state.locked_dims      = None
                st.session_state.fingerprint      = ""
                st.session_state.locked_at        = ""
                st.session_state.selected_job     = None
                st.session_state.editing_dims     = None
                st.session_state.screening_results= {}
                st.session_state.overrides        = {}
                st.session_state.rule_id          = None
                st.session_state.public_html      = ""
                st.rerun()
        with col_go:
            st.info("👉 切换到「筛选工作台」标签开始筛选", icon="ℹ️")

        return   # 锁定后不渲染下方表单

    # ── 未锁定：选岗位 + 调整权重 ────────────────────────────────────────────
    st.markdown("### 选择招募岗位")
    col_pm, col_dev = st.columns(2)

    def _select_job(key: str):
        preset = JOB_PRESETS[key]
        st.session_state.selected_job  = key
        st.session_state.editing_dims  = copy.deepcopy(preset["dims"])
        # 重置各维度 slider 的 session key
        for d in preset["dims"]:
            st.session_state[f"w_{d['id']}"] = d["weight"]

    with col_pm:
        preset_pm = JOB_PRESETS["pm"]
        selected_pm = st.session_state.selected_job == "pm"
        border = "border:2px solid #3b82f6;background:#eff6ff;" if selected_pm else "border:2px solid #e5e7eb;"
        st.markdown(
            f'<div style="{border}border-radius:12px;padding:12px 14px;cursor:pointer;">'
            f'<div style="font-weight:700;color:{"#1d4ed8" if selected_pm else "#111"};">'
            f'{preset_pm["label"]}</div>'
            f'<div style="font-size:12px;color:#9ca3af;margin-top:2px;">{preset_pm["desc"]}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
        if st.button("选择此岗位", key="sel_pm"):
            _select_job("pm")
            st.rerun()

    with col_dev:
        preset_dev = JOB_PRESETS["dev"]
        selected_dev = st.session_state.selected_job == "dev"
        border = "border:2px solid #8b5cf6;background:#f5f3ff;" if selected_dev else "border:2px solid #e5e7eb;"
        st.markdown(
            f'<div style="{border}border-radius:12px;padding:12px 14px;">'
            f'<div style="font-weight:700;color:{"#5b21b6" if selected_dev else "#111"};">'
            f'{preset_dev["label"]}</div>'
            f'<div style="font-size:12px;color:#9ca3af;margin-top:2px;">{preset_dev["desc"]}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
        if st.button("选择此岗位", key="sel_dev"):
            _select_job("dev")
            st.rerun()

    # ── 维度权重配置 ──────────────────────────────────────────────────────────
    job_key = st.session_state.selected_job
    if not job_key:
        st.info("请先选择岗位，系统将自动加载对应的评估维度。", icon="👆")
        return

    preset    = JOB_PRESETS[job_key]
    edit_dims = st.session_state.editing_dims or copy.deepcopy(preset["dims"])
    st.session_state.editing_dims = edit_dims

    st.markdown(f"---\n✅ 已加载「{preset['label']}」评估维度")

    with st.expander("查看岗位 JD"):
        st.text(preset["jd"])

    st.markdown("### 调整评估维度权重")
    st.caption("拖动滑块调整各维度权重，总计需为 100%")

    new_dims = []
    for d in edit_dims:
        w = st.slider(
            label=d["label"],
            min_value=5,
            max_value=60,
            value=st.session_state.get(f"w_{d['id']}", d["weight"]),
            step=5,
            key=f"w_{d['id']}",
            format="%d%%",
        )
        new_dims.append({**d, "weight": w})

    st.session_state.editing_dims = new_dims
    total = sum(d["weight"] for d in new_dims)

    if total == 100:
        st.success(f"✅ 总计 {total}%", icon="✅")
    else:
        st.warning(f"⚠ 总计 {total}%，需要调整至 100%")

    # ── 锁定按钮 ──────────────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown(
        "点击「锁定规则并发布」后规则**不可修改**，系统将生成规则指纹并同步公示。"
    )

    if st.button(
        "🔒 锁定规则并发布",
        disabled=(total != 100),
        type="primary",
        key="lock_btn",
    ):
        fp  = rule_fingerprint(new_dims)
        at  = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        rid = save_rule(job_key, preset["label"], new_dims, fp, at)

        st.session_state.rule_locked  = True
        st.session_state.locked_dims  = new_dims
        st.session_state.fingerprint  = fp
        st.session_state.locked_at    = at
        st.session_state.rule_id      = rid
        st.session_state.public_html  = ""
        st.rerun()


# ─── Page 2：筛选工作台 ───────────────────────────────────────────────────────

def render_screening():
    st.markdown("## 筛选工作台")
    st.caption("选择简历，AI 按锁定规则逐条评分并给出可追溯理由")

    locked    = st.session_state.rule_locked
    dims      = st.session_state.locked_dims
    job_key   = st.session_state.selected_job
    rule_id   = st.session_state.rule_id
    results   = st.session_state.screening_results

    if not locked or not dims or not job_key:
        st.info("请先在「规则构建」页完成规则锁定，再来筛选。", icon="🔒")
        return

    preset        = JOB_PRESETS[job_key]
    job_candidates = [c for c in CANDIDATES if c["job"] == job_key]

    # ── 候选人选择 ────────────────────────────────────────────────────────────
    with st.container(border=True):
        col_title, col_all = st.columns([3, 1])
        with col_title:
            st.markdown(f"**选择待筛简历** — {preset['label']}")
        with col_all:
            if st.button("全选 / 取消", key="toggle_all"):
                current = st.session_state.get("selected_cands", [])
                all_ids = [c["id"] for c in job_candidates]
                if set(current) == set(all_ids):
                    st.session_state.selected_cands = []
                else:
                    st.session_state.selected_cands = all_ids
                st.rerun()

        if "selected_cands" not in st.session_state:
            st.session_state.selected_cands = []

        cols = st.columns(2)
        for i, c in enumerate(job_candidates):
            with cols[i % 2]:
                checked = c["id"] in st.session_state.selected_cands
                tag_html = _tag_badge(c["tag"])
                label_html = (
                    f"**{c['name']}** &nbsp;"
                    f'<span style="font-size:12px;color:#6b7280;">'
                    f'{c["school"]}</span>&nbsp;{tag_html}'
                )
                if st.checkbox(
                    f"{c['name']} · {c['school']} · {c['tag']}",
                    value=checked,
                    key=f"chk_{c['id']}",
                ):
                    if c["id"] not in st.session_state.selected_cands:
                        st.session_state.selected_cands.append(c["id"])
                else:
                    if c["id"] in st.session_state.selected_cands:
                        st.session_state.selected_cands.remove(c["id"])

        selected_ids = st.session_state.selected_cands

        # ── 开始筛选按钮 ──────────────────────────────────────────────────────
        mode_label = "🤖 AI 真实评分（OpenRouter）" if has_api_key() else "📋 使用预设数据（未配置 API Key）"
        st.caption(mode_label)

        if st.button(
            "🚀 开始筛选",
            disabled=not selected_ids,
            type="primary",
            key="run_screening",
        ):
            progress_bar = st.progress(0, text="AI 评分中…")
            selected_candidates = [c for c in job_candidates if c["id"] in selected_ids]
            total = len(selected_candidates)

            for idx, cand in enumerate(selected_candidates):
                progress_bar.progress(
                    (idx) / total,
                    text=f"正在评分：{cand['name']}（{idx+1}/{total}）",
                )

                if has_api_key():
                    llm_result = screen_candidate_with_llm(cand, dims, preset["jd"])
                else:
                    llm_result = None

                if llm_result:
                    scores    = llm_result["scores"]
                    reasons   = llm_result["reasons"]
                    ai_result = llm_result["ai_result"]
                    source    = "ai"
                else:
                    # 降级：使用 data.py 预设数据
                    scores    = cand["scores"]
                    reasons   = cand["reasons"]
                    ai_result = cand["result"]
                    source    = "preset"

                st.session_state.screening_results[cand["id"]] = {
                    "scores":    scores,
                    "reasons":   reasons,
                    "ai_result": ai_result,
                    "source":    source,
                }
                save_screening_result(cand["id"], rule_id, scores, reasons, ai_result, source)
                time.sleep(0.3)   # 让进度条可见

            progress_bar.progress(1.0, text="评分完成 ✓")
            time.sleep(0.5)
            st.rerun()

    # ── 汇总栏 ───────────────────────────────────────────────────────────────
    if results:
        all_results_list = []
        for cid, r in results.items():
            final, _ = _get_final_result(cid, r["ai_result"])
            all_results_list.append(final)

        total_n  = len(all_results_list)
        strong_n = sum(1 for r in all_results_list if r == "强推进面试")
        pending_n= sum(1 for r in all_results_list if r == "待定")
        reject_n = sum(1 for r in all_results_list if r == "不推进")
        auto_rate= round(((strong_n + reject_n) / total_n) * 100) if total_n else 0

        with st.container(border=True):
            c1, c2, c3, c4, c5 = st.columns(5)
            c1.metric("本次筛选", f"{total_n} 份")
            c2.metric("强推进", strong_n, delta=None)
            c3.metric("待定", pending_n)
            c4.metric("不推进", reject_n)
            c5.metric("AI 自动处理率", f"{auto_rate}%")

    # ── 候选人结果卡片 ────────────────────────────────────────────────────────
    if not results:
        return

    for cand in job_candidates:
        cid = cand["id"]
        if cid not in results:
            continue

        r           = results[cid]
        final_res, is_ov = _get_final_result(cid, r["ai_result"])
        color       = result_color(final_res)
        score       = weighted_score(r["scores"], dims)
        card_cls    = f"card-{color}"
        source_tag  = "🤖 AI" if r.get("source") == "ai" else "📋 预设"

        with st.container():
            # 卡片头部
            st.markdown(
                f'<div class="{card_cls}">',
                unsafe_allow_html=True,
            )
            col_info, col_score = st.columns([5, 2])
            with col_info:
                st.markdown(
                    f'**{cand["name"]}** &nbsp;'
                    f'<span style="background:#f3f4f6;border-radius:999px;'
                    f'padding:2px 8px;font-size:12px;color:#374151;">'
                    f'{cand["school"]}</span>&nbsp;'
                    f'{_tag_badge(cand["tag"])}'
                    f'<span style="font-size:11px;color:#9ca3af;margin-left:6px;">'
                    f'{source_tag}</span>',
                    unsafe_allow_html=True,
                )
                st.caption(cand["summary"])
                if is_ov:
                    ov_data = st.session_state.overrides.get(cid, {})
                    st.markdown(
                        f'<div class="override-note">⚠ HR 已覆盖：原 AI 建议「{r["ai_result"]}」'
                        f'→ 调整为「{final_res}」<br/>'
                        f'覆盖原因：{ov_data.get("note","")}</div>',
                        unsafe_allow_html=True,
                    )
            with col_score:
                st.markdown(
                    f'<div style="text-align:right;">'
                    f'{_result_badge(final_res)}<br/>'
                    f'<span style="font-size:28px;font-weight:900;color:#111;">{score}</span>'
                    f'<span style="font-size:14px;color:#9ca3af;"> 分</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
            st.markdown("</div>", unsafe_allow_html=True)

            # 分数条
            for d in dims:
                _score_bar(r["scores"].get(d["id"], 0), d["label"], d["weight"])

            # 操作按钮行
            btn_col1, btn_col2, btn_col3, btn_col4 = st.columns([2, 2, 2, 3])
            with btn_col1:
                expand_key = f"expand_{cid}"
                if st.session_state.get(expand_key):
                    if st.button("▲ 收起理由", key=f"collapse_{cid}"):
                        st.session_state[expand_key] = False
                        st.rerun()
                else:
                    if st.button("▼ 展开理由", key=f"expand_btn_{cid}"):
                        st.session_state[expand_key] = True
                        st.rerun()
            with btn_col2:
                if st.button("📄 查看简历", key=f"resume_{cid}"):
                    st.session_state[f"show_resume_{cid}"] = not st.session_state.get(f"show_resume_{cid}", False)
                    st.rerun()
            with btn_col3:
                pool_ids = [p["candidate_id"] for p in st.session_state.pool]
                if final_res == "不推进":
                    if cid in pool_ids:
                        st.markdown(
                            '<span style="color:#d97706;font-size:13px;">✓ 已在备选池</span>',
                            unsafe_allow_html=True,
                        )
                    else:
                        if st.button("➕ 加入备选池", key=f"pool_{cid}"):
                            job_label = JOB_PRESETS[job_key]["label"]
                            add_to_pool_db(cid, job_label)
                            _sync_pool()
                            st.rerun()

            # 展开：AI 评分理由 + HR 覆盖
            if st.session_state.get(f"expand_{cid}"):
                with st.container(border=True):
                    st.markdown("**AI 评分理由（按维度）**")
                    for d in dims:
                        c_l, c_r = st.columns([1, 4])
                        with c_l:
                            st.markdown(
                                f'<span style="font-size:13px;font-weight:600;'
                                f'color:#374151;">{d["label"]}</span>',
                                unsafe_allow_html=True,
                            )
                        with c_r:
                            st.markdown(
                                f'<span style="font-size:13px;color:#4b5563;">'
                                f'{r["reasons"].get(d["id"], "")}</span>',
                                unsafe_allow_html=True,
                            )
                        st.markdown('<hr class="divider"/>', unsafe_allow_html=True)

                    # HR 覆盖区域
                    st.markdown("**HR 覆盖 AI 建议**")
                    st.caption("覆盖操作将留存审计记录。")
                    ov_data = st.session_state.overrides.get(cid, {})

                    ov_options = ["（不覆盖）", "强推进面试", "待定", "不推进"]
                    current_ov = ov_data.get("result", "")
                    default_idx = ov_options.index(current_ov) if current_ov in ov_options else 0

                    new_ov = st.selectbox(
                        "调整为",
                        ov_options,
                        index=default_idx,
                        key=f"ov_sel_{cid}",
                    )
                    ov_note = st.text_input(
                        "覆盖原因（必填，将留存记录）",
                        value=ov_data.get("note", ""),
                        key=f"ov_note_{cid}",
                        placeholder="请说明覆盖原因…",
                    )
                    if st.button("保存覆盖", key=f"ov_save_{cid}"):
                        if new_ov == "（不覆盖）":
                            st.session_state.overrides.pop(cid, None)
                            st.toast("已取消覆盖", icon="↩")
                        elif not ov_note.strip():
                            st.error("覆盖原因不能为空")
                        else:
                            st.session_state.overrides[cid] = {
                                "result": new_ov,
                                "note":   ov_note,
                            }
                            save_hr_override(
                                cid, rule_id, r["ai_result"],
                                new_ov, ov_note,
                            )
                            st.toast(f"✅ 已覆盖为「{new_ov}」，记录已保存", icon="✅")
                            st.rerun()

            # 简历弹出
            if st.session_state.get(f"show_resume_{cid}"):
                with st.expander(f"📄 {cand['name']} 的原始简历", expanded=True):
                    resume = cand["resume"]
                    st.markdown(
                        f"**{cand['name']}** · {cand['school']} · {cand['major']} · {cand['tag']}"
                    )
                    st.caption(f"GPA {resume.get('gpa', '—')} · {resume.get('period', '')}")
                    st.markdown("---")
                    for exp in resume.get("experiences", []):
                        st.markdown(f"**{exp['title']}**")
                        st.caption(f"{exp['org']} &nbsp;&nbsp; {exp['period']}")
                        for b in exp.get("bullets", []):
                            st.markdown(f"  · {b}")
                        st.markdown("")
                    st.markdown(f"🛠 **技能**：{resume.get('skills', '')}")
                    awards = resume.get("awards", "")
                    if awards and awards != "无":
                        st.markdown(f"🏆 **奖项**：{awards}")

            st.markdown("---")


# ─── Page 3：候选人视图 ───────────────────────────────────────────────────────

def render_candidate_view():
    st.markdown("## 候选人视图")
    st.caption("候选人登录后看到的页面（模拟）。维度结论可见，具体分数不对外显示。")

    dims      = st.session_state.locked_dims
    fp        = st.session_state.fingerprint
    locked_at = st.session_state.locked_at
    job_key   = st.session_state.selected_job
    results   = st.session_state.screening_results

    # ── 候选人选择器（分组） ──────────────────────────────────────────────────
    st.markdown("**切换候选人**")
    for group in [("pm", "产品经理岗"), ("dev", "后端开发岗")]:
        g_key, g_label = group
        cands = [c for c in CANDIDATES if c["job"] == g_key]
        st.caption(g_label)
        btn_cols = st.columns(len(cands))
        for i, c in enumerate(cands):
            with btn_cols[i]:
                if st.button(c["name"], key=f"cv_sel_{c['id']}"):
                    st.session_state.cv_selected = c["id"]
                    st.session_state[f"appeal_open_{c['id']}"] = False
                    st.rerun()

    sel_id = st.session_state.get("cv_selected", "B")
    cand   = CANDIDATES_MAP.get(sel_id)
    if not cand:
        return

    # 确定结果：有筛选结果取筛选结果，没有则用预设
    if sel_id in results:
        r         = results[sel_id]
        ai_result = r["ai_result"]
        scores    = r["scores"]
    else:
        ai_result = cand["result"]
        scores    = cand["scores"]

    final_res, is_ov = _get_final_result(sel_id, ai_result)
    color  = result_color(final_res)
    # 使用候选人自己岗位的维度（避免跨岗位维度 ID 错位）
    display_dims = JOB_PRESETS[cand["job"]]["dims"]
    job_label    = JOB_PRESETS[cand["job"]]["label"]

    st.markdown("---")

    # ── 候选人结果主卡片 ──────────────────────────────────────────────────────
    with st.container(border=True):
        col_l, col_r = st.columns([3, 2])
        with col_l:
            st.markdown(
                f'<span style="font-size:12px;color:#9ca3af;">'
                f'腾讯 · {job_label} · 2026届秋招</span>',
                unsafe_allow_html=True,
            )
            st.markdown(f"### 您好，{cand['name']}")
        with col_r:
            st.markdown(
                f'<div style="text-align:right;padding-top:8px;">'
                f'{_result_badge(final_res)}'
                f'{"<br/><span style=\'font-size:11px;color:#d97706;\'>HR 已调整</span>" if is_ov else ""}'
                f'</div>',
                unsafe_allow_html=True,
            )

        st.markdown("---")

        # 评估维度结果（只显示通过/未通过，不显示分数）
        st.markdown("**评估维度结果**")
        for d in display_dims:
            s     = scores.get(d["id"], 0)
            pass_ = s >= 65
            tag   = "✅ 符合要求" if pass_ else "⚠️ 有待提升"
            col_name, col_tag = st.columns([4, 1])
            with col_name:
                st.markdown(
                    f'<span style="font-size:14px;font-weight:500;color:#111;">'
                    f'{d["label"]}</span>'
                    f'<span style="font-size:12px;color:#9ca3af;margin-left:6px;">'
                    f'权重 {d["weight"]}%</span>',
                    unsafe_allow_html=True,
                )
            with col_tag:
                style = "color:#065f46;background:#d1fae5;" if pass_ else "color:#991b1b;background:#fee2e2;"
                st.markdown(
                    f'<div style="{style}border-radius:999px;padding:3px 10px;'
                    f'font-size:12px;font-weight:600;text-align:center;">{tag}</div>',
                    unsafe_allow_html=True,
                )
            st.markdown('<hr class="divider"/>', unsafe_allow_html=True)

        # 规则指纹验证区
        st.markdown("**本次评估适用规则版本**")
        display_fp = fp if fp else rule_fingerprint(display_dims)
        col_fp, col_link = st.columns([3, 1])
        with col_fp:
            st.markdown(
                f'<span style="font-family:monospace;background:#f3f4f6;'
                f'border-radius:6px;padding:3px 8px;font-size:13px;">'
                f'{display_fp}</span>'
                f'<span style="font-size:12px;color:#9ca3af;margin-left:8px;">'
                f'投递时已发送至您的邮箱</span>',
                unsafe_allow_html=True,
            )
        with col_link:
            if st.button("查看公示页 ↗", key=f"pub_{sel_id}"):
                if dims and fp:
                    html = build_public_page_html(dims, fp, locked_at, job_label)
                    st.session_state.public_html = html
                else:
                    st.toast("请先在规则构建页锁定规则", icon="⚠️")

        if st.session_state.public_html:
            with st.expander("📄 规则公示页", expanded=False):
                st.download_button(
                    "⬇ 下载公示页 HTML",
                    data=st.session_state.public_html,
                    file_name="rule_public_page.html",
                    mime="text/html",
                )
                st.components.v1.html(st.session_state.public_html, height=440, scrolling=True)

        st.info(
            "ℹ 评估结果基于公开发布的岗位规则，各维度分数不对外显示。"
            "如对结果有异议，可在下方提交申诉。",
            icon="ℹ️",
        )

        # ── 申诉入口 ─────────────────────────────────────────────────────────
        if sel_id in st.session_state.appeal_submitted:
            st.success("✅ 申诉已提交，预计 5 个工作日内处理完毕。", icon="✅")
        else:
            appeal_key = f"appeal_open_{sel_id}"
            if not st.session_state.get(appeal_key):
                if st.button("我对结果有异议，申请复核 →", key=f"appeal_btn_{sel_id}"):
                    st.session_state[appeal_key] = True
                    st.rerun()
            else:
                st.markdown("**提交申诉**")
                st.caption("请说明异议理由，申诉将在 5 个工作日内处理。")
                appeal_text = st.text_area(
                    "申诉说明",
                    key=f"appeal_text_{sel_id}",
                    placeholder="请描述您认为评估不准确的具体原因…",
                    height=100,
                    label_visibility="collapsed",
                )
                col_cancel, col_submit = st.columns(2)
                with col_cancel:
                    if st.button("取消", key=f"appeal_cancel_{sel_id}"):
                        st.session_state[appeal_key] = False
                        st.rerun()
                with col_submit:
                    if st.button(
                        "提交申诉",
                        disabled=not appeal_text.strip(),
                        type="primary",
                        key=f"appeal_submit_{sel_id}",
                    ):
                        save_appeal(sel_id, cand["name"], appeal_text)
                        st.session_state.appeal_submitted.add(sel_id)
                        st.session_state[appeal_key] = False
                        st.rerun()

    # ── 演示说明气泡 ─────────────────────────────────────────────────────────
    DEMO_NOTES = {
        "A": "王芳来自复旦（985），有主导项目和数据分析经验，强推进面试。说明系统对强 985 候选人同样公平。",
        "B": "陈志远来自深圳大学（双非），凭项目主导经验得分与复旦王芳相当，同样强推进。核心对比：双非 ≠ 低能力。",
        "D": "李思琪来自浙大（985），但无产品主导经历，按规则不推进。印证系统不因学历放行，985 也要凭实力。",
        "E": "刘晓晨来自广东工业大学（双非），项目和技能均不达标，同样不推进。印证系统不因双非而降低标准。",
        "F": "吴佳琪来自杭州电子科技大学（双非），有完整后端项目和开源贡献，技术与算法维度得分高，强推进。",
        "G": "赵明远来自南京大学（985），四项维度均衡优秀，技术与项目经验充分，强推进面试。",
        "I": "周晓敏来自西安交通大学（985），缺乏后端工程经验，算法竞赛背景与岗位不匹配，按规则不推进。",
    }
    if sel_id in DEMO_NOTES:
        st.info(f"💡 **演示说明** — {DEMO_NOTES[sel_id]}", icon="💡")


# ─── Page 4：简历备选池 ───────────────────────────────────────────────────────

def render_pool_view():
    st.markdown("## 简历备选池")
    st.caption("跨岗位备选简历，供其他 HR 参考复用。不推进的候选人可在筛选工作台加入备选池。")

    pool = st.session_state.pool

    if not pool:
        st.info("备选池暂无简历。在筛选工作台对「不推进」候选人点击「加入备选池」即可加入。", icon="📭")
        return

    st.info(
        "💡 这些候选人虽未通过本岗位筛选，但可能匹配其他部门需求。"
        "各岗位 HR 可在此浏览并联系感兴趣的候选人。",
        icon="💡",
    )
    st.markdown(f"**共 {len(pool)} 份备选简历**")
    st.markdown("---")

    for entry in pool:
        cid  = entry["candidate_id"]
        cand = CANDIDATES_MAP.get(cid)
        if not cand:
            continue

        with st.container(border=True):
            col_info, col_btn = st.columns([5, 1])
            with col_info:
                st.markdown(
                    f'**{cand["name"]}** &nbsp;'
                    f'<span style="background:#f3f4f6;border-radius:999px;'
                    f'padding:2px 8px;font-size:12px;">{cand["school"]}</span>&nbsp;'
                    f'{_tag_badge(cand["tag"])}',
                    unsafe_allow_html=True,
                )
                st.caption(cand["summary"])
                st.markdown(
                    f'<span style="font-size:12px;color:#9ca3af;">来源岗位：</span>'
                    f'<span style="font-size:12px;color:#374151;">'
                    f'{entry["from_job_label"]}</span>'
                    f'<span style="font-size:12px;color:#ef4444;margin-left:6px;">'
                    f'· 未通过</span>',
                    unsafe_allow_html=True,
                )
            with col_btn:
                if st.button("移出", key=f"rm_pool_{cid}"):
                    remove_from_pool_db(cid)
                    _sync_pool()
                    st.rerun()


# ─── 顶部 Header ──────────────────────────────────────────────────────────────

def render_header():
    col_logo, col_status = st.columns([3, 4])
    with col_logo:
        st.markdown(
            '<div style="display:flex;align-items:center;gap:10px;">'
            '<div style="width:32px;height:32px;background:#111;border-radius:8px;'
            'display:flex;align-items:center;justify-content:center;">'
            '<span style="color:white;font-weight:700;font-size:14px;">智</span></div>'
            '<span style="font-weight:800;font-size:18px;color:#111;">智筛 AI</span>'
            '<span style="font-size:12px;color:#9ca3af;">· 可信简历筛选系统</span>'
            '</div>',
            unsafe_allow_html=True,
        )
    with col_status:
        badges = []
        if st.session_state.rule_locked:
            job_key   = st.session_state.selected_job
            job_label = JOB_PRESETS[job_key]["label"] if job_key else "自定义"
            badges.append(
                f'<span style="background:#111;color:#fff;border-radius:999px;'
                f'padding:3px 10px;font-size:12px;margin-right:6px;">'
                f'🔒 {job_label} · 规则已锁定</span>'
            )
        pool_n = len(st.session_state.pool)
        if pool_n > 0:
            badges.append(
                f'<span style="background:#f59e0b;color:#fff;border-radius:999px;'
                f'padding:3px 10px;font-size:12px;">📦 备选池 {pool_n}</span>'
            )
        if not has_api_key():
            badges.append(
                '<span style="background:#fef3c7;color:#92400e;border-radius:999px;'
                'padding:3px 10px;font-size:12px;">⚠ 未配置 API Key · 使用预设数据</span>'
            )
        if badges:
            st.markdown(
                '<div style="display:flex;align-items:center;justify-content:flex-end;gap:6px;padding-top:4px;">'
                + "".join(badges) + "</div>",
                unsafe_allow_html=True,
            )


# ─── 主入口 ──────────────────────────────────────────────────────────────────

render_header()
st.markdown("---")

tab1, tab2, tab3, tab4 = st.tabs(
    ["🏗 规则构建", "📊 筛选工作台", "👤 候选人视图", "📦 简历备选池"]
)

with tab1:
    render_rule_builder()

with tab2:
    render_screening()

with tab3:
    render_candidate_view()

with tab4:
    render_pool_view()
