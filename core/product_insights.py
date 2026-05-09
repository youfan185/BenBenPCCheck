import json
import re
from pathlib import Path


CHAT_KEYWORDS = ("wechat", "weixin", "qq", "tim", "wxwork", "dingtalk")
BROWSER_KEYWORDS = ("chrome", "msedge", "edge", "firefox", "browser")
DESIGN_KEYWORDS = ("photoshop", "illustrator", "premiere", "afterfx", "blender", "c4d", "coreldraw")
DEV_KEYWORDS = ("pycharm", "cursor", "code.exe", "vscode", "visual studio", "idea")
BACKGROUND_KEYWORDS = ("baidunetdisk", "onedrive", "adobe", "creative cloud", "update", "sync", "service")
KEEP_STARTUP_KEYWORDS = ("defender", "security", "driver", "audio", "nvidia", "amd", "intel", "input")
DISABLE_STARTUP_KEYWORDS = ("wechat", "weixin", "qq", "baidu", "onedrive", "spotify", "adobe", "cloud", "game")
BLOAT_KEYWORDS = ("360", "2345", "drivergenius", "ludashi", "sogou", "kingsoft", "wpscloud", "kuaizip")
PROFILE_PATH = Path(__file__).resolve().parents[1] / "resources" / "software_profiles.json"


def build_product_insights(report: dict) -> dict:
    dimensions = build_six_dimension_report(report)
    top3 = build_top3_experience_issues(report, dimensions)
    return {
        "six_dimensions": dimensions,
        "four_dimension_score": dimensions,
        "current_emotion": build_current_emotion(report, dimensions),
        "overview_questions": build_overview_questions(dimensions),
        "top3_experience_issues": top3,
        "space_sections": build_space_sections(report),
        "process_summary": build_process_summary(report),
        "startup_summary": build_startup_summary(report),
        "hardware_bottlenecks": build_hardware_bottlenecks(report),
        "software_fit": build_software_fit(report),
        "user_software_profile": report.get("user_software_profile", []),
        "system_bloat": build_system_bloat(report),
        "optimization_tasks": build_optimization_tasks(report),
        "plain_summary": build_plain_summary(top3),
    }


def build_six_dimension_report(report: dict) -> dict:
    return {
        "space": build_space_dimension(report),
        "hardware": build_hardware_dimension(report),
        "common_software": build_common_software_dimension(report),
        "system_background": build_background_dimension(report),
        "windows_settings": build_windows_settings_dimension(report),
        "stability_risk": build_stability_dimension(report),
    }


def build_space_dimension(report: dict) -> dict:
    c_drive = _c_drive(report)
    cleanable = _cleanable_total(report)
    clutter = _user_clutter_total(report)
    free = c_drive.get("free_gb", 0) if c_drive else 0
    usage = c_drive.get("usage_percent", 0) if c_drive else 0

    score = 92
    if not c_drive:
        score -= 18
    elif free < 10:
        score -= 45
    elif free < 30:
        score -= 28
    elif free < 60:
        score -= 12
    if usage > 90:
        score -= 14
    if cleanable > 20:
        score -= 8
    if clutter > 100:
        score -= 10
    score = _clamp_score(score)

    return {
        "score": score,
        "status": _score_label(score),
        "summary": _space_summary(free, cleanable, clutter, bool(c_drive)),
        "evidence": [
            f"C盘剩余 {free}GB" if c_drive else "未识别到 C 盘",
            f"安全/需确认可清理约 {round(cleanable, 1)}GB",
            f"桌面/下载/文档约 {round(clutter, 1)}GB",
        ],
        "safe_clean": [_space_name(i.get("name", "")) for i in report.get("cleanable_items", []) if i.get("risk") == "safe"],
        "need_confirm": [_space_name(i.get("name", "")) for i in report.get("cleanable_items", []) if i.get("risk") != "safe"],
        "manual_review": [
            _space_name(i.get("name", ""))
            for i in report.get("large_folders", [])
            if i.get("category") in {"desktop_files", "download_files", "documents", "wechat_cache", "qq_cache", "adobe_cache", "browser_cache"}
        ][:8],
    }


