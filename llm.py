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


# ─── 维度提取（与 JD 任职要求一一对应） ───────────────────────────────────────

def extract_dims_from_jd(jd: str, job_label: str = "") -> list | None:
    """
    从 JD 的「任职要求」中提取评估维度，每条要求对应且仅对应一个维度。
    返回格式：
        [{"id": str, "label": str, "weight": int}, ...]
    失败时返回 None，调用方回退到预设维度。
    """
    api_key = _api_key()
    if not api_key:
        return None

    prompt = f"""你是一名 HR 规则构建助手。请从以下招聘 JD 中提取评估维度。

【岗位】{job_label}

【JD 原文】
{jd}

【提取规则（严格执行，违反则结果无效）】
1. 只读取 JD 中「任职要求」部分的每一条要求
2. 每条任职要求 → 对应且仅对应一个评估维度，顺序与原文保持一致
3. 维度 label 用 4-8 个汉字概括该条要求的核心能力点
4. 维度 id 用英文小写+下划线命名（如 project_exp、coding_skill）
5. 各维度权重初始设为相等（总计恰好 100%；若不能整除，将余数加到最后一个维度）
6. 绝对禁止：不得合并多条要求为一个维度，不得凭空增加 JD 未写明的维度

【输出格式 — 只输出 JSON，不要任何其他内容】
{{
  "dims": [
    {{"id": "dim_id", "label": "维度名称", "weight": 25}},
    ...
  ]
}}"""

    try:
        resp = requests.post(
            f"{OPENROUTER_BASE}/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://zhishai.streamlit.app",
                "X-Title": "智筛 AI",
            },
            json={
                "model": _model(),
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.1,
                "response_format": {"type": "json_object"},
            },
            timeout=30,
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]
        data = json.loads(content)

        dims = data.get("dims")
        if not dims or not isinstance(dims, list):
            return None

        # 校验每个维度的必要字段
        for d in dims:
            if not all(k in d for k in ("id", "label", "weight")):
                return None

        # 确保权重总和 = 100（防模型输出误差）
        total = sum(d["weight"] for d in dims)
        if total != 100:
            diff = 100 - total
            dims[-1]["weight"] += diff

        return dims

    except Exception as e:
        import logging
        logging.warning(f"[智筛 LLM] 维度提取失败，回退预设: {e}")
        return None


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
- 院校排名、学历层次、性别、年龄不得影响任何维度分数
- 评分只能基于简历中可观察的具体事实
- 每条理由必须引用上述维度名称（如「符合『项目经验』维度要求」）

【候选人简历】
{resume_text}

【评分标准】
80-100：完全符合维度要求，有量化实例支撑
65-79 ：基本符合，略有不足
50-64 ：部分符合，明显缺失
0-49  ：不符合岗位要求

【推荐标准】
- 强推进面试：加权总分 ≥75 且核心维度均 ≥65
- 不推进：加权总分 <60 或核心维度严重不足（<50）
- 待定：介于两者之间

【输出格式 — 只输出 JSON，不要任何其他内容】
{{
  "scores": {{{scores_placeholder}}},
  "reasons": {{{reasons_placeholder}}},
  "ai_result": "强推进面试 或 待定 或 不推进"
}}"""

    try:
        resp = requests.post(
            f"{OPENROUTER_BASE}/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://zhishai.streamlit.app",
                "X-Title": "智筛 AI",
            },
            json={
                "model": _model(),
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.1,
                "response_format": {"type": "json_object"},
            },
            timeout=45,
        )
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
