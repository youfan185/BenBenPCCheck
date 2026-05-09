from core.hardware_rules import clamp_score


SOFTWARE_RULES = [
    ("办公", ("word", "wps", "excel", "pdf", "acrobat", "chrome", "edge", "browser"), {"memory_gb": 8, "cpu_threads": 4, "disk_free_gb": 10}),
    ("设计", ("photoshop", "illustrator", "coreldraw", "cdr"), {"memory_gb": 16, "cpu_threads": 6, "disk_free_gb": 40, "gpu_vram_gb": 2}),
    ("开发", ("pycharm", "cursor", "codex", "code", "vscode", "python", "git", "idea"), {"memory_gb": 16, "cpu_threads": 8, "disk_free_gb": 30}),
    ("剪辑", ("premiere", "afterfx", "media encoder", "jianying", "capcut", "剪映"), {"memory_gb": 32, "cpu_threads": 8, "disk_free_gb": 80, "gpu_vram_gb": 4}),
    ("3D", ("blender", "c4d", "cinema 4d", "bambu"), {"memory_gb": 32, "cpu_threads": 12, "disk_free_gb": 80, "gpu_vram_gb": 6}),
    ("聊天", ("wechat", "weixin", "微信", "qq", "tim", "wxwork", "企业微信"), {"memory_gb": 8, "cpu_threads": 4, "disk_free_gb": 20}),
    ("网盘同步", ("baidunetdisk", "onedrive", "ugreen", "quark", "夸克"), {"memory_gb": 8, "cpu_threads": 4, "disk_free_gb": 40}),
    ("电商", ("qianniu", "千牛", "aliworkbench", "alirender"), {"memory_gb": 16, "cpu_threads": 6, "disk_free_gb": 40}),
    ("游戏", ("wegame", "league", "lol", "delta force", "三角洲"), {"memory_gb": 16, "cpu_threads": 8, "disk_free_gb": 80, "gpu_vram_gb": 4}),
]


def classify_software_name(name: str) -> str:
    text = (name or "").lower()
    for category, keywords, _ in SOFTWARE_RULES:
        if any(keyword in text for keyword in keywords):
            return category
    return "普通软件"


def analyze_software_fit(report: dict) -> dict:
    profile = report.get("user_software_profile", [])
    process_groups = report.get("software", {}).get("process_groups") or report.get("process_groups", [])
    hardware = report.get("hardware", {})
    memory = hardware.get("memory", {})
    cpu = hardware.get("cpu", {})
    gpus = hardware.get("gpu", [])
    c_drive = next((d for d in report.get("disk_partitions", []) if str(d.get("drive", "")).upper().startswith("C:")), None)

    actual = {
        "memory_gb": float(memory.get("total_gb") or 0),
        "cpu_threads": float(cpu.get("logical_cores") or 0),
        "disk_free_gb": float(c_drive.get("free_gb") or 0) if c_drive else 0,
        "gpu_vram_gb": max((float(g.get("vram_gb") or 0) for g in gpus), default=0),
    }

    detected = _detected_categories(profile, process_groups)
    requirement_match = []
    score = 92
    bottlenecks = []
    easy = []
    pressure = []

    for category in detected:
        requirement = _category_requirement(category)
        match = _match_category(category, requirement, actual)
        requirement_match.append(match)
        score -= match["penalty"]
        if match["weak_hardware"]:
            bottlenecks.extend(match["weak_hardware"])
            pressure.append(category)
        else:
            easy.append(category)

    if len(detected) >= 4:
        score -= 5
    heavy_open_groups = [g for g in process_groups if g.get("memory_mb", 0) >= 800 or g.get("process_count", 0) >= 8]
    score -= min(12, len(heavy_open_groups) * 3)
    score = clamp_score(score)

    bottlenecks = list(dict.fromkeys(bottlenecks))
    status = _fit_status(score, bottlenecks, heavy_open_groups)
    detected_use_cases = [f"{c}类软件" for c in detected] or ["暂未识别到稳定常用软件"]
    return {
        "score": score,
        "status": status,
        "summary": _software_summary(detected, easy, pressure, bottlenecks),
        "detected_categories": detected,
        "detected_use_cases": detected_use_cases,
        "easy_to_run": easy,
        "pressure_categories": pressure,
        "multi_app_pressure": _multi_app_pressure(detected, heavy_open_groups),
        "bottlenecks": bottlenecks or ["暂未发现明显硬件短板"],
        "process_group_attention": heavy_open_groups[:8],
        "software_requirement_match": requirement_match,
    }


