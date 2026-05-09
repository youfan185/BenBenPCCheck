import json


LEVELS = ("很好", "不错", "一般", "较差", "很差")


def level_from_score(score: int | float) -> str:
    score = int(score or 0)
    if score >= 85:
        return "很好"
    if score >= 70:
        return "不错"
    if score >= 55:
        return "一般"
    if score >= 40:
        return "较差"
    return "很差"


def emotion_key(score: int | float) -> str:
    score = int(score or 0)
    if score >= 90:
        return "90-100"
    if score >= 75:
        return "75-89"
    if score >= 60:
        return "60-74"
    if score >= 40:
        return "40-59"
    return "0-39"


def strip_code_fence(text: str) -> str:
    clean = (text or "").strip()
    if clean.startswith("```"):
        clean = clean.replace("```json", "").replace("```JSON", "").replace("```", "").strip()
    return clean


def default_ai_result(error_message: str = "") -> dict:
    return build_empty_result("AI 分析失败", error_message or "本次未获得 AI 分析结果，已使用本地规则兜底。")


def build_empty_result(status: str, summary: str) -> dict:
    return {
        "source": "local_fallback",
        "error": summary,
        "overall": {"score": 0, "level": "很差", "status": status, "summary": summary, "emotion": "0-39"},
        "hardware_market_review": {"score": 0, "level": "很差", "status": "未知", "summary": "AI 未返回硬件市场分析。", "items": []},
        "software_smoothness_review": {"score": 0, "level": "很差", "status": "未知", "summary": "AI 未返回软件流畅度分析。", "pressure_apps": []},
        "system_review": {"score": 0, "level": "很差", "status": "未知", "summary": "AI 未返回系统可用性分析。", "issues": []},
        "brief_report": {"title": "简版报告", "issues_by_impact": []},
        "optimization_guide": {"title": "优化引导", "steps": []},
    }


