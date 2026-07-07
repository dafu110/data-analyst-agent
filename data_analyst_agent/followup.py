from __future__ import annotations

from typing import Any


ITERATION_KEYWORDS = {"按", "筛选", "只看", "重新", "再分析", "分组", "排除", "过滤", "对比", "drill", "filter", "group"}
METRIC_KEYWORDS = {"指标", "口径", "公式", "怎么算", "metric", "formula"}


QUALITY_KEYWORDS = {"质量", "缺失", "重复", "异常", "空值", "完整", "quality", "missing", "duplicate"}
TREND_KEYWORDS = {"趋势", "增长", "下降", "变化", "时间", "月份", "同比", "环比", "trend", "change"}
FIELD_KEYWORDS = {"字段", "列", "指标", "维度", "含义", "业务字段", "column", "field", "metric"}
ACTION_KEYWORDS = {"建议", "下一步", "怎么做", "优化", "行动", "recommend", "next"}
WHY_KEYWORDS = {"为什么", "原因", "驱动", "影响", "归因", "why", "reason"}


def answer_followup(result: dict[str, Any], report_markdown: str, question: str) -> dict[str, Any]:
    clean_question = question.strip()
    if not clean_question:
        raise ValueError("追问内容不能为空。")
    if not result:
        raise ValueError("任务结果不可用，无法追问。")

    lowered = clean_question.lower()
    sections: list[str] = []
    citations: list[str] = []

    profile = result.get("profile") if isinstance(result.get("profile"), dict) else {}
    insights = result.get("insights") if isinstance(result.get("insights"), list) else []
    semantic_roles = result.get("semantic_roles") if isinstance(result.get("semantic_roles"), list) else []
    time_series = result.get("time_series") if isinstance(result.get("time_series"), list) else []
    charts = result.get("chart_specs") if isinstance(result.get("chart_specs"), list) else []
    action_items = result.get("action_items") if isinstance(result.get("action_items"), list) else []
    metric_definitions = result.get("metric_definitions") if isinstance(result.get("metric_definitions"), list) else []

    matched_insights = _match_insights(insights, clean_question)
    if matched_insights:
        sections.append(_format_insights(matched_insights))
        citations.extend(_insight_citations(matched_insights))

    if _has_any(lowered, QUALITY_KEYWORDS):
        sections.append(_format_quality(profile))
        citations.append("数据画像：质量评分、缺失值、重复行和字段可用性")

    if _has_any(lowered, TREND_KEYWORDS) and time_series:
        sections.append(_format_time_series(time_series))
        citations.append("时间序列摘要")

    if _has_any(lowered, FIELD_KEYWORDS) and semantic_roles:
        sections.append(_format_semantic_roles(semantic_roles))
        citations.append("业务字段识别")

    if _has_any(lowered, ACTION_KEYWORDS | WHY_KEYWORDS):
        recommendations = _collect_recommendations(insights)
        if recommendations:
            sections.append("可执行建议：" + "；".join(recommendations[:4]) + "。")
            citations.append("结构化 insight 的 recommendation 字段")

    if _has_any(lowered, METRIC_KEYWORDS) and metric_definitions:
        sections.append(_format_metric_definitions(metric_definitions))
        citations.append("指标口径")

    if _has_any(lowered, ACTION_KEYWORDS | WHY_KEYWORDS) and action_items:
        sections.append(_format_action_items(action_items))
        citations.append("行动清单")

    followup_actions = _build_followup_actions(clean_question, result)
    if followup_actions:
        sections.append(_format_followup_actions(followup_actions))
        citations.append("二次分析建议")

    if not sections:
        sections.append(_format_overview(profile, insights, charts))
        citations.append("报告总览和结构化分析结果")

    answer = "\n\n".join(section for section in sections if section).strip()
    return {
        "question": clean_question,
        "answer": answer,
        "confidence": _confidence(matched_insights, report_markdown),
        "needs_review": len(matched_insights) == 0 and not _has_any(lowered, QUALITY_KEYWORDS | TREND_KEYWORDS | FIELD_KEYWORDS),
        "citations": list(dict.fromkeys(citations))[:6],
        "suggested_questions": suggest_followups(result),
        "followup_actions": followup_actions,
    }