def build_hardware_dimension(report: dict) -> dict:
    cpu = report.get("hardware", {}).get("cpu", {})
    mem = report.get("hardware", {}).get("memory", {})
    gpus = report.get("hardware", {}).get("gpu", [])
    c_drive = _c_drive(report)
    threads = int(cpu.get("logical_cores") or 0)
    mem_total = float(mem.get("total_gb") or 0)
    mem_usage = float(mem.get("usage_percent") or 0)

    score = 88
    if threads < 4:
        score -= 30
    elif threads < 8:
        score -= 10
    if mem_total < 8:
        score -= 35
    elif mem_total < 16:
        score -= 18
    if mem_usage > 85:
        score -= 14
    if c_drive and c_drive.get("free_gb", 0) < 30:
        score -= 8
    if not gpus:
        score -= 6
    score = _clamp_score(score)

    gpu_text = gpus[0].get("name", "未检测到") if gpus else "未检测到"
    return {
        "score": score,
        "status": _score_label(score),
        "summary": _hardware_summary(cpu, mem, c_drive, gpus, score),
        "evidence": [
            f"CPU：{cpu.get('name', 'Unknown')}，{threads} 线程",
            f"内存：{mem_total}GB，当前占用 {mem_usage}%",
            f"显卡：{gpu_text}",
        ],
        "gpu": gpus,
    }


def build_common_software_dimension(report: dict) -> dict:
    profile = report.get("user_software_profile", [])
    fit = build_software_fit(report)
    mem_usage = report.get("hardware", {}).get("memory", {}).get("usage_percent", 0)
    attention_count = sum(1 for item in fit if item.get("level") != "good")
    score = _clamp_score(88 - attention_count * 7 - (10 if mem_usage > 80 else 0))
    names = "、".join(item.get("name", "") for item in profile[:5] if item.get("name"))
    return {
        "score": score,
        "status": _score_label(score),
        "summary": f"识别到常用软件：{names}。" if names else "暂未形成稳定的常用软件画像，建议多扫描几次后再判断。",
        "evidence": [
            f"高频/可能常用软件 {len(profile)} 个",
            f"需关注适配的软件 {attention_count} 个",
            f"当前内存占用 {mem_usage}%",
        ],
        "items": fit,
    }


def build_background_dimension(report: dict) -> dict:
    process_summary = build_process_summary(report)
    startup_summary = build_startup_summary(report)
    score = 92
    score -= min(25, startup_summary.get("disable_count", 0) * 3)
    score -= min(20, startup_summary.get("suspicious_count", 0) * 8)
    score -= min(18, process_summary.get("high_cpu_count", 0) * 6 + process_summary.get("high_memory_count", 0) * 4)
    score -= min(12, process_summary.get("background_count", 0))
    score = _clamp_score(score)
    return {
        "score": score,
        "status": _score_label(score),
        "running_process_count": process_summary.get("total_count", 0),
        "startup_count": startup_summary.get("total_count", 0),
        "suggest_disable_count": startup_summary.get("disable_count", 0),
        "suspicious_count": startup_summary.get("suspicious_count", 0),
        "summary": f"检测到 {startup_summary.get('total_count', 0)} 个启动项，建议关闭 {startup_summary.get('disable_count', 0)} 个非必要项。",
        "evidence": [
            f"运行进程 {process_summary.get('total_count', 0)} 个",
            f"高占用进程 {process_summary.get('high_cpu_count', 0) + process_summary.get('high_memory_count', 0)} 个",
            f"可疑启动项 {startup_summary.get('suspicious_count', 0)} 个",
        ],
        "items": startup_summary.get("items", [])[:20],
    }


def build_windows_settings_dimension(report: dict) -> dict:
    settings = report.get("windows_settings", {})
    items = settings.get("items", [])
    attention = sum(1 for item in items if item.get("level") in {"warning", "unknown"})
    score = _clamp_score(88 - attention * 7)
    return {
        "score": score,
        "status": _score_label(score),
        "summary": settings.get("summary") or "已完成 Windows 常见设置轻量检查。",
        "evidence": [f"{item.get('name')}：{item.get('value')}" for item in items[:3]] or ["Windows 设置检查结果较少"],
        "items": items,
    }


