# utils.py — 工具函数

import json


def rule_fingerprint(dims: list) -> str:
    """FNV-1a 哈希，与 demo.html 中的 JS 实现完全一致。
    规则内容改变一个字，指纹随之改变。"""
    payload = json.dumps(
        [{"id": d["id"], "weight": d["weight"]} for d in dims],
        ensure_ascii=False,
        separators=(",", ":"),
    )
    h = 0x811C9DC5
    for ch in payload:
        h ^= ord(ch)
        h = (h * 0x01000193) & 0xFFFFFFFF
    return h.to_bytes(4, "big").hex().upper()


def weighted_score(scores: dict, dims: list) -> int:
    """按维度权重计算加权总分（整数）。"""
    total, total_weight = 0, 0
    for d in dims:
        total += scores.get(d["id"], 0) * d["weight"]
        total_weight += d["weight"]
    return round(total / total_weight) if total_weight > 0 else 0


def result_color(result: str) -> str:
    """结果 → 颜色标识（green / yellow / red）。"""
    if result == "强推进面试":
        return "green"
    if result == "待定":
        return "yellow"
    return "red"


def build_resume_text(candidate: dict) -> str:
    """把候选人 resume 结构拼成纯文本，供 LLM 阅读。"""
    r = candidate["resume"]
    lines = []
    lines.append(f"学校：{candidate['school']}（仅供记录，不得用于评分）")
    lines.append(f"专业：{candidate['major']}　GPA：{r.get('gpa', '未知')}")
    lines.append("")
    lines.append("=== 项目 / 实习经历 ===")
    for exp in r.get("experiences", []):
        lines.append(f"\n【{exp['title']}】{exp['org']}  {exp['period']}")
        for b in exp.get("bullets", []):
            lines.append(f"  · {b}")
    lines.append(f"\n技能：{r.get('skills', '')}")
    awards = r.get("awards", "")
    if awards and awards != "无":
        lines.append(f"奖项：{awards}")
    return "\n".join(lines)


def build_public_page_html(dims: list, fp: str, locked_at: str, job_label: str) -> str:
    """生成与 demo.html 风格一致的规则公示页 HTML。"""
    rows = "".join(
        f'<tr><td style="padding:10px 16px;border-bottom:1px solid #f0f0f0;'
        f'font-size:14px;color:#111">{d["label"]}</td>'
        f'<td style="padding:10px 16px;border-bottom:1px solid #f0f0f0;'
        f'font-size:14px;color:#555;text-align:right">{d["weight"]}%</td></tr>'
        for d in dims
    )
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1"/>
  <title>筛选规则公示页 · 智筛 AI</title>
  <style>
    *{{box-sizing:border-box;margin:0;padding:0}}
    body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
         background:#f7f8fa;min-height:100vh;padding:40px 16px}}
    .card{{max-width:520px;margin:0 auto;background:#fff;border-radius:16px;
           border:1px solid #e5e7eb;overflow:hidden}}
    .header{{background:#111;color:#fff;padding:24px 28px}}
    .header h1{{font-size:18px;font-weight:700;margin-bottom:4px}}
    .header p{{font-size:12px;color:#9ca3af}}
    .body{{padding:24px 28px;display:flex;flex-direction:column;gap:20px}}
    .fp-box{{background:#f9fafb;border:1px solid #e5e7eb;border-radius:10px;padding:14px 16px}}
    .fp-label{{font-size:11px;color:#9ca3af;text-transform:uppercase;
               letter-spacing:.06em;margin-bottom:6px}}
    .fp-value{{font-family:monospace;font-size:16px;color:#111;
               letter-spacing:.15em;font-weight:700}}
    .fp-note{{font-size:11px;color:#9ca3af;margin-top:6px}}
    .section-label{{font-size:11px;color:#9ca3af;text-transform:uppercase;
                    letter-spacing:.06em;margin-bottom:10px}}
    table{{width:100%;border-collapse:collapse;border:1px solid #f0f0f0;
           border-radius:8px;overflow:hidden}}
    th{{background:#f9fafb;padding:10px 16px;font-size:11px;color:#9ca3af;
        text-transform:uppercase;letter-spacing:.06em;text-align:left;
        font-weight:600}}
    th:last-child{{text-align:right}}
    .badge{{display:inline-block;background:#f0fdf4;color:#16a34a;
            border:1px solid #bbf7d0;border-radius:20px;font-size:11px;
            padding:3px 10px;font-weight:600}}
    .readonly{{background:#fffbeb;border:1px solid #fde68a;border-radius:8px;
               padding:12px 14px;font-size:12px;color:#92400e}}
    .meta{{font-size:12px;color:#9ca3af}}
    .meta span{{color:#374151;font-weight:500}}
  </style>
</head>
<body>
  <div class="card">
    <div class="header">
      <h1>筛选规则公示页</h1>
      <p>腾讯 · {job_label} · 2026届秋招 · 智筛 AI 提供技术支持</p>
    </div>
    <div class="body">
      <div class="fp-box">
        <div class="fp-label">规则指纹（Rule Hash）</div>
        <div class="fp-value">{fp}</div>
        <div class="fp-note">
          候选人可将此指纹与投递确认邮件中的指纹对比，一致则表示规则未被修改。
        </div>
      </div>
      <div>
        <div class="section-label">评估维度与权重</div>
        <table>
          <thead><tr><th>维度</th><th>权重</th></tr></thead>
          <tbody>{rows}</tbody>
        </table>
      </div>
      <div class="meta">
        锁定时间：<span>{locked_at}</span><br/>
        状态：<span class="badge">已锁定 · 不可修改</span>
      </div>
      <div class="readonly">
        ⚠ 本页面为只读公示，规则自锁定后不可更改。
        如对评估结果有异议，请通过候选人系统提交申诉。
      </div>
    </div>
  </div>
</body>
</html>"""