def suggest_followups(result: dict[str, Any]) -> list[str]:
    if isinstance(result.get("suggested_questions"), list) and result["suggested_questions"]:
        return [str(question) for question in result["suggested_questions"][:5]]
    suggestions = [
        "这份数据最值得关注的 3 个结论是什么？",
        "数据质量有什么风险，是否需要人工复核？",
        "下一步应该优先做哪些业务动作？",
    ]
    if result.get("time_series"):
        suggestions.insert(1, "核心指标的趋势是增长还是下降？")
    if result.get("semantic_roles"):
        suggestions.append("哪些字段被识别成了关键业务指标？")
    return suggestions[:5]


def _has_any(text: str, keywords: set[str]) -> bool:
    return any(keyword.lower() in text for keyword in keywords)


def _match_insights(insights: list[Any], question: str) -> list[dict[str, Any]]:
    terms = [term for term in _tokenize(question) if len(term) >= 2]
    scored: list[tuple[int, dict[str, Any]]] = []
    for insight in insights:
        if not isinstance(insight, dict):
            continue
        haystack = " ".join(
            str(insight.get(key, ""))
            for key in ("title", "detail", "recommendation", "metric_value", "insight_type", "severity")
        )
        haystack += " " + " ".join(str(item) for item in insight.get("evidence", []) if isinstance(item, str))
        score = sum(1 for term in terms if term.lower() in haystack.lower())
        if score:
            scored.append((score, insight))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [insight for _, insight in scored[:4]]


def _tokenize(text: str) -> list[str]:
    normalized = "".join(character if character.isalnum() else " " for character in text)
    return [part.strip() for part in normalized.split() if part.strip()]


def _format_insights(insights: list[dict[str, Any]]) -> str:
    lines = ["和你问题最相关的发现："]
    for insight in insights:
        title = insight.get("title", "未命名发现")
        detail = insight.get("detail", "")
        metric = insight.get("metric_value")
        confidence = round(float(insight.get("confidence") or 0) * 100)
        suffix = f" 指标值：{metric}。" if metric else ""
        lines.append(f"- {title}：{detail}{suffix} 置信度约 {confidence}%。")
    return "\n".join(lines)


def _format_quality(profile: dict[str, Any]) -> str:
    quality_score = round(float(profile.get("quality_score") or 0) * 100)
    missing_values = profile.get("missing_values") if isinstance(profile.get("missing_values"), dict) else {}
    warnings = profile.get("warnings") if isinstance(profile.get("warnings"), list) else []
    missing_columns = [f"{column}={count}" for column, count in missing_values.items() if count]
    parts = [f"数据质量评分约 {quality_score}%。"]
    if missing_columns:
        parts.append("存在缺失值的字段：" + "，".join(missing_columns[:8]) + "。")
    if warnings:
        parts.append("质量提示：" + "；".join(str(item) for item in warnings[:4]) + "。")
    if not missing_columns and not warnings:
        parts.append("当前画像未发现明显缺失、重复或常量字段风险。")
    return "".join(parts)


def _format_time_series(time_series: list[Any]) -> str:
    lines = ["趋势摘要："]
    for item in time_series[:3]:
        if not isinstance(item, dict):
            continue
        metric = item.get("metric_column", "核心指标")
        first_period = item.get("first_period", "起点")
        last_period = item.get("last_period", "终点")
        change = item.get("percent_change")
        if change is None:
            change_text = f"绝对变化 {item.get('absolute_change', 0)}"
        else:
            change_text = f"变化 {float(change):.2f}%"
        lines.append(f"- {metric} 从 {first_period} 到 {last_period} 的{change_text}，峰值出现在 {item.get('peak_period', '未知')}。")
    return "\n".join(lines)