def build_stability_dimension(report: dict) -> dict:
    risk = report.get("stability_risk", {})
    items = risk.get("risk_items", [])
    warning_count = sum(1 for item in items if item.get("level") in {"warning", "danger", "unknown"})
    score = _clamp_score(86 - warning_count * 8)
    return {
        "score": score,
        "status": _score_label(score),
        "summary": risk.get("summary") or "当前没有发现明显稳定性风险，后续可增加 SMART、温度和蓝屏日志检查。",
        "evidence": [f"{item.get('name')}：{item.get('status')}" for item in items[:3]] or ["轻量风险检查完成"],
        "risk_items": items,
    }


def build_overview_questions(dimensions: dict) -> list[dict]:
    meta = [
        ("space", "空间", "查看空间"),
        ("hardware", "硬件", "查看硬件"),
        ("common_software", "常用软件", "查看软件"),
        ("system_background", "后台自启", "查看后台"),
        ("windows_settings", "Windows 设置", "查看设置"),
        ("stability_risk", "稳定风险", "查看风险"),
    ]
    rows = []
    for index, (key, title, button) in enumerate(meta, start=1):
        item = dimensions.get(key, {})
        rows.append({
            "key": key,
            "title": title,
            "score": item.get("score", 0),
            "status": item.get("status", ""),
            "summary": item.get("summary", ""),
            "evidence": item.get("evidence", []),
            "button": button,
            "page_index": index,
        })
    return rows


def build_top3_experience_issues(report: dict, dimensions: dict | None = None) -> list[dict]:
    dimensions = dimensions or build_six_dimension_report(report)
    candidates = []
    c_drive = _c_drive(report)
    mem = report.get("hardware", {}).get("memory", {})
    startup = build_startup_summary(report)
    process_summary = build_process_summary(report)
    process_groups = report.get("process_groups", []) or report.get("software", {}).get("process_groups", [])
    heavy_groups = [g for g in process_groups if g.get("pressure_level") in {"中", "高"}]
    cleanable = _cleanable_total(report)
    clutter = _user_clutter_total(report)

    if c_drive and (c_drive.get("free_gb", 0) < 30 or c_drive.get("usage_percent", 0) > 90):
        candidates.append(_issue("C 盘空间偏紧", "C 盘是系统和软件缓存最常用的位置。", "空间太少会影响 Windows 更新、浏览器缓存和设计软件暂存。", "先清理临时文件，再确认回收站和大文件。", 1))
    if mem.get("usage_percent", 0) > 80:
        candidates.append(_issue("内存压力较高", f"当前内存占用 {mem.get('usage_percent')}%。", "同时打开浏览器、聊天、设计或开发软件时更容易卡。", "关闭暂时不用的软件，长期高压再考虑升级内存。", 2))
    if process_summary.get("high_cpu_count", 0) or process_summary.get("high_memory_count", 0):
        candidates.append(_issue("存在高占用进程", "检测到 CPU 或内存占用偏高的程序。", "如果不是正在使用的大软件，就会明显拖慢当前操作。", "到后台详情里确认来源，先关闭观察，不要直接删除文件。", 3))
    if heavy_groups:
        names = "、".join(g.get("name", "") for g in heavy_groups[:4])
        candidates.append(_issue("多软件后台叠加压力明显", f"{names} 等软件按应用聚合后占用较高。", "这通常不是硬件跑不动，而是多个常用软件同时打开导致内存和后台压力叠加。", "优先关闭不用的标签页、小程序窗口、同步和更新后台。", 2))
    if startup.get("disable_count", 0) > 0:
        candidates.append(_issue("非必要启动项偏多", f"建议关闭 {startup.get('disable_count')} 个非必要启动项。", "开机慢、后台常驻多，都会让电脑一开始就背着负担。", "优先关闭聊天、网盘、更新器、游戏平台等非必要自启。", 4))
    if cleanable > 5:
        candidates.append(_issue("临时文件和缓存可整理", f"可清理空间约 {round(cleanable, 1)}GB。", "缓存堆积通常不危险，但会占空间并增加排查成本。", "用户 Temp 和 Windows Temp 可优先清理，回收站要先确认。", 5))
    if clutter > 20:
        candidates.append(_issue("桌面/下载/文档目录较大", f"这些目录约 {round(clutter, 1)}GB。", "不建议自动删除，但长期混放会让 C 盘越来越乱。", "把安装包、压缩包、素材归档到其他盘。", 6))

    candidates.sort(key=lambda item: item["priority"])
    fallback = [
        _issue("建议关注：保持 C 盘至少 40GB 可用空间", "系统和常用软件需要缓存空间。", "空间太紧会让很多软件变慢。", "每周看一次 C 盘剩余空间。", 90, "good"),
        _issue("建议关注：定期检查开机启动项", "软件更新后可能重新加入自启动。", "启动项越多，开机和后台越慢。", "保留安全、驱动类项目，其他按需关闭。", 91, "good"),
        _issue("建议关注：每周重启一次电脑", "长期不重启会累积后台状态。", "偶发卡顿和更新等待可能变多。", "重启后再扫描一次，对比状态变化。", 92, "good"),
    ]
    for item in fallback:
        if len(candidates) >= 3:
            break
        candidates.append(item)
    return candidates[:3]


