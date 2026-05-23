# llm.py — OpenRouter API 调用（Claude 模型）
#
# 填写 API Key 方式：
#   1. 本地运行：在项目根目录创建 .streamlit/secrets.toml，写入：
#        OPENROUTER_API_KEY = "sk-or-v1-xxxxxxxxxxxx"
#   2. Streamlit Cloud 部署：在 App Settings → Secrets 粘贴同样内容。
#
# 模型默认使用 anthropic/claude-3.5-sonnet。
# 如需换用其他 Claude 版本，在 secrets.toml 中增加：
#        OPENROUTER_MODEL = "anthropic/claude-3-opus"

import json
import os
import requests

from utils import build_resume_text

OPENROUTER_BASE = "https://openrouter.ai/api/v1"
DEFAULT_MODEL   = "anthropic/claude-3.5-haiku"   # claude-3.5-sonnet 已从 OR 下线


# ─── 配置读取 ─────────────────────────────────────────────────────────────────

def _api_key() -> str:
    """先尝试 Streamlit secrets，再回退到环境变量。"""
    try:
        import streamlit as st
        return st.secrets.get("OPENROUTER_API_KEY", "")
    except Exception:
        return os.environ.get("OPENROUTER_API_KEY", "")


def _model() -> str:
    try:
        import streamlit as st
        return st.secrets.get("OPENROUTER_MODEL", DEFAULT_MODEL)
    except Exception:
        return os.environ.get("OPENROUTER_MODEL", DEFAULT_MODEL)


def has_api_key() -> bool:
    return bool(_api_key())


# ─── 内部 HTTP helper ─────────────────────────────────────────────────────────

def _chat(payload: dict, timeout: int = 45) -> requests.Response:
    """统一的 OpenRouter chat 请求。
    - Header 全部使用 ASCII，避免 Python 3.14 对非 ASCII header 的 UnicodeEncodeError
    - Body 显式序列化为 UTF-8 bytes，ensure_ascii=False 保留中文原文
    """
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    return requests.post(
        f"{OPENROUTER_BASE}/chat/completions",
        headers={
            "Authorization": f"Bearer {_api_key()}",
            "Content-Type": "application/json; charset=utf-8",
            "HTTP-Referer": "https://zhishai.streamlit.app",
            "X-Title": "ZhiShai-AI",   # ASCII only — no Chinese in headers
        },
        data=body,
        timeout=timeout,
    )


# ─── 维度提取（与 JD 任职要求一一对应） ───────────────────────────────────────

def extract_dims_from_jd(jd: str, job_label: str = "") -> tuple:
    """
    从 JD 的「任职要求」中提取评估维度，每条要求对应且仅对应一个维度。

    返回：(dims, error_msg)
      - 成功：(list[dict], None)
      - 失败：(None, str)  —— error_msg 可直接展示给用户
    """
    import logging

    api_key = _api_key()
    if not api_key:
        return None, "未配置 API Key（OPENROUTER_API_KEY）"

    prompt = f"""你是一名 HR 规则构建助手。请从以下招聘 JD 中提取评估维度。

【岗位】{job_label}

【JD 原文】
{jd}

【提取规则（严格执行，违反则结果无效）】
1. 只读取 JD 中「任职要求」部分的每一条要求
2. 每条任职要求 → 对应且仅对应一个评估维度，顺序与原文保持一致
3. 维度 label：必须直接从该条要求原文中摘取最核心的 2-6 个汉字短语，
   不得改写或意译——相同 JD 多次提取必须得到完全一致的 label（这是可信指纹的基础）
4. 维度 id：对应 label 的英文简写（小写+下划线，如 project_exp）
5. 各维度权重初始设为相等（总计恰好 100%；若不能整除，将余数加到最后一个维度）
6. 绝对禁止：不得合并多条要求为一个维度，不得凭空增加 JD 未写明的维度

【输出格式 — 只输出合法 JSON，不要任何解释或 markdown 代码块】
{{
  "dims": [
    {{"id": "dim_id", "label": "维度名称", "weight": 25}},
    ...
  ]
}}"""

    try:
        resp = _chat({
            "model": _model(),
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1,
        }, timeout=45)
    except requests.exceptions.Timeout:
        return None, "请求超时（>45s），请稍后重试"
    except requests.exceptions.ConnectionError as e:
        return None, f"网络连接失败：{e}"
    except Exception as e:
        return None, f"请求异常：{e}"

    if not resp.ok:
        return None, f"API 错误 {resp.status_code}：{resp.text[:300]}"

    try:
        raw = resp.json()["choices"][0]["message"]["content"]
    except (KeyError, IndexError, ValueError) as e:
        return None, f"API 响应格式异常：{e}\n原始响应：{resp.text[:300]}"

    # 从可能含 markdown 代码块的响应中提取 JSON
    text = raw.strip()
    if "```" in text:
        # 去掉 ```json ... ``` 包装
        text = text.split("```")[-2] if text.count("```") >= 2 else text
        text = text.lstrip("json").strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        return None, f"JSON 解析失败：{e}\n模型原始输出：{raw[:400]}"

    dims = data.get("dims")
    if not dims or not isinstance(dims, list):
        return None, f"模型返回结构缺少 'dims' 字段\n原始输出：{raw[:400]}"

    for d in dims:
        if not all(k in d for k in ("id", "label", "weight")):
            return None, f"维度字段不完整（需要 id/label/weight）：{d}"

    # 确保权重总和 = 100
    total = sum(d["weight"] for d in dims)
    if total != 100:
        dims[-1]["weight"] += 100 - total

    logging.info(f"[智筛 LLM] 维度提取成功，共 {len(dims)} 个维度")
    return dims, None