def _format_semantic_roles(roles: list[Any]) -> str:
    labels = []
    for role in roles[:8]:
        if isinstance(role, dict):
            labels.append(f"{role.get('column')} -> {role.get('role')}（{round(float(role.get('confidence') or 0) * 100)}%）")
    return "关键业务字段识别：" + "；".join(labels) + "。"


def _collect_recommendations(insights: list[Any]) -> list[str]:
    recommendations = []
    for insight in insights:
        if isinstance(insight, dict) and insight.get("recommendation"):
            recommendations.append(str(insight["recommendation"]))
    return recommendations


def _build_followup_actions(question: str, result: dict[str, Any]) -> list[dict[str, str]]:
    lowered = question.lower()
    if not _has_any(lowered, ITERATION_KEYWORDS):
        return []
    roles = result.get("semantic_roles") if isinstance(result.get("semantic_roles"), list) else []
    columns = [str(role.get("column")) for role in roles if isinstance(role, dict) and role.get("column")]
    matched_columns = [column for column in columns if column.lower() in lowered or column in question]
    if not matched_columns and columns:
        matched_columns = columns[:2]
    return [
        {
            "type": "rerun_analysis",
            "title": "可发起二次分析",
            "detail": f"建议基于字段 {', '.join(matched_columns) if matched_columns else '关键维度'} 重新分组、筛选或对比，并生成一份新报告。",
            "suggested_goal": question,
        }
    ]


def _format_action_items(items: list[Any]) -> str:
    lines = ["建议优先执行这些动作："]
    for item in items[:5]:
        if not isinstance(item, dict):
            continue
        priority = item.get("priority", "medium")
        title = item.get("title", "行动项")
        detail = item.get("detail", "")
        next_step = item.get("next_step")
        suffix = f" 下一步：{next_step}" if next_step else ""
        lines.append(f"- [{priority}] {title}：{detail}{suffix}")
    return "\n".join(lines)


def _format_metric_definitions(metrics: list[Any]) -> str:
    lines = ["当前可用或待补充的指标口径："]
    for item in metrics[:8]:
        if not isinstance(item, dict):
            continue
        status = "可计算" if item.get("available") else "需补充字段"
        columns = "、".join(str(column) for column in item.get("columns", []))
        columns_text = f"，字段：{columns}" if columns else ""
        lines.append(f"- {item.get('name')}（{status}）：{item.get('formula')}{columns_text}。{item.get('reason', '')}")
    return "\n".join(lines)


def _format_followup_actions(actions: list[dict[str, str]]) -> str:
    lines = ["这类问题适合发起二次分析："]
    for action in actions[:3]:
        lines.append(f"- {action['title']}：{action['detail']}")
    return "\n".join(lines)


def _format_overview(profile: dict[str, Any], insights: list[Any], charts: list[Any]) -> str:
    rows = profile.get("rows", "未知")
    columns = profile.get("columns", "未知")
    return (
        f"当前报告覆盖 {rows} 行、{columns} 个字段，"
        f"生成了 {len(insights)} 条结构化结论和 {len(charts)} 个图表建议。"
        "你的问题没有命中特定字段或结论，我建议改问某个字段、趋势、质量风险或下一步建议。"
    )


def _insight_citations(insights: list[dict[str, Any]]) -> list[str]:
    return [f"Insight：{insight.get('title', '未命名发现')}" for insight in insights]


def _confidence(matched_insights: list[dict[str, Any]], report_markdown: str) -> float:
    if matched_insights:
        values = [float(insight.get("confidence") or 0.7) for insight in matched_insights]
        return round(min(0.95, max(0.55, sum(values) / len(values))), 2)
    return 0.62 if report_markdown else 0.5
