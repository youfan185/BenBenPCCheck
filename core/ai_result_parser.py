import json


def strip_code_fence(text: str) -> str:
    clean = (text or "").strip()
    if clean.startswith("```"):
        clean = clean.replace("```json", "").replace("```JSON", "").replace("```", "").strip()
    return clean


def default_ai_result(error_message: str = "") -> dict:
    return {
        "overall": {"score": 0, "status": "AI 分析失败", "summary": error_message or "本次未获得 AI 分析结果，已使用本地规则兜底。", "top_summary": ""},
        "hardware_market_review": {"score": 0, "status": "未知", "summary": "AI 未返回硬件市场分析。", "items": []},
        "software_smoothness_review": {"score": 0, "status": "未知", "summary": "AI 未返回软件流畅度分析。", "smooth_apps": [], "pressure_apps": [], "bottlenecks": []},
        "system_review": {"score": 0, "status": "未知", "summary": "AI 未返回系统可用性分析。", "issues": [], "top_5_tasks": [], "do_not_touch": []},
        "brief_report": {"title": "简版报告", "issues_by_impact": []},
        "optimization_guide": {"title": "优化引导", "steps": []},
    }


def normalize_ai_result(data: dict) -> dict:
    data = _normalize_result(data)
    base = default_ai_result()
    for key in base:
        if isinstance(data.get(key), dict):
            base[key].update(data[key])
    base["hardware_review"] = base["hardware_market_review"]
    base["software_fit_review"] = base["software_smoothness_review"]
    return base


def parse_ai_text(text: str) -> dict:
    try:
        data = json.loads(strip_code_fence(text))
        if not isinstance(data, dict):
            return default_ai_result("AI 返回不是 JSON 对象。")
        return normalize_ai_result(data)
    except Exception as exc:
        return default_ai_result(f"AI JSON 解析失败：{exc}")


def parse_ai_result(result: dict, report: dict) -> dict:
    if not result.get("ok"):
        return build_local_ai_result(report, result.get("error", "AI 分析失败"))
    data = result.get("data") or {}
    if not isinstance(data, dict):
        return build_local_ai_result(report, "AI 返回格式不正确")
    fallback = build_local_ai_result(report)
    return _normalize_result(_merge_result(fallback, data, source="ai"))


def build_local_ai_result(report: dict, error: str = "") -> dict:
    scores = report.get("scores", {})
    hardware = scores.get("hardware_score", {})
    software = scores.get("software_fit_score", {})
    system = scores.get("system_usability_score", {})
    total = int(scores.get("total_score", report.get("score", {}).get("total_score", 0)) or 0)
    pressure = software.get("multi_app_pressure", [])
    tasks = _fallback_tasks(report, software, system)
    result = {
        "source": "local_fallback" if error else "local",
        "error": error,
        "overall": {
            "score": total,
            "status": _overall_status(total, software, system),
            "summary": _overall_summary(hardware, software, system),
            "emotion": emotion_key(total),
        },
        "hardware_market_review": {
            "score": hardware.get("score", 0),
            "status": hardware.get("status", "等待扫描"),
            "emotion": emotion_key(hardware.get("score", 0)),
            "summary": hardware.get("summary", ""),
            "items": hardware.get("items", []),
        },
        "software_smoothness_review": {
            "score": software.get("score", 0),
            "status": _software_status(software),
            "emotion": emotion_key(software.get("score", 0)),
            "summary": _software_summary(software),
            "smooth_apps": software.get("easy_to_run", []),
            "pressure_apps": _pressure_apps(report, software),
            "bottlenecks": [b for b in software.get("bottlenecks", []) if b != "暂未发现明显硬件短板"],
        },
        "system_review": {
            "score": system.get("score", 0),
            "status": system.get("status", "等待扫描"),
            "emotion": emotion_key(system.get("score", 0)),
            "summary": system.get("summary", ""),
            "issues": _system_issues(system),
            "top_5_tasks": tasks,
            "do_not_touch": system.get("do_not_touch", []),
        },
        "brief_report": {
            "title": "简版报告",
            "content": _brief_report(hardware, software, system, tasks),
        },
        "optimization_guide": {
            "title": "优化引导",
            "steps": tasks,
        },
    }
    result["hardware_review"] = result["hardware_market_review"]
    result["software_fit_review"] = result["software_smoothness_review"]
    return result


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


def apply_ai_result(report: dict, ai_result: dict) -> dict:
    report["ai_result"] = ai_result
    report["brief_report"] = ai_result.get("brief_report", {})
    report["optimization_guide"] = ai_result.get("optimization_guide", {})
    return report


