from core.hardware_rules import score_hardware
from core.software_rules import analyze_software_fit


def _score_low_is_good(value: float, bands: list[tuple[float, int]]) -> int:
    for max_value, score in bands:
        if value <= max_value:
            return score
    return bands[-1][1]


def _score_high_is_good(value: float, bands: list[tuple[float, int]]) -> int:
    for min_value, score in bands:
        if value >= min_value:
            return score
    return bands[-1][1]


def _status_from_health(health_score: int, optimization_score: int) -> tuple[str, str, str, str]:
    if health_score < 40:
        return "alert", "建议尽快处理", "alert", "先备份重要文件，再检查空间、内存和可疑启动项。"
    if health_score < 60:
        return "bad", "存在风险", "sick", "电脑有多项问题叠加，建议尽快处理几个关键项。"
    if optimization_score < 50:
        return "normal", "有点累", "tired", "后台或缓存有点多，先帮我减负吧。"
    if health_score >= 90:
        return "excellent", "状态很好", "happy", "电脑状态很棒，继续保持。"
    if health_score >= 80:
        return "good", "状态良好", "smile", "电脑整体不错，只有少量可优化项目。"
    return "warm", "需要整理", "fever", "电脑还能正常使用，但已经有一些值得整理的地方。"


def calculate_score(report: dict) -> dict:
    hardware_score = score_hardware(report)
    software_fit_score = analyze_software_fit(report)
    system_usability_score = calculate_system_usability_score(report)
    v2_total = round(
        hardware_score["score"] * 0.30
        + software_fit_score["score"] * 0.40
        + system_usability_score["score"] * 0.30
    )

    cpu = report.get("hardware", {}).get("cpu", {}).get("current_usage_percent", 0)
    mem = report.get("hardware", {}).get("memory", {}).get("usage_percent", 0)
    c_drive = next((d for d in report.get("disk_partitions", []) if str(d.get("drive", "")).upper().startswith("C:")), None)
    c_free = c_drive.get("free_gb", 0) if c_drive else 0
    startup_count = report.get("startup_items", {}).get("total_count", 0)
    high_count = len(report.get("processes", {}).get("high_cpu_processes", [])) + len(report.get("processes", {}).get("high_memory_processes", []))
    cleanable = sum(i.get("size_gb", 0) for i in report.get("cleanable_items", []))
    user_file_size = sum(
        i.get("size_gb", 0)
        for i in report.get("large_folders", [])
        if i.get("category") in {"desktop_files", "download_files", "documents"}
    )

    disk_score = _score_high_is_good(c_free, [(80, 20), (40, 16), (20, 10), (10, 5), (0, 1)])
    memory_score = _score_low_is_good(mem, [(50, 20), (70, 16), (80, 11), (90, 6), (1000, 2)])
    process_score = _score_low_is_good(high_count, [(0, 15), (2, 11), (5, 7), (999, 3)])
    startup_score = _score_low_is_good(startup_count, [(5, 15), (10, 12), (20, 8), (30, 4), (999, 1)])
    clean_score = _score_low_is_good(cleanable, [(2, 10), (5, 8), (15, 6), (30, 3), (9999, 1)])
    clutter_score = _score_low_is_good(user_file_size, [(5, 10), (20, 8), (50, 5), (100, 3), (9999, 1)])
    cpu_score = _score_low_is_good(cpu, [(30, 10), (50, 8), (70, 5), (90, 3), (1000, 1)])

    health_score = disk_score + memory_score + process_score + cpu_score + 35
    health_score = max(0, min(100, health_score))

    optimization_score = startup_score + clean_score + clutter_score + process_score + 50
    optimization_score = max(0, min(100, optimization_score))

    total = v2_total
    level, display_level, ip_name, message = _status_from_health(hardware_score["score"], system_usability_score["score"])

    return {
        "total_score": total,
        "health_score": health_score,
        "optimization_score": optimization_score,
        "level": level,
        "display_level": display_level,
        "sub_scores": {
            "cpu_score": cpu_score,
            "memory_score": memory_score,
            "disk_space_score": disk_score,
            "process_score": process_score,
            "startup_score": startup_score,
            "clean_score": clean_score,
            "clutter_score": clutter_score,
        },
        "hardware_score": hardware_score,
        "software_fit_score": software_fit_score,
        "system_usability_score": system_usability_score,
        "ip_status": {
            "name": ip_name,
            "display_name": display_level,
            "emotion": ip_name,
            "image": f"assets/ip/{ip_name}.png",
            "message": message,
        },
    }


