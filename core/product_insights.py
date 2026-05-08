CHAT_KEYWORDS = ("wechat", "weixin", "qq", "tim", "wxwork")
BROWSER_KEYWORDS = ("chrome", "edge", "firefox", "browser")
DESIGN_KEYWORDS = ("photoshop", "illustrator", "coreldraw", "premiere", "afterfx", "blender", "c4d")
BACKGROUND_KEYWORDS = ("baidunetdisk", "onedrive", "adobe", "creative cloud", "update", "sync", "service")
KEEP_STARTUP_KEYWORDS = ("defender", "security", "driver", "audio", "nvidia", "amd", "intel", "input")
DISABLE_STARTUP_KEYWORDS = ("wechat", "weixin", "qq", "baidu", "onedrive", "spotify", "adobe", "cloud", "game")


def build_product_insights(report: dict) -> dict:
    return {
        "problem_cards": build_problem_cards(report),
        "space_sections": build_space_sections(report),
        "process_summary": build_process_summary(report),
        "startup_summary": build_startup_summary(report),
        "hardware_bottlenecks": build_hardware_bottlenecks(report),
        "software_fit": build_software_fit(report),
        "optimization_tasks": build_optimization_tasks(report),
        "plain_summary": build_plain_summary(report),
    }


def build_problem_cards(report: dict) -> list[dict]:
    cards = []
    c_drive = _c_drive(report)
    startup = report.get("startup_items", {})
    startup_count = startup.get("total_count", 0)
    mem = report.get("hardware", {}).get("memory", {})
    high_count = _high_process_count(report)
    cleanable = _cleanable_total(report)
    clutter = _user_clutter_total(report)

    if c_drive and (c_drive.get("free_gb", 0) < 20 or c_drive.get("usage_percent", 0) > 90):
        cards.append(_card(
            "c_drive_low",
            "C 盘空间偏紧",
            "high" if c_drive.get("free_gb", 0) < 10 else "medium",
            "space",
            f"C 盘剩余 {c_drive.get('free_gb', 0)}GB，占用率 {c_drive.get('usage_percent', 0)}%。",
            "C 盘是系统盘，空间太紧会影响 Windows、浏览器和 Photoshop 缓存。",
            "优先清理临时文件、回收站和确认无用的大文件。",
            "safe_clean",
            1,
        ))

    if mem.get("usage_percent", 0) > 80:
        cards.append(_card(
            "memory_pressure",
            "内存压力较高",
            "medium",
            "hardware",
            f"当前内存占用 {mem.get('usage_percent', 0)}%。",
            "内存像电脑工作台，同时打开软件越多越容易卡。",
            "关闭暂时不用的软件，处理大图或多项目开发前减少后台程序。",
            "close_apps",
            2,
        ))

    if high_count:
        cards.append(_card(
            "high_usage_process",
            "有软件占用偏高",
            "medium",
            "process",
            f"检测到 {high_count} 个 CPU 或内存占用偏高的程序。",
            "如果不是正在使用的大软件，可能会拖慢当前操作。",
            "到“谁在偷偷运行”里查看，占用异常时先关闭再观察。",
            "review_process",
            3,
        ))

    if startup_count > 10:
        cards.append(_card(
            "startup_too_many",
            "开机启动项偏多",
            "medium" if startup_count <= 20 else "high",
            "startup",
            f"检测到 {startup_count} 个开机启动项。",
            "启动项越多，开机越慢，后台常驻也越多。",
            "关闭微信、QQ、网盘、Adobe 等非必要自启。",
            "can_disable",
            4,
        ))

    if cleanable > 5:
        cards.append(_card(
            "cache_cleanup",
            "缓存和临时文件可整理",
            "low" if cleanable < 15 else "medium",
            "space",
            f"可清理空间约 {round(cleanable, 1)}GB。",
            "临时文件通常是安装、解压和软件运行留下的。",
            "先清理用户临时文件和 Windows Temp，回收站需要确认。",
            "safe_clean",
            5,
        ))

    if clutter > 20:
        cards.append(_card(
            "user_file_clutter",
            "桌面/下载/文档较大",
            "low" if clutter < 50 else "medium",
            "space",
            f"桌面、下载或文档目录合计约 {round(clutter, 1)}GB。",
            "这些文件不建议自动删除，但长期堆在系统盘会影响管理。",
            "建议转移到其他盘或归档目录。",
            "manual整理",
            6,
        ))

    cards.sort(key=lambda x: x["priority"])
    return cards[:6]


