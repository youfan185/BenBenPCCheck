import json
from datetime import datetime

from config import DATA_DIR
from core.product_insights import classify_process, classify_startup


USAGE_DIR = DATA_DIR / "usage"
USAGE_FILE = USAGE_DIR / "software_usage.json"


def update_software_usage(process_rows: list[dict], scan_time: str | None = None) -> dict:
    USAGE_DIR.mkdir(parents=True, exist_ok=True)
    usage = _load_usage()
    now = scan_time or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for process in process_rows:
        raw_name = process.get("name") or "unknown"
        key = raw_name.lower()
        memory = float(process.get("memory_mb") or 0)
        previous = usage.get(key, {})
        run_count = int(previous.get("run_count", 0)) + 1
        total_memory = float(previous.get("total_memory_mb", 0)) + memory
        usage[key] = {
            "display_name": _display_name(raw_name),
            "process_name": raw_name,
            "run_count": run_count,
            "last_seen": now,
            "max_memory_mb": max(float(previous.get("max_memory_mb", 0)), memory),
            "avg_memory_mb": round(total_memory / run_count, 1),
            "total_memory_mb": round(total_memory, 1),
            "category": classify_process(process),
        }
    USAGE_FILE.write_text(json.dumps(usage, ensure_ascii=False, indent=2), encoding="utf-8")
    return usage


def build_user_software_profile(
    process_rows: list[dict],
    installed: list[dict],
    startup_items: list[dict],
    usage: dict,
    limit: int = 12,
) -> list[dict]:
    candidates: dict[str, dict] = {}
    for process in process_rows:
        name = _display_name(process.get("name", ""))
        if not name:
            continue
        item = candidates.setdefault(name.lower(), _base_profile(name))
        item["sources"].add("正在运行")
        item["score"] += 40 + min(10, int(float(process.get("memory_mb") or 0) / 500))
        item["category"] = classify_process(process)
        item["max_memory_mb"] = max(float(item.get("max_memory_mb", 0)), float(process.get("memory_mb") or 0))
        item["evidence"].append(f"{process.get('name')} 正在运行")

    for software in installed:
        matched = _known_app_name(software.get("name", ""))
        if not matched:
            continue
        item = candidates.setdefault(matched.lower(), _base_profile(matched))
        item["sources"].add("已安装")
        item["score"] += 12
        item["publisher"] = software.get("publisher", "")
        item["evidence"].append("已安装")

    for startup in startup_items:
        matched = _known_app_name(f"{startup.get('name', '')} {startup.get('path', '')}") or _display_name(startup.get("name", ""))
        if not matched:
            continue
        item = candidates.setdefault(matched.lower(), _base_profile(matched))
        item["sources"].add("开机自启动")
        item["score"] += 20
        item["category"] = classify_startup(startup)
        item["evidence"].append("开机自启动")

    for stored in usage.values():
        name = _known_app_name(stored.get("display_name", "")) or stored.get("display_name", "")
        if not name:
            continue
        item = candidates.setdefault(name.lower(), _base_profile(name))
        run_count = int(stored.get("run_count", 0))
        item["sources"].add("历史扫描")
        item["score"] += min(36, run_count * 3)
        item["last_seen"] = stored.get("last_seen", "")
        item["category"] = stored.get("category", item.get("category", "普通软件"))
        item["max_memory_mb"] = max(float(item.get("max_memory_mb", 0)), float(stored.get("max_memory_mb", 0)))
        item["evidence"].append(f"历史扫描出现 {run_count} 次")

    rows = []
    for item in candidates.values():
        item["common_score"] = max(0, min(100, int(item.pop("score"))))
        item["usage_score"] = item["common_score"]
        item["sources"] = sorted(item["sources"])
        item["evidence"] = list(dict.fromkeys(item["evidence"]))[:4]
        rows.append(item)
    rows.sort(key=lambda item: item["common_score"], reverse=True)
    return rows[:limit]


def _load_usage() -> dict:
    if not USAGE_FILE.exists():
        return {}
    try:
        return json.loads(USAGE_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _base_profile(name: str) -> dict:
    return {
        "name": name,
        "category": "普通软件",
        "common_score": 0,
        "score": 0,
        "sources": set(),
        "evidence": [],
        "last_seen": "",
        "publisher": "",
        "max_memory_mb": 0,
    }


def _display_name(process_name: str) -> str:
    name = (process_name or "").strip()
    if not name:
        return ""
    lower = name.lower().removesuffix(".exe")
    return _known_app_name(lower) or lower[:1].upper() + lower[1:]


def _known_app_name(text: str) -> str:
    lower = text.lower()
    mapping = [
        ("photoshop", "Photoshop"),
        ("illustrator", "Illustrator"),
        ("coreldraw", "CorelDRAW"),
        ("premiere", "Premiere Pro"),
        ("afterfx", "After Effects"),
        ("blender", "Blender"),
        ("c4d", "Cinema 4D"),
        ("pycharm", "PyCharm"),
        ("cursor", "Cursor"),
        ("code.exe", "VS Code"),
        ("visual studio code", "VS Code"),
        ("chrome", "Chrome"),
        ("msedge", "Edge"),
        ("edge", "Edge"),
        ("wechat", "微信"),
        ("weixin", "微信"),
        ("qq", "QQ"),
        ("tim", "TIM"),
        ("baidunetdisk", "百度网盘"),
        ("onedrive", "OneDrive"),
        ("bambu", "Bambu Studio"),
        ("jianying", "剪映"),
        ("capcut", "剪映"),
    ]
    for keyword, name in mapping:
        if keyword in lower:
            return name
    return ""