def parse_ai_text(text: str) -> dict:
    try:
        data = json.loads(strip_code_fence(text))
    except Exception as exc:
        raise ValueError(f"AI 返回非 JSON 或 JSON 解析失败：{exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("AI 返回不是 JSON 对象。")
    return normalize_ai_result(data, strict=True)


def normalize_ai_result(data: dict, strict: bool = False) -> dict:
    data = _normalize_aliases(dict(data or {}))
    required = ("overall", "hardware_market_review", "software_smoothness_review", "system_review")
    missing = [key for key in required if not isinstance(data.get(key), dict)]
    if strict and missing:
        raise ValueError("AI JSON 缺少必要字段：" + "、".join(missing))

    base = build_empty_result("", "")
    base["source"] = data.get("source", "ai")
    base["error"] = data.get("error", "")
    for key in ("overall", "hardware_market_review", "software_smoothness_review", "system_review", "brief_report", "optimization_guide"):
        if isinstance(data.get(key), dict):
            base[key].update(data[key])

    for key in ("overall", "hardware_market_review", "software_smoothness_review", "system_review"):
        _normalize_level(base[key], strict=strict, section_name=key)

    for item in base["hardware_market_review"].get("items", []) or []:
        if isinstance(item, dict):
            _normalize_level(item, strict=strict, section_name=f"hardware item {item.get('name', '')}")
            item["bar_percent"] = max(0, min(100, int(item.get("bar_percent", item.get("score", 0)) or 0)))

    base["hardware_review"] = base["hardware_market_review"]
    base["software_fit_review"] = base["software_smoothness_review"]
    return base


def build_local_ai_result(report: dict, error: str = "") -> dict:
    scores = report.get("scores", {})
    hardware = scores.get("hardware_market_score") or scores.get("hardware_score", {})
    software = scores.get("software_smoothness_score") or scores.get("software_fit_score", {})
    system = scores.get("system_usability_score", {})
    total = int(scores.get("total_score", report.get("score", {}).get("total_score", 0)) or 0)
    tasks = _fallback_tasks(report, software, system)

    result = {
        "source": "local_fallback" if error else "local",
        "error": error,
        "overall": {
            "score": total,
            "level": level_from_score(total),
            "status": _overall_status(total, software, system),
            "summary": _overall_summary(hardware, software, system),
            "emotion": emotion_key(total),
        },
        "hardware_market_review": {
            "score": hardware.get("score", 0),
            "level": level_from_score(hardware.get("score", 0)),
            "status": hardware.get("status", hardware.get("level", "等待扫描")),
            "summary": hardware.get("summary", ""),
            "items": _hardware_items(hardware),
            "emotion": emotion_key(hardware.get("score", 0)),
        },
        "software_smoothness_review": {
            "score": software.get("score", 0),
            "level": level_from_score(software.get("score", 0)),
            "status": _software_status(software),
            "summary": _software_summary(software),
            "pressure_apps": _pressure_apps(report, software),
            "emotion": emotion_key(software.get("score", 0)),
        },
        "system_review": {
            "score": system.get("score", 0),
            "level": level_from_score(system.get("score", 0)),
            "status": system.get("status", "等待扫描"),
            "summary": system.get("summary", ""),
            "issues": _system_issues(system),
            "top_5_tasks": tasks,
            "emotion": emotion_key(system.get("score", 0)),
        },
        "brief_report": {"title": "简版报告", "content": _brief_report(hardware, software, system, tasks)},
        "optimization_guide": {"title": "优化引导", "steps": tasks},
    }
    result["hardware_review"] = result["hardware_market_review"]
    result["software_fit_review"] = result["software_smoothness_review"]
    return result


def apply_ai_result(report: dict, ai_result: dict) -> dict:
    report["ai_result"] = ai_result
    report["brief_report"] = ai_result.get("brief_report", {})
    report["optimization_guide"] = ai_result.get("optimization_guide", {})
    return report


def _normalize_aliases(data: dict) -> dict:
    if "hardware_market_review" not in data and "hardware_review" in data:
        data["hardware_market_review"] = data["hardware_review"]
    if "software_smoothness_review" not in data and "software_fit_review" in data:
        data["software_smoothness_review"] = data["software_fit_review"]
    return data


def _normalize_level(data: dict, strict: bool, section_name: str = "") -> None:
    score = int(data.get("score", 0) or 0)
    level = data.get("level")
    if level not in LEVELS:
        if strict and level:
            raise ValueError(f"{section_name} 的 level 不合法：{level}")
        data["level"] = level_from_score(score)
    data["emotion"] = data.get("emotion") or emotion_key(score)


def _overall_status(total: int, software: dict, system: dict) -> str:
    if total >= 85:
        return "很好"
    if software.get("multi_app_pressure"):
        return "不错，但后台负担偏重"
    if system.get("score", 100) < 70:
        return "一般，系统环境需要整理"
    return level_from_score(total)


def _overall_summary(hardware: dict, software: dict, system: dict) -> str:
    if software.get("multi_app_pressure"):
        return f"硬件属于{hardware.get('status', '可用')}，常用软件能跑，主要问题是多软件后台叠加压力。"
    return " ".join(x for x in [hardware.get("summary", ""), software.get("summary", ""), system.get("summary", "")] if x).strip()


def _software_status(software: dict) -> str:
    score = int(software.get("score", 0) or 0)
    bottlenecks = [b for b in software.get("bottlenecks", []) if "暂未发现" not in str(b)]
    if score >= 85:
        return "运行流畅，重度多开需注意"
    if score >= 70 and not bottlenecks:
        return "常用软件能跑，多开时有压力"
    if score >= 55:
        return "一般，多开和重软件需要控制"
    return "较差，当前使用压力明显"


def _software_summary(software: dict) -> str:
    pressure = " ".join(software.get("multi_app_pressure", [])[:2])
    if pressure:
        return f"当前常用软件基本能流畅运行，主要压力来自多软件同时打开后的后台累计占用。{pressure}".strip()
    return software.get("summary", "当前常用软件未发现明显硬件短板。")


def _hardware_items(hardware: dict) -> list[dict]:
    rows = []
    for item in hardware.get("items", []) or []:
        score = int(item.get("score", 0) or 0)
        max_score = int(item.get("max_score", 100) or 100)
        percent = int(score / max_score * 100) if max_score else score
        rows.append({
            "name": item.get("name", ""),
            "score": score,
            "level": item.get("level") if item.get("level") in LEVELS else level_from_score(percent),
            "market_position": item.get("market_position") or item.get("status") or level_from_score(percent),
            "bar_percent": max(0, min(100, percent)),
            "reason": item.get("reason", item.get("detail", "")),
            "max_score": max_score,
        })
    return rows


def _system_issues(system: dict) -> list[dict]:
    return [{"title": item, "risk": "中", "action": "打开详情核实后再处理。"} for item in system.get("priority_items", [])]


def _fallback_tasks(report: dict, software: dict, system: dict) -> list[dict]:
    tasks = []
    for text in software.get("multi_app_pressure", [])[:2]:
        tasks.append({"title": "检查多软件后台叠加压力", "reason": text, "benefit": "减少多任务切换和内存压力", "risk": "低", "auto_supported": False, "action": "关闭不用的标签页、小程序窗口和后台同步。"})
    for text in system.get("priority_items", [])[:3]:
        tasks.append({"title": text, "reason": "本地扫描把它排在较高优先级。", "benefit": "改善系统可用性", "risk": "中", "auto_supported": False, "action": "在扫描详情中确认来源后处理。"})
    if not tasks:
        tasks.append({"title": "保持当前使用习惯并定期复查", "reason": "暂未发现高优先级问题。", "benefit": "避免误删误关", "risk": "低", "auto_supported": False, "action": "一周后或明显卡顿时重新体检。"})
    return tasks[:5]


def _brief_report(hardware: dict, software: dict, system: dict, tasks: list[dict]) -> list[str]:
    return [
        f"综合结论：硬件市场水平 {hardware.get('status', '')}，软件运行流畅度 {_software_status(software)}，系统状态 {system.get('status', '')}。",
        f"硬件市场水平：{hardware.get('summary', '')}",
        f"软件运行流畅度：{_software_summary(software)}",
        f"系统可用性：{system.get('summary', '')}",
        "建议优先处理：" + "；".join(task.get("title", "") for task in tasks[:3]),
    ]


def _pressure_apps(report: dict, software: dict) -> list[dict]:
    groups = software.get("process_group_attention") or report.get("software", {}).get("process_groups", [])[:5]
    rows = []
    for group in groups[:5]:
        rows.append({
            "name": group.get("name", ""),
            "level": group.get("pressure_level", "中"),
            "memory_mb": group.get("memory_mb", 0),
            "process_count": group.get("process_count", 0),
        })
    return rows