def _merge_result(fallback: dict, data: dict, source: str) -> dict:
    data = _normalize_result(data)
    merged = {**fallback, **data}
    merged["source"] = source
    for key in ["overall", "hardware_market_review", "software_smoothness_review", "system_review", "brief_report", "optimization_guide"]:
        if isinstance(fallback.get(key), dict):
            merged[key] = {**fallback.get(key, {}), **(data.get(key) if isinstance(data.get(key), dict) else {})}
    merged["hardware_review"] = merged.get("hardware_market_review", {})
    merged["software_fit_review"] = merged.get("software_smoothness_review", {})
    return merged


def _normalize_result(data: dict) -> dict:
    if not isinstance(data, dict):
        return {}
    if "hardware_market_review" not in data and "hardware_review" in data:
        data["hardware_market_review"] = data["hardware_review"]
    if "software_smoothness_review" not in data and "software_fit_review" in data:
        data["software_smoothness_review"] = data["software_fit_review"]
    return data


def _overall_status(total: int, software: dict, system: dict) -> str:
    if total >= 85:
        return "良好"
    if software.get("multi_app_pressure"):
        return "良好，但后台负担偏重"
    if system.get("score", 100) < 75:
        return "有点累"
    return "需要关注"


def _overall_summary(hardware: dict, software: dict, system: dict) -> str:
    if software.get("multi_app_pressure"):
        return f"硬件属于{hardware.get('status', '可用')}，常用软件能跑，主要问题是多软件后台叠加压力。"
    return f"{hardware.get('summary', '')}{software.get('summary', '')}{system.get('summary', '')}"


def _software_status(software: dict) -> str:
    score = int(software.get("score", 0) or 0)
    has_hardware_bottleneck = any(b != "暂未发现明显硬件短板" for b in software.get("bottlenecks", []))
    if score >= 90:
        return "运行流畅"
    if score >= 80 and not has_hardware_bottleneck:
        return "常用软件能跑，多开时有压力"
    if score >= 70 and not has_hardware_bottleneck:
        return "常用软件基本能跑，重度多开需注意"
    if score >= 60:
        return "部分重软件场景会吃力"
    return "常用软件已明显超出当前硬件能力"


def _software_summary(software: dict) -> str:
    bottlenecks = [b for b in software.get("bottlenecks", []) if b != "暂未发现明显硬件短板"]
    categories = " / ".join(software.get("detected_categories", [])[:6])
    if not bottlenecks:
        pressure = " ".join(software.get("multi_app_pressure", [])[:2])
        return f"当前常用软件都能跑，{categories or '已识别的软件'} 没有明显硬件短板。主要问题是多软件同时打开时后台累计占用。{pressure}".strip()
    return software.get("summary", "")


def _system_issues(system: dict) -> list[dict]:
    return [{"title": item, "risk": "中", "action": "打开详情核实后再处理。"} for item in system.get("priority_items", [])]


def _fallback_tasks(report: dict, software: dict, system: dict) -> list[dict]:
    tasks = []
    for text in software.get("multi_app_pressure", [])[:2]:
        tasks.append({"title": "检查多软件后台叠加压力", "reason": text, "benefit": "减少多任务切换和内存压力", "risk": "低", "auto_supported": False, "action": "关闭不用的标签页、小程序窗口和后台同步。"})
    for text in system.get("priority_items", []):
        risk = "中" if "可疑" in text or "核实" in text else "低"
        tasks.append({"title": text, "reason": "本地扫描把它排在较高优先级。", "benefit": "改善系统可用性", "risk": risk, "auto_supported": False, "action": "在扫描详情中确认来源后处理。"})
    if not tasks:
        tasks.append({"title": "保持当前使用习惯并定期复查", "reason": "暂未发现高优先级问题。", "benefit": "避免误删误关", "risk": "低", "auto_supported": False, "action": "一周后或明显卡顿时重新扫描。"})
    return tasks[:5]


def _brief_report(hardware: dict, software: dict, system: dict, tasks: list[dict]) -> list[str]:
    return [
        f"综合结论：硬件市场水平 {hardware.get('status', '')}，软件运行流畅度 {software.get('status', '')}，系统 {system.get('status', '')}。",
        f"硬件市场水平：{hardware.get('summary', '')}",
        f"软件运行是否流畅：{_software_status(software)}。{_software_summary(software)}",
        f"系统是否拖后腿：{system.get('summary', '')}",
        "影响程度从高到低的问题：" + "；".join(task.get("title", "") for task in tasks[:5]),
        "不要乱动：" + "、".join(system.get("do_not_touch", [])),
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