def calculate_system_usability_score(report: dict) -> dict:
    c_drive = next((d for d in report.get("disk_partitions", []) if str(d.get("drive", "")).upper().startswith("C:")), None)
    c_free = c_drive.get("free_gb", 0) if c_drive else 0
    c_usage = c_drive.get("usage_percent", 0) if c_drive else 0
    cleanable = sum(i.get("size_gb", 0) for i in report.get("cleanable_items", []))
    app_cache = sum(i.get("size_gb", 0) for i in report.get("large_folders", []) if "cache" in i.get("category", ""))
    chat_files = sum(i.get("size_gb", 0) for i in report.get("large_folders", []) if i.get("category") in {"wechat_cache", "qq_cache"})
    process_groups = report.get("process_groups", []) or report.get("software", {}).get("process_groups", [])
    heavy_groups = [g for g in process_groups if g.get("pressure_level") in {"中", "高"}]
    startup_count = report.get("startup_items", {}).get("total_count", 0)
    suspicious = report.get("product", {}).get("startup_summary", {}).get("suspicious_count", 0)
    if not suspicious:
        suspicious = sum(1 for i in report.get("startup_items", {}).get("items", []) if not i.get("path"))

    windows_points = 20
    if report.get("windows_settings", {}).get("items"):
        attention = sum(1 for i in report.get("windows_settings", {}).get("items", []) if i.get("level") in {"warning", "unknown"})
        windows_points -= min(8, attention * 2)

    space_points = 25
    if not c_drive:
        space_points = 12
    elif c_free < 10 or c_usage > 95:
        space_points = 5
    elif c_free < 30 or c_usage > 90:
        space_points = 13
    elif c_free < 60:
        space_points = 19
    if cleanable > 30:
        space_points -= 3

    file_points = 20
    if app_cache + chat_files > 80:
        file_points = 9
    elif app_cache + chat_files > 30:
        file_points = 14
    elif app_cache + chat_files > 10:
        file_points = 17

    background_points = 20 - min(16, len(heavy_groups) * 4)
    startup_points = 15
    if startup_count > 25:
        startup_points -= 8
    elif startup_count > 15:
        startup_points -= 5
    elif startup_count > 8:
        startup_points -= 2
    startup_points -= min(6, suspicious * 3)

    total = max(0, min(100, int(round(windows_points + space_points + file_points + background_points + startup_points))))
    if total >= 85:
        status = "干净"
    elif total >= 70:
        status = "有点累"
    elif total >= 55:
        status = "需要整理"
    else:
        status = "风险较高"
    return {
        "score": total,
        "status": status,
        "summary": _system_summary(c_free, app_cache, chat_files, heavy_groups, suspicious),
        "detail": {
            "windows": windows_points,
            "space_cache": space_points,
            "software_files": file_points,
            "background": background_points,
            "startup_risk": startup_points,
        },
        "priority_items": _system_priority_items(c_free, cleanable, heavy_groups, startup_count, suspicious),
        "do_not_touch": ["Windows 系统目录", "驱动和安全软件启动项", "不确定来源的大文件", "注册表和系统服务"],
    }


def _system_summary(c_free: float, app_cache: float, chat_files: float, heavy_groups: list[dict], suspicious: int) -> str:
    points = []
    if c_free and c_free < 40:
        points.append(f"C盘剩余 {c_free}GB")
    if app_cache + chat_files > 10:
        points.append(f"聊天/缓存文件约 {round(app_cache + chat_files, 1)}GB")
    if heavy_groups:
        points.append(f"{len(heavy_groups)} 类后台进程占用明显")
    if suspicious:
        points.append(f"{suspicious} 个启动项建议核实")
    return "、".join(points) + "。" if points else "系统环境整体干净，暂未发现明显拖后腿项目。"


def _system_priority_items(c_free: float, cleanable: float, heavy_groups: list[dict], startup_count: int, suspicious: int) -> list[str]:
    rows = []
    if heavy_groups:
        rows.append("先确认高占用的软件进程组，尤其是多进程叠加的软件。")
    if c_free and c_free < 40:
        rows.append("把 C 盘可用空间恢复到 40GB 以上。")
    if suspicious:
        rows.append("核实可疑启动项，只禁用观察，不直接删除文件。")
    if startup_count > 12:
        rows.append("关闭聊天、网盘、更新器、游戏平台等非必要自启动。")
    if cleanable > 5:
        rows.append("最后再处理低风险临时文件和缓存。")
    return rows[:5]
