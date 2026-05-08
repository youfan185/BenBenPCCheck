def _score_by_ranges(value: float, mapping: list[tuple[float, int]], reverse: bool = False) -> int:
    if reverse:
        for threshold, score in mapping:
            if value >= threshold:
                return score
        return mapping[-1][1]
    for threshold, score in mapping:
        if value <= threshold:
            return score
    return mapping[-1][1]


def calculate_score(report: dict) -> dict:
    cpu = report.get("hardware", {}).get("cpu", {}).get("current_usage_percent", 0)
    mem = report.get("hardware", {}).get("memory", {}).get("usage_percent", 0)
    c_drive = next((d for d in report.get("disk_partitions", []) if str(d.get("drive", "")).upper().startswith("C:")), None)
    c_free = c_drive.get("free_gb", 0) if c_drive else 0
    startup_count = report.get("startup_items", {}).get("total_count", 0)
    high_count = len(report.get("processes", {}).get("high_cpu_processes", [])) + len(report.get("processes", {}).get("high_memory_processes", []))
    cleanable = sum(i.get("size_gb", 0) for i in report.get("cleanable_items", []))

    cpu_score = _score_by_ranges(cpu, [(30, 15), (50, 12), (70, 8), (90, 4), (1000, 1)])
    mem_score = _score_by_ranges(mem, [(50, 15), (70, 12), (80, 8), (90, 4), (1000, 1)])
    disk_score = _score_by_ranges(c_free, [(10, 1), (20, 5), (40, 10), (80, 16), (9999, 20)], reverse=True)
    process_score = _score_by_ranges(high_count, [(0, 15), (2, 10), (5, 6), (999, 3)])
    startup_score = _score_by_ranges(startup_count, [(5, 10), (10, 8), (20, 5), (30, 3), (999, 1)])
    clean_score = _score_by_ranges(cleanable, [(2, 10), (5, 8), (15, 6), (30, 3), (9999, 1)])

    total = cpu_score + mem_score + disk_score + process_score + startup_score + clean_score

    if total >= 90:
        level = "excellent"
    elif total >= 80:
        level = "good"
    elif total >= 70:
        level = "normal"
    elif total >= 60:
        level = "warm"
    elif total >= 40:
        level = "bad"
    else:
        level = "alert"

    ip_map = {
        "excellent": ("happy", "开心", "电脑状态很棒，继续保持。"),
        "good": ("smile", "微笑", "电脑整体不错，有少量可优化项目。"),
        "normal": ("tired", "有点累", "电脑还能用，但已经有点累了。"),
        "warm": ("fever", "发烧", "电脑开始发热和卡顿，需要清理优化。"),
        "bad": ("sick", "难受", "电脑状态较差，建议尽快处理。"),
        "alert": ("alert", "报警", "电脑风险较高，请优先备份和检查硬盘。"),
    }
    n, display, msg = ip_map[level]
    return {
        "total_score": total,
        "level": level,
        "sub_scores": {
            "cpu_score": cpu_score,
            "memory_score": mem_score,
            "disk_space_score": disk_score,
            "process_score": process_score,
            "startup_score": startup_score,
            "clean_score": clean_score,
        },
        "ip_status": {
            "name": n,
            "display_name": display,
            "emotion": n,
            "image": f"assets/ip/{n}.png",
            "message": msg,
        },
    }