# ─── 简历评分 ─────────────────────────────────────────────────────────────────

def screen_candidate_with_llm(candidate: dict, dims: list, jd: str) -> dict | None:
    """
    调用 Claude 对单份简历评分。
    返回格式：
        {
          "scores":      {"dim_id": int, ...},
          "reasons":     {"dim_id": str, ...},
          "ai_result":   "强推进面试" | "待定" | "不推进",
          "source":      "ai"
        }
    失败（无 key / 解析错误 / 超时）时返回 None，调用方降级为预设数据。
    """
    api_key = _api_key()
    if not api_key:
        return None

    dims_text = "\n".join(
        f'  - {d["label"]}（权重 {d["weight"]}%）：请从简历可观察事实中打分 0-100'
        for d in dims
    )
    scores_placeholder = ", ".join(f'"{d["id"]}": <0-100 整数>' for d in dims)
    reasons_placeholder = ", ".join(f'"{d["id"]}": "<一句话理由，必须引用维度名称>"' for d in dims)

    resume_text = build_resume_text(candidate)

    prompt = f"""你是一名专业的 HR 筛选助手，负责按照锁定规则对候选人简历进行客观评分。

【岗位】{dims[0].get("job_label", "未知岗位")} — {jd[:300]}...

【锁定评估维度（不可更改）】
{dims_text}

【绝对禁止 — 违反则结果无效】
- 简历中已移除院校名称，你收到的文本中没有院校排名信号，也不应主动推断
- 学历层次（本科/硕士/博士）、性别、年龄、公司知名度本身不得影响任何维度分数
- 评分只能基于简历中可观察的具体行为事实（做了什么、量化结果是什么）
- 无直接事实证据的维度必须给低分，不得因"背景看起来不错"而补分
- 每条理由必须引用上述维度名称，并指向简历中的具体事实
- 严禁晕轮效应（Halo Effect）：不得因候选人整体印象好/差而拉高或压低其他维度
  · 即使候选人整体很强，若某维度证据不足，该维度仍必须给低分
  · 即使候选人整体较弱，若某维度有具体证据，该维度仍应客观打分

【独立评分要求】
- 每个维度必须单独对照简历证据评分，与其他维度无关
- 真实候选人各维度通常存在明显差异（如项目强但表达弱，或技术强但协作弱）
- 如果你给出的所有维度分数都很接近，说明可能存在晕轮效应，请重新检查

【候选人简历】
{resume_text}

【评分标准】
85-100：该维度有突出量化成果，远超岗位要求
70-84 ：该维度基本符合，有具体事实支撑
55-69 ：该维度部分满足，证据有限或质量一般
0-54  ：该维度证据不足或与岗位要求明显不符

【推荐标准】
- 强推进面试：加权总分 ≥75
- 不推进：加权总分 <65
- 待定：加权总分 65–74（证据真正模糊、难以判断时才用，此区间应占所有候选人 ≤20%）

【特别提醒】
- "不推进" 并非否定候选人整体价值，而是本岗位证据不足
- 候选人背景再光鲜（名校/大厂/竞赛），若简历中无本岗位的可观察证据，也应给出"不推进"
- 宁可给出"不推进"再补面试，也不因背景印象膨胀为"待定"
- "待定" 是高成本决策，仅在候选人综合证据真正处于临界线、HR 介入能带来实质判断价值时使用；总分低于 65 的候选人即便背景亮眼也应给出"不推进"

【输出格式 — 只输出 JSON，不要任何其他内容】
{{
  "scores": {{{scores_placeholder}}},
  "reasons": {{{reasons_placeholder}}},
  "ai_result": "强推进面试 或 待定 或 不推进"
}}"""

    try:
        resp = _chat({
            "model": _model(),
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1,
            "response_format": {"type": "json_object"},
        }, timeout=45)
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]
        data = json.loads(content)

        # 校验必要字段
        if "scores" not in data or "reasons" not in data or "ai_result" not in data:
            return None

        # 确保 ai_result 是合法值
        valid_results = {"强推进面试", "待定", "不推进"}
        if data["ai_result"] not in valid_results:
            data["ai_result"] = "待定"

        data["source"] = "ai"
        return data

    except Exception as e:
        import logging
        logging.warning(f"[智筛 LLM] 调用失败，回退预设数据: {e}")
        return None