def _detected_categories(profile: list[dict], process_groups: list[dict]) -> list[str]:
    categories = []
    for item in profile:
        category = classify_software_name(f"{item.get('name', '')} {item.get('category', '')}")
        if category != "普通软件":
            categories.append(category)
    for group in process_groups:
        category = classify_software_name(group.get("name", ""))
        if category != "普通软件":
            categories.append(category)
    return list(dict.fromkeys(categories))


def _category_requirement(category: str) -> dict:
    for rule_category, _, requirement in SOFTWARE_RULES:
        if rule_category == category:
            return requirement
    return {"memory_gb": 8, "cpu_threads": 4, "disk_free_gb": 20}


def _match_category(category: str, requirement: dict, actual: dict) -> dict:
    weak = []
    penalty = 0
    labels = {
        "memory_gb": "内存",
        "cpu_threads": "CPU线程",
        "disk_free_gb": "C盘空间",
        "gpu_vram_gb": "显卡/显存",
    }
    for key, required in requirement.items():
        if actual.get(key, 0) < required:
            weak.append(labels[key])
            penalty += 8 if key != "gpu_vram_gb" else 10
    return {
        "category": category,
        "required": requirement,
        "actual": {key: actual.get(key, 0) for key in requirement},
        "weak_hardware": weak,
        "penalty": penalty,
        "status": "适配" if not weak else "有压力",
    }


def _multi_app_pressure(categories: list[str], heavy_groups: list[dict]) -> list[str]:
    pressure = []
    if {"开发", "聊天", "办公"}.issubset(set(categories)):
        pressure.append("PyCharm/Cursor/Codex + Chrome 多标签 + 微信/QQ 同时打开时，内存压力会上升。")
    if {"设计", "开发"}.issubset(set(categories)):
        pressure.append("设计软件和开发工具同时开大项目时，CPU、内存和 C 盘缓存都会吃紧。")
    if {"剪辑", "3D"}.intersection(categories):
        pressure.append("剪辑/3D 场景对 CPU、内存、显卡和硬盘空间都会更敏感。")
    for group in heavy_groups[:3]:
        pressure.append(f"{group.get('name')} 当前累计 {group.get('memory_mb')}MB / {group.get('process_count')} 个进程，属于重点后台压力。")
    return pressure[:5]


def _software_summary(categories: list[str], easy: list[str], pressure: list[str], bottlenecks: list[str]) -> str:
    if not categories:
        return "暂未识别到稳定常用软件，先以后台进程和硬件状态作为参考。"
    scene = " + ".join(categories[:4])
    if pressure:
        return f"当前主要场景是 {scene}，多数能跑，但 {', '.join(pressure[:3])} 多开时容易有压力。"
    return f"当前主要场景是 {scene}，硬件对这些常用软件整体适配。"


def _fit_status(score: int, bottlenecks: list[str], heavy_groups: list[dict]) -> str:
    has_real_bottleneck = bool(bottlenecks)
    if score >= 90:
        return "常用软件轻松运行"
    if score >= 80 and not has_real_bottleneck:
        return "常用软件能跑，多开时有压力" if heavy_groups else "常用软件轻松运行"
    if score >= 70 and not has_real_bottleneck:
        return "常用软件基本能跑，重度多开需注意"
    if score >= 60:
        return "部分重软件场景会吃力"
    return "常用软件已明显超出当前硬件能力"