def build_space_sections(report: dict) -> dict:
    safe, confirm, manual = [], [], []
    for item in report.get("cleanable_items", []):
        row = {
            "name": _space_name(item.get("name", "")),
            "path": item.get("path", ""),
            "size_gb": item.get("size_gb", 0),
            "explain": _space_explain(item.get("name", "")),
            "button": "立即清理" if item.get("risk") == "safe" else "查看内容",
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
                "button": "打开文件夹",
            })
    return {"safe_clean": safe, "confirm_clean": confirm, "manual整理": manual}


def build_process_summary(report: dict) -> dict:
    process_list = report.get("process_list", [])
    rows = []
    for item in process_list:
        category = classify_process(item)
        can_close = category not in {"系统/驱动", "未知"}
        rows.append({
            **item,
            "category": category,
            "can_close": can_close,
            "explain": explain_process(item, category),
        })
    return {
        "total_count": len(process_list),
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
    return {
        "total_count": len(items),
        "keep_count": keep,
        "disable_count": disable,
        "suspicious_count": suspicious,
        "unknown_count": unknown,
        "items": items,
    }


def build_hardware_bottlenecks(report: dict) -> list[dict]:
    cpu = report.get("hardware", {}).get("cpu", {})
    mem = report.get("hardware", {}).get("memory", {})
    c_drive = _c_drive(report)
    memory_status = "够用" if mem.get("total_gb", 0) >= 16 and mem.get("usage_percent", 0) < 80 else "紧张"
    disk_status = "够用" if c_drive and c_drive.get("free_gb", 0) >= 40 else "紧张"
    return [
        {
            "name": "CPU",
            "status": "够用" if cpu.get("logical_cores", 0) >= 4 else "紧张",
            "impact": "影响软件响应速度、多任务处理和开发编译体验。",
            "suggestion": "当前优先级不高，除非长期 CPU 占用很高。"
        },
        {
            "name": "内存",
            "status": memory_status,
            "impact": "影响 Photoshop、Chrome、PyCharm/Cursor 同时打开时的流畅度。",
            "suggestion": "如果经常同时开大软件，建议未来升级到 32GB 或 64GB。"
        },
        {
            "name": "硬盘空间",
            "status": disk_status,
            "impact": "C 盘太满会影响系统缓存、安装软件和设计软件暂存盘。",
            "suggestion": "建议保持 C 盘至少 40GB，设计用户尽量 100GB 以上。"
        },
        {
            "name": "显卡",
            "status": "无法判断",
            "impact": "影响 Blender/C4D、AI 生图、视频剪辑和 3D 场景。",
            "suggestion": "当前版本还未采集显卡信息，后续增加显卡检测。"
        },
    ]


def build_software_fit(report: dict) -> list[dict]:
    mem = report.get("hardware", {}).get("memory", {})
    c_drive = _c_drive(report)
    total_mem = mem.get("total_gb", 0)
    c_free = c_drive.get("free_gb", 0) if c_drive else 0
    memory_good = total_mem >= 16
    disk_good = c_free >= 40
    return [
        {
            "name": "Photoshop",
            "status": "can_run" if memory_good and disk_good else "attention",
            "level": "good" if memory_good and disk_good else "medium",
            "summary": "可以运行中等规模设计项目。" if memory_good and disk_good else "可以运行，但需要注意内存和 C 盘空间。",
            "bottleneck": "同时打开浏览器、微信和大 PSD 时内存会有压力。",
            "suggestion": "处理大图前关闭不用的软件，保持 C 盘空间充足。"
        },
        {
            "name": "PyCharm / Cursor",
            "status": "can_run" if total_mem >= 16 else "attention",
            "level": "good" if total_mem >= 16 else "medium",
            "summary": "开发工具基本可以正常运行。",
            "bottleneck": "多项目、多插件和 AI 工具同时运行时会吃内存。",
            "suggestion": "同时开多个项目时，关闭不用的浏览器标签页。"
        },
        {
            "name": "Chrome / Edge",
            "status": "can_run",
            "level": "good" if total_mem >= 16 else "medium",
            "summary": "日常浏览没问题，标签页过多会占内存。",
            "bottleneck": "浏览器多进程会逐步占用内存。",
            "suggestion": "减少长期不用的标签页，定期重启浏览器。"
        },
        {
            "name": "Blender / C4D / AI 生图",
            "status": "unknown",
            "level": "unknown",
            "summary": "暂时无法判断 3D 或 AI 生图性能。",
            "bottleneck": "当前报告没有显卡型号和显存信息。",
            "suggestion": "后续版本增加显卡检测后再给出升级建议。"
        },
    ]


def build_optimization_tasks(report: dict) -> list[dict]:
    tasks = []
    for item in report.get("cleanable_items", []):
        if item.get("risk") == "safe":
            tasks.append({
                "title": f"清理{_space_name(item.get('name', '临时文件'))}",
                "type": "safe_clean",
                "risk": "low",
                "group": "立即处理",
                "expected_gain": f"释放约 {item.get('size_gb', 0)}GB 空间",
                "button_text": "立即清理",
                "auto_supported": True,
            })

    startup_summary = build_startup_summary(report)
    if startup_summary["disable_count"] > 0:
        tasks.append({
            "title": f"优化 {startup_summary['disable_count']} 个非必要开机启动项",
            "type": "startup_disable",
            "risk": "low",
            "group": "建议处理",
            "expected_gain": "减少开机和后台常驻占用",
            "button_text": "优化启动项",
            "auto_supported": True,
        })

    if _user_clutter_total(report) > 20:
        tasks.append({
            "title": "整理桌面、下载和文档目录",
            "type": "manual整理",
            "risk": "low",
            "group": "建议处理",
            "expected_gain": "让系统盘更清爽，文件更容易管理",
            "button_text": "查看大目录",
            "auto_supported": False,
        })

    if startup_summary["suspicious_count"] > 0:
        tasks.append({
            "title": "检查可疑启动项",
            "type": "risk_check",
            "risk": "medium",
            "group": "谨慎处理",
            "expected_gain": "降低异常软件开机自启风险",
            "button_text": "查看详情",
            "auto_supported": False,
        })
    return tasks


def build_plain_summary(report: dict) -> str:
    cards = build_problem_cards(report)
    if not cards:
        return "电脑整体状态不错，暂时没有明显影响体验的问题。"
    names = "、".join(card["title"] for card in cards[:3])
    return f"主要影响体验的是：{names}。建议先处理风险低、收益明显的项目。"


def classify_process(item: dict) -> str:
    text = f"{item.get('name', '')} {item.get('path', '')}".lower()
    if any(k in text for k in BROWSER_KEYWORDS):
        return "浏览器多进程"
    if any(k in text for k in CHAT_KEYWORDS):
        return "聊天社交"
    if any(k in text for k in DESIGN_KEYWORDS):
        return "设计软件"
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
    if category == "设计软件":
        return f"{name} 占用 {memory}MB 内存。如果正在处理大文件，这是正常的；不用时可以关闭释放内存。"
    if category == "浏览器多进程":
        return f"{name} 属于浏览器进程。标签页越多，占用越高。"
    if category == "后台常驻":
        return f"{name} 可能在后台同步、更新或常驻，暂时不用时可以关闭。"
    return f"{name} 当前占用 {memory}MB 内存。"


def classify_startup(item: dict) -> str:
    name = item.get("name", "").lower()
    path = item.get("path", "").lower()
    if not path or "\\temp\\" in path or "/temp/" in path:
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
        return "关闭后不影响软件使用，只是不再开机自动打开。"
    if category == "建议保留":
        return "可能与驱动、安全或系统体验有关，建议保留。"
    if category == "可疑项目":
        return "路径或名称不够明确，建议先确认来源。"
    return "暂时无法判断来源，建议打开位置或复制路径查询。"


def _card(id_: str, title: str, level: str, category: str, evidence: str, impact: str, suggestion: str, action_type: str, priority: int) -> dict:
    return {
        "id": id_,
        "title": title,
        "level": level,
        "category": category,
        "evidence": evidence,
        "impact": impact,
        "suggestion": suggestion,
        "action_type": action_type,
        "priority": priority,
    }


def _c_drive(report: dict) -> dict | None:
    return next((d for d in report.get("disk_partitions", []) if str(d.get("drive", "")).upper().startswith("C:")), None)


def _high_process_count(report: dict) -> int:
    processes = report.get("processes", {})
    return len(processes.get("high_cpu_processes", [])) + len(processes.get("high_memory_processes", []))


def _cleanable_total(report: dict) -> float:
    return sum(i.get("size_gb", 0) for i in report.get("cleanable_items", []))


def _user_clutter_total(report: dict) -> float:
    return sum(
        i.get("size_gb", 0)
        for i in report.get("large_folders", [])
        if i.get("category") in {"desktop_files", "download_files", "documents"}
    )


def _space_name(name: str) -> str:
    mapping = {
        "User Temp": "用户临时文件",
        "Windows Temp": "Windows 临时文件",
        "Recycle Bin": "回收站",
        "Desktop": "桌面文件",
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
        return "软件安装、解压和运行时留下的临时文件，大部分可以安全清理。"
    if name == "Recycle Bin":
        return "回收站里的文件仍然占用空间，清空前需要确认不再需要。"
    return "建议确认内容后再处理。"
