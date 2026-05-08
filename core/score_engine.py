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

    total = round(health_score * 0.65 + optimization_score * 0.35)
    level, display_level, ip_name, message = _status_from_health(health_score, optimization_score)

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
        "ip_status": {
            "name": ip_name,
            "display_name": display_level,
            "emotion": ip_name,
            "image": f"assets/ip/{ip_name}.png",
            "message": message,
        },
    }