def build_current_emotion(report: dict, dimensions: dict) -> dict:
    score = int(report.get("score", {}).get("total_score", 0) or 0)
    if score >= 90:
        image, status, message = "assets/ip/90-100.png", "很健康", "电脑状态很好，继续保持。"
    elif score >= 75:
        image, status, message = "assets/ip/70-90.png", "良好", "整体不错，只有少量项目值得整理。"
    elif score >= 60:
        image, status, message = "assets/ip/60-70.png", "有点累", "电脑还能用，但后台、缓存或常用软件压力需要关注。"
    elif score >= 40:
        image, status, message = "assets/ip/30-60.png", "难受", "多项问题叠加，建议先处理低风险高收益项目。"
    else:
        image, status, message = "assets/ip/0-30.png", "报警", "电脑负担较重，建议先备份重要文件再排查风险项。"
    weakest = min(dimensions.items(), key=lambda pair: pair[1].get("score", 100), default=("", {}))
    if weakest[0]:
        message += f" 当前最需要关注：{_dimension_name(weakest[0])}。"
    return {"score": score, "status": status, "emoji": image, "message": message}


def build_space_sections(report: dict) -> dict:
    safe, confirm, manual = [], [], []
    for item in report.get("cleanable_items", []):
        row = {
            "name": _space_name(item.get("name", "")),
            "path": item.get("path", ""),
            "size_gb": item.get("size_gb", 0),
            "explain": _space_explain(item.get("name", "")),
            "button": "立即清理" if item.get("risk") == "safe" else "先确认",
        }
        if item.get("risk") == "safe":
            safe.append(row)
        else:
            confirm.append(row)
    for item in report.get("large_folders", []):
        if item.get("category") in {"desktop_files", "download_files", "documents", "wechat_cache", "qq_cache", "adobe_cache", "browser_cache"}:
            manual.append({
                "name": _space_name(item.get("name", "")),
                "path": item.get("path", ""),
                "size_gb": item.get("size_gb", 0),
                "explain": item.get("suggestion", "建议确认内容后再处理。"),
                "button": "打开位置",
            })
    return {"safe_clean": safe, "confirm_clean": confirm, "manual_review": manual}


def build_process_summary(report: dict) -> dict:
    rows = []
    for item in report.get("process_list", []):
        category = classify_process(item)
        can_close = category not in {"系统/驱动", "未知"}
        rows.append({**item, "category": category, "can_close": can_close, "explain": explain_process(item, category)})
    return {
        "total_count": len(report.get("process_list", [])),
        "high_cpu_count": len(report.get("processes", {}).get("high_cpu_processes", [])),
        "high_memory_count": len(report.get("processes", {}).get("high_memory_processes", [])),
        "background_count": sum(1 for r in rows if r["category"] == "后台常驻"),
        "suggest_close_count": sum(1 for r in rows if r["can_close"] and r.get("memory_mb", 0) > 300),
        "items": rows,
    }


