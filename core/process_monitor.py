import psutil


def top_processes(limit: int = 50) -> list[dict]:
    rows = []
    for p in psutil.process_iter(["pid", "name", "cpu_percent", "memory_info", "exe"]):
        try:
            mem_mb = (p.info["memory_info"].rss / (1024**2)) if p.info["memory_info"] else 0
            rows.append(
                {
                    "name": p.info.get("name") or "unknown",
                    "pid": p.info.get("pid"),
                    "cpu_percent": round(p.info.get("cpu_percent") or 0.0, 1),
                    "memory_mb": round(mem_mb, 1),
                    "path": p.info.get("exe") or "",
                }
            )
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    rows.sort(key=lambda x: (x["cpu_percent"], x["memory_mb"]), reverse=True)
    return rows[:limit]


def high_usage_processes(rows: list[dict]) -> dict:
    high_cpu = [r for r in rows if r["cpu_percent"] > 30]
    high_mem = [r for r in rows if r["memory_mb"] > 2048]
    return {
        "total_count": len(rows),
        "high_cpu_processes": high_cpu,
        "high_memory_processes": high_mem,
    }
