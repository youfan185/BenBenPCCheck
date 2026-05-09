import json


SYSTEM_PROMPT = """你是 Windows 电脑诊断专家。
只根据用户提供的扫描 JSON 输出诊断，不要猜测不存在的数据。
必须返回 JSON，不要输出 Markdown。

顶层字段必须包含：
overall、hardware_market_review、software_smoothness_review、system_review、brief_report、optimization_guide。

所有 level 字段只能使用：很好、不错、一般、较差、很差。
分数映射：85-100 很好，70-84 不错，55-69 一般，40-54 较差，0-39 很差。

硬件市场水平只看硬件在当前市场中的档次，不要把当前 CPU 占用、内存占用、后台进程算进硬件市场分。
硬件单项必须包含 name、score、level、market_position、bar_percent、reason。
软件运行流畅度判断当前常用软件是否流畅；没有明显硬件短板时，不要输出“部分软件吃力”。
系统可用性不要夸大 C 盘、临时文件、普通启动项问题。
"""


def build_ai_input(report: dict) -> dict:
    scores = report.get("scores", {})
    software = report.get("software", {})
    storage = report.get("storage", {})
    system = report.get("system", {})
    hardware = report.get("hardware", {})
    return {
        "scan_time": report.get("scan_time"),
        "computer": _pick(report.get("computer", {}), ["hostname", "os", "os_version", "machine", "processor"]),
        "hardware": {
            "cpu": _pick(hardware.get("cpu", {}), ["name", "cores", "threads", "current_usage_percent"]),
            "memory": _pick(hardware.get("memory", {}), ["total_gb", "available_gb", "usage_percent"]),
            "gpu": [_pick(x, ["name", "memory_gb", "driver_version"]) for x in _as_list(hardware.get("gpu"))[:3]],
            "disks": [_pick(x, ["model", "health", "size_gb", "interface"]) for x in _as_list(hardware.get("disks"))[:4]],
        },
        "scores": {
            "total_score": scores.get("total_score"),
            "hardware_market_score": _score_summary(scores.get("hardware_market_score") or scores.get("hardware_score", {})),
            "software_smoothness_score": _score_summary(scores.get("software_smoothness_score") or scores.get("software_fit_score", {})),
            "system_usability_score": _score_summary(scores.get("system_usability_score", {})),
        },
        "software": {
            "categories": software.get("software_categories", [])[:8],
            "process_groups": [_pick(x, ["name", "category", "memory_mb", "process_count", "pressure_level", "explain"]) for x in _as_list(software.get("process_groups"))[:8]],
            "requirement_match": [_pick(x, ["category", "status", "fit_score", "weak_hardware", "bottleneck"]) for x in _as_list(software.get("software_requirement_match"))[:8]],
        },
        "storage": {
            "partitions": [_pick(x, ["drive", "total_gb", "free_gb", "usage_percent"]) for x in _as_list(storage.get("partitions"))[:6]],
            "large_folders": [_pick(x, ["name", "category", "size_gb"]) for x in _as_list(storage.get("large_folders"))[:8]],
            "disk_health": [_pick(x, ["model", "health", "temperature", "status"]) for x in _as_list(storage.get("disk_health"))[:4]],
        },
        "system": {
            "startup_count": len(system.get("startup_items", [])),
            "settings": _pick(system.get("settings", {}), ["summary", "items"]),
            "events": _pick(system.get("system_events", {}), ["summary", "risk_items"]),
        },
        "ai_input_summary": report.get("ai_input_summary", {}),
    }


def build_prompts(report: dict) -> tuple[str, str]:
    user_prompt = (
        "请根据下面 JSON 输出电脑诊断。只使用 JSON 中已有数据，不要脑补。"
        "必须返回固定结构 JSON，不要返回 Markdown。\n\n"
    )
    user_prompt += json.dumps(build_ai_input(report), ensure_ascii=False, separators=(",", ":"))
    return SYSTEM_PROMPT, user_prompt


def build_ai_prompt(report: dict) -> str:
    system_prompt, user_prompt = build_prompts(report)
    return system_prompt + "\n\n" + user_prompt


def _pick(data: dict, keys: list[str]) -> dict:
    if not isinstance(data, dict):
        return {}
    return {key: data.get(key) for key in keys if key in data and data.get(key) not in (None, "", [], {})}


def _as_list(value) -> list:
    return value if isinstance(value, list) else []


def _score_summary(data: dict) -> dict:
    if not isinstance(data, dict):
        return {}
    result = _pick(data, ["score", "level", "status", "summary", "bottlenecks", "multi_app_pressure", "priority_items"])
    if data.get("items"):
        result["items"] = [
            _pick(x, ["name", "score", "max_score", "level", "status", "market_position", "bar_percent", "reason", "detail"])
            for x in _as_list(data.get("items"))[:6]
        ]
    return result