def build_startup_summary(report: dict) -> dict:
    items = []
    keep = disable = suspicious = unknown = 0
    for item in report.get("startup_items", {}).get("items", []):
        category = classify_startup(item)
        if category == "建议保留":
            keep += 1
        elif category == "建议关闭":
            disable += 1
        elif category == "可疑项目":
            suspicious += 1
        else:
            unknown += 1
        items.append({
            **item,
            "category": category,
            "type": startup_type(item.get("name", "")),
            "impact": startup_impact(category),
            "buttons": ["禁用", "打开位置", "复制路径"],
        })
    return {"total_count": len(items), "keep_count": keep, "disable_count": disable, "suspicious_count": suspicious, "unknown_count": unknown, "items": items}


def build_hardware_bottlenecks(report: dict) -> list[dict]:
    hardware = build_hardware_dimension(report)
    cpu = report.get("hardware", {}).get("cpu", {})
    mem = report.get("hardware", {}).get("memory", {})
    gpus = report.get("hardware", {}).get("gpu", [])
    c_drive = _c_drive(report)
    return [
        {"name": "CPU", "status": "够用" if cpu.get("logical_cores", 0) >= 4 else "偏弱", "impact": "影响软件响应、多任务和开发编译。", "suggestion": "只有长期 CPU 满载时才优先考虑升级。"},
        {"name": "内存", "status": "够用" if mem.get("total_gb", 0) >= 16 and mem.get("usage_percent", 0) < 80 else "偏紧", "impact": "影响多开浏览器、设计、剪辑和开发工具。", "suggestion": "经常多开大软件时，优先考虑升级到 32GB 或更高。"},
        {"name": "硬盘空间", "status": "够用" if c_drive and c_drive.get("free_gb", 0) >= 40 else "偏紧", "impact": "影响系统缓存、安装更新和软件暂存。", "suggestion": "建议 C 盘长期保留 40GB，设计/剪辑用户尽量 100GB 以上。"},
        {"name": "显卡", "status": "已检测" if gpus else "未检测", "impact": gpus[0].get("name", "") if gpus else report.get("gpu_status", {}).get("message", "未读取到显卡信息。"), "suggestion": "重度 3D、AI 生图、视频特效需要结合显存判断。"},
    ]


def build_software_fit(report: dict) -> list[dict]:
    profiles = _load_software_profiles()
    user_profile = report.get("user_software_profile", [])
    mem = report.get("hardware", {}).get("memory", {})
    cpu = report.get("hardware", {}).get("cpu", {})
    gpus = report.get("hardware", {}).get("gpu", [])
    c_drive = _c_drive(report)
    total_mem = float(mem.get("total_gb") or 0)
    c_free = c_drive.get("free_gb", 0) if c_drive else 0
    cpu_threads = int(cpu.get("logical_cores") or 0)
    gpu_vram = max((float(gpu.get("vram_gb") or 0) for gpu in gpus), default=0)

    rows = []
    for item in user_profile[:10]:
        name = item.get("name", "")
        profile = profiles.get(name) or _profile_by_keyword(profiles, name)
        if not profile:
            rows.append(_unknown_software_fit(item))
            continue
        recommended = profile.get("recommended", {})
        fit_score = 100
        hardware_match = {}
        fit_score = _match_requirement(hardware_match, "memory", total_mem, recommended.get("memory_gb", 0), fit_score, 22)
        fit_score = _match_requirement(hardware_match, "cpu", cpu_threads, recommended.get("cpu_threads", 0), fit_score, 16)
        fit_score = _match_requirement(hardware_match, "disk", c_free, recommended.get("disk_free_gb", 0), fit_score, 18)
        required_vram = recommended.get("gpu_vram_gb")
        if required_vram:
            fit_score = _match_requirement(hardware_match, "gpu", gpu_vram, required_vram, fit_score, 20)
        else:
            hardware_match["gpu"] = "不关键"
        fit_score = _clamp_score(fit_score)
        rows.append({
            "name": name,
            "category": profile.get("category", item.get("category", "普通软件")),
            "usage_score": item.get("common_score", 0),
            "common_score": item.get("common_score", 0),
            "fit_score": fit_score,
            "status": _fit_status(fit_score),
            "level": "good" if fit_score >= 75 else "medium",
            "summary": _software_summary(name, fit_score),
            "hardware_match": hardware_match,
            "bottleneck": _software_bottleneck(name, hardware_match),
            "suggestion": _software_suggestion(hardware_match),
            "evidence": item.get("evidence", []),
        })
    return rows


