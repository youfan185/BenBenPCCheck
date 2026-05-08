def build_diagnosis(report: dict) -> dict:
    issues = []

    c_drive = next((d for d in report.get("disk_partitions", []) if str(d.get("drive", "")).upper().startswith("C:")), None)
    if c_drive and (c_drive["free_gb"] < 20 or c_drive["usage_percent"] > 90):
        issues.append(
            {
                "level": "warning",
                "title": "C盘空间偏少",
                "detail": f"C盘剩余 {c_drive['free_gb']}GB，占用率 {c_drive['usage_percent']}%。",
                "priority": 1,
            }
        )

    startup_count = report.get("startup_items", {}).get("total_count", 0)
    if startup_count > 20:
        issues.append(
            {
                "level": "warning",
                "title": "启动项偏多",
                "detail": f"当前检测到 {startup_count} 个启动项，可能拖慢开机速度。",
                "priority": 2,
            }
        )

    mem = report.get("hardware", {}).get("memory", {})
    if mem.get("usage_percent", 0) > 80:
        issues.append(
            {
                "level": "warning",
                "title": "内存压力较高",
                "detail": f"当前内存占用 {mem.get('usage_percent')}%。",
                "priority": 3,
            }
        )

    processes = report.get("processes", {})
    if processes.get("high_cpu_processes") or processes.get("high_memory_processes"):
        issues.append(
            {
                "level": "info",
                "title": "存在高占用程序",
                "detail": "检测到 CPU 或内存占用较高进程，建议检查是否为正常工作负载。",
                "priority": 4,
            }
        )

    cleanable_total = sum(i.get("size_gb", 0) for i in report.get("cleanable_items", []))
    if cleanable_total > 15:
        issues.append(
            {
                "level": "info",
                "title": "缓存堆积明显",
                "detail": f"可清理空间约 {round(cleanable_total, 1)}GB，建议执行安全清理。",
                "priority": 5,
            }
        )

    issues.sort(key=lambda x: x["priority"])
    summary = "系统整体可用。" if not issues else "当前主要问题集中在：" + "、".join(i["title"] for i in issues[:3])

    return {"main_issues": issues, "local_summary": summary}