def build_optimization_tasks(report: dict) -> list[dict]:
    tasks = []
    for item in report.get("cleanable_items", []):
        if item.get("risk") == "safe":
            tasks.append({"title": f"清理{_space_name(item.get('name', '临时文件'))}", "type": "safe_clean", "risk": "低", "group": "立即处理", "expected_gain": f"释放约 {item.get('size_gb', 0)}GB 空间", "button_text": "立即清理", "auto_supported": True})
    startup = build_startup_summary(report)
    if startup["disable_count"] > 0:
        tasks.append({"title": f"关闭 {startup['disable_count']} 个非必要启动项", "type": "startup_disable", "risk": "低", "group": "建议处理", "expected_gain": "减少开机和后台常驻占用", "button_text": "优化启动项", "auto_supported": True})
    if _user_clutter_total(report) > 20:
        tasks.append({"title": "整理桌面、下载和文档目录", "type": "manual_review", "risk": "低", "group": "建议处理", "expected_gain": "让系统盘更清爽，文件更容易管理", "button_text": "查看大目录", "auto_supported": False})
    if startup["suspicious_count"] > 0:
        tasks.append({"title": "检查可疑启动项", "type": "risk_check", "risk": "中", "group": "谨慎处理", "expected_gain": "降低异常软件自启动风险", "button_text": "查看详情", "auto_supported": False})
    return tasks[:5]


def build_system_bloat(report: dict) -> dict:
    process_summary = build_process_summary(report)
    bloat_like = []
    for item in process_summary.get("items", []):
        text = f"{item.get('name', '')} {item.get('path', '')}".lower()
        if any(keyword in text for keyword in BLOAT_KEYWORDS):
            bloat_like.append({"name": item.get("name", ""), "path": item.get("path", ""), "reason": "命中常见捆绑/常驻软件关键词，建议先确认来源。"})
    startup = build_startup_summary(report)
    return {
        "startup_total": startup.get("total_count", 0),
        "startup_disable_count": startup.get("disable_count", 0),
        "startup_suspicious_count": startup.get("suspicious_count", 0),
        "background_count": process_summary.get("background_count", 0),
        "bloat_like_processes": bloat_like[:10],
        "message": "可疑项只代表来源不够明确，建议先禁用观察，不要直接删除文件。",
    }


def classify_process(item: dict) -> str:
    text = f"{item.get('name', '')} {item.get('path', '')}".lower()
    if any(k in text for k in BROWSER_KEYWORDS):
        return "浏览器"
    if any(k in text for k in CHAT_KEYWORDS):
        return "聊天软件"
    if any(k in text for k in DESIGN_KEYWORDS):
        return "设计/剪辑"
    if any(k in text for k in DEV_KEYWORDS):
        return "开发工具"
    if any(k in text for k in BACKGROUND_KEYWORDS):
        return "后台常驻"
    if "windows" in text or "system32" in text:
        return "系统/驱动"
    if not item.get("path"):
        return "未知"
    return "正在使用"


def explain_process(item: dict, category: str) -> str:
    name = item.get("name", "这个程序")
    memory = item.get("memory_mb", 0)
    if category in {"设计/剪辑", "开发工具"}:
        return f"{name} 占用 {memory}MB 内存。如果正在处理大项目，这是正常的；不用时可关闭释放资源。"
    if category == "浏览器":
        return f"{name} 属于浏览器进程，标签页越多占用越高。"
    if category == "后台常驻":
        return f"{name} 可能在后台同步、更新或常驻，不用时可关闭观察。"
    return f"{name} 当前占用 {memory}MB 内存。"


def classify_startup(item: dict) -> str:
    name = item.get("name", "").lower()
    path = item.get("path", "").lower()
    if not path or "\\temp\\" in path or "/temp/" in path or _looks_random(name):
        return "可疑项目"
    if any(k in name or k in path for k in KEEP_STARTUP_KEYWORDS):
        return "建议保留"
    if any(k in name or k in path for k in DISABLE_STARTUP_KEYWORDS):
        return "建议关闭"
    return "未知项目"


def startup_type(name: str) -> str:
    text = name.lower()
    if any(k in text for k in CHAT_KEYWORDS):
        return "聊天软件"
    if "cloud" in text or "drive" in text or "disk" in text:
        return "同步/网盘"
    if "adobe" in text:
        return "设计软件组件"
    return "普通软件"


def startup_impact(category: str) -> str:
    if category == "建议关闭":
        return "关闭后通常不影响使用，只是不再开机自动打开。"
    if category == "建议保留":
        return "可能与驱动、安全或系统体验有关，建议保留。"
    if category == "可疑项目":
        return "路径或名称不够明确，建议先确认来源。"
    return "暂时无法判断来源，建议打开位置或复制路径查询。"


def build_plain_summary(top3: list[dict]) -> str:
    risky = [item for item in top3 if item.get("level") != "good"]
    if not risky:
        return "电脑整体状态不错，暂时没有明显影响体验的问题。"
    return "主要影响体验的是：" + "、".join(item["title"] for item in risky[:3]) + "。建议先处理风险低、收益明显的项目。"


def _issue(title: str, why: str, impact: str, action: str, priority: int, level: str = "medium") -> dict:
    return {"title": title, "level": level, "why": why, "impact": impact, "action": action, "priority": priority}


def _match_requirement(result: dict, key: str, actual: float, required: float, score: int, penalty: int) -> int:
    if actual >= required:
        result[key] = "够用"
        return score
    result[key] = "偏紧" if actual > 0 else "未知"
    return score - penalty


def _c_drive(report: dict) -> dict | None:
    return next((d for d in report.get("disk_partitions", []) if str(d.get("drive", "")).upper().startswith("C:")), None)


def _cleanable_total(report: dict) -> float:
    return sum(i.get("size_gb", 0) for i in report.get("cleanable_items", []))


def _user_clutter_total(report: dict) -> float:
    return sum(i.get("size_gb", 0) for i in report.get("large_folders", []) if i.get("category") in {"desktop_files", "download_files", "documents"})


def _space_summary(free: float, cleanable: float, clutter: float, has_c_drive: bool) -> str:
    if not has_c_drive:
        return "暂未识别 C 盘空间，建议重新扫描。"
    if free < 30:
        return f"C 盘剩余 {free}GB，建议优先清理临时文件和确认大文件。"
    if cleanable > 10 or clutter > 50:
        return "C 盘空间基本够用，但缓存和用户目录建议整理。"
    return "空间比较充足，不是当前卡顿的主要原因。"


def _hardware_summary(cpu: dict, mem: dict, c_drive: dict | None, gpus: list[dict], score: int) -> str:
    if score >= 75:
        return f"{cpu.get('logical_cores', 0)} 线程 CPU、{mem.get('total_gb', 0)}GB 内存，日常使用基本够用。"
    if mem.get("total_gb", 0) < 16:
        return f"内存 {mem.get('total_gb', 0)}GB 偏紧，多开大软件时容易有压力。"
    if c_drive and c_drive.get("free_gb", 0) < 30:
        return "硬件基本够用，但 C 盘空间会影响软件缓存。"
    if not gpus:
        return "显卡信息未读到，3D、AI 生图、视频特效能力暂时无法准确判断。"
    return "部分硬件指标偏弱，建议结合常用软件再判断是否升级。"


def _load_software_profiles() -> dict:
    try:
        return json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _profile_by_keyword(profiles: dict, name: str) -> dict:
    lower = name.lower()
    for profile_name, profile in profiles.items():
        names = [profile_name, *profile.get("process_names", [])]
        if any(item.lower().removesuffix(".exe") in lower or lower in item.lower() for item in names):
            return profile
    return {}


def _unknown_software_fit(item: dict) -> dict:
    return {
        "name": item.get("name", ""),
        "category": item.get("category", "普通软件"),
        "usage_score": item.get("common_score", 0),
        "common_score": item.get("common_score", 0),
        "fit_score": 70,
        "status": "需要观察",
        "level": "medium",
        "summary": "已识别为常用软件，但暂时没有内置配置档案。",
        "hardware_match": {"cpu": "未知", "memory": "未知", "disk": "未知", "gpu": "未知"},
        "bottleneck": "当前版本还无法准确判断它的硬件需求。",
        "suggestion": "如果运行时明显卡顿，使用前先关闭不用的后台软件。",
        "evidence": item.get("evidence", []),
    }


def _fit_status(score: int) -> str:
    if score >= 85:
        return "常用软件轻松运行"
    if score >= 70:
        return "常用软件能跑，多开时有压力"
    if score >= 55:
        return "部分重软件场景会吃力"
    return "常用软件已明显超出当前硬件能力"


def _software_summary(name: str, score: int) -> str:
    if score >= 85:
        return f"{name} 跑起来比较稳。"
    if score >= 70:
        return f"{name} 能跑，多任务和后台叠加时需要注意。"
    if score >= 55:
        return f"{name} 能运行，但处理大文件或多开时可能会慢。"
    return f"{name} 对当前电脑有压力。"


def _software_bottleneck(name: str, hardware_match: dict) -> str:
    weak = [key for key, value in hardware_match.items() if value in {"偏紧", "未知"}]
    if not weak:
        return "暂未发现明显硬件短板。"
    names = {"cpu": "CPU", "memory": "内存", "disk": "C盘空间", "gpu": "显卡"}
    return f"{name} 主要需要关注：" + "、".join(names.get(key, key) for key in weak)


def _software_suggestion(hardware_match: dict) -> str:
    suggestions = []
    if hardware_match.get("memory") in {"偏紧", "未知"}:
        suggestions.append("使用前关闭不用的软件和浏览器标签页")
    if hardware_match.get("disk") in {"偏紧", "未知"}:
        suggestions.append("保持 C 盘足够空间")
    if hardware_match.get("gpu") in {"偏紧", "未知"}:
        suggestions.append("重度 3D、AI 生图或视频特效前确认显卡能力")
    return "；".join(suggestions) + "。" if suggestions else "正常使用即可，定期扫描观察后台和空间。"


def _space_name(name: str) -> str:
    mapping = {
        "User Temp": "用户临时文件",
        "Windows Temp": "Windows 临时文件",
        "Recycle Bin": "回收站",
        "Desktop": "桌面",
        "Downloads": "下载目录",
        "Documents": "文档目录",
        "Chrome Cache": "Chrome 缓存",
        "Edge Cache": "Edge 缓存",
        "WeChat Files": "微信文件",
        "Tencent Files": "QQ 文件",
        "Adobe Cache": "Adobe 缓存",
    }
    return mapping.get(name, name)


def _space_explain(name: str) -> str:
    if "Temp" in name:
        return "安装、解压和运行留下的临时文件，大多数可以安全清理。"
    if name == "Recycle Bin":
        return "清空前需要确认里面没有还要恢复的文件。"
    return "建议确认内容后再处理。"


def _score_label(score: int) -> str:
    if score >= 90:
        return "很健康"
    if score >= 75:
        return "良好"
    if score >= 60:
        return "有点累"
    if score >= 40:
        return "需要整理"
    return "需要尽快处理"


def _dimension_name(key: str) -> str:
    return {
        "space": "空间",
        "hardware": "硬件",
        "common_software": "常用软件",
        "system_background": "后台自启",
        "windows_settings": "Windows 设置",
        "stability_risk": "稳定风险",
    }.get(key, key)


def _clamp_score(score: int | float) -> int:
    return max(0, min(100, int(round(score))))


def _looks_random(name: str) -> bool:
    return bool(re.fullmatch(r"[a-z0-9]{10,}", name or ""))
