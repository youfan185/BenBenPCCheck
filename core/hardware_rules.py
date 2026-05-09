def clamp_score(value: int | float) -> int:
    return max(0, min(100, int(round(value))))


def score_hardware(report: dict) -> dict:
    hardware = report.get("hardware", {})
    cpu = hardware.get("cpu", {})
    memory = hardware.get("memory", {})
    gpus = hardware.get("gpu", [])
    partitions = report.get("disk_partitions", [])
    c_drive = next((d for d in partitions if str(d.get("drive", "")).upper().startswith("C:")), None)

    cpu_threads = int(cpu.get("logical_cores") or 0)
    memory_total = float(memory.get("total_gb") or 0)
    gpu_vram = max((float(g.get("vram_gb") or 0) for g in gpus), default=0)
    disk_total = max((float(d.get("total_gb") or 0) for d in partitions), default=0)
    disk_health_rows = report.get("disk_health") or report.get("storage", {}).get("disk_health", [])
    cpu_name = cpu.get("name", "Unknown CPU")
    gpu_name = gpus[0].get("name", "未检测到显卡") if gpus else "未检测到显卡"

    cpu_score = 22
    if cpu_threads < 4:
        cpu_score = 8
    elif cpu_threads < 8:
        cpu_score = 16
    elif cpu_threads < 12:
        cpu_score = 20
    elif cpu_threads >= 16:
        cpu_score = 24
    if _unknown_cpu(cpu_name):
        cpu_score = min(cpu_score, 20)
    if _looks_current_high_end_cpu(cpu_name):
        cpu_score = max(cpu_score, 26)
    cpu_score = min(cpu_score, 29)

    gpu_score = 18
    if not gpus:
        gpu_score = 10
    elif gpu_vram == 0:
        gpu_score = 14
    elif gpu_vram < 4:
        gpu_score = 16
    elif gpu_vram < 8:
        gpu_score = 20
    elif gpu_vram < 12:
        gpu_score = 23
    else:
        gpu_score = 25
    if _looks_current_high_end_gpu(gpu_name):
        gpu_score = max(gpu_score, 27)
    gpu_score = min(gpu_score, 29)

    memory_score = 10
    if memory_total < 8:
        memory_score = 4
    elif memory_total < 16:
        memory_score = 8
    elif memory_total < 32:
        memory_score = 11
    elif memory_total < 64:
        memory_score = 13
    else:
        memory_score = 15

    disk_score = 10
    if not partitions:
        disk_score = 7
    elif disk_total >= 1800:
        disk_score = 13
    elif disk_total >= 900:
        disk_score = 12
    elif disk_total >= 450:
        disk_score = 10
    if disk_health_rows:
        disk_score += 1
    disk_score = min(disk_score, 15)

    platform_score = 7
    if cpu_threads >= 16 and memory_total >= 32:
        platform_score = 8
    if _unknown_cpu(cpu_name):
        platform_score = min(platform_score, 7)
    if not disk_health_rows:
        platform_score = min(platform_score, 7)

    total = clamp_score(cpu_score + gpu_score + memory_score + disk_score + platform_score)
    if total >= 90:
        status = "高端"
        upgrade_needed = "不需要"
    elif total >= 80:
        status = "主流偏上"
        upgrade_needed = "不需要"
    elif total >= 70:
        status = "主流可用"
        upgrade_needed = "可选升级"
    elif total >= 60:
        status = "偏旧"
        upgrade_needed = "建议升级"
    else:
        status = "明显落后"
        upgrade_needed = "必须升级"

    items = [
        {"name": "CPU", "score": cpu_score, "max_score": 30, "level": _part_level(cpu_score, 30), "reason": _cpu_reason(cpu_name, cpu_threads)},
        {"name": "显卡", "score": gpu_score, "max_score": 30, "level": _part_level(gpu_score, 30), "reason": _gpu_reason(gpu_name, gpu_vram, bool(gpus))},
        {"name": "内存", "score": memory_score, "max_score": 15, "level": _part_level(memory_score, 15), "reason": _memory_reason(memory_total)},
        {"name": "硬盘", "score": disk_score, "max_score": 15, "level": _part_level(disk_score, 15), "reason": _disk_reason(disk_total, bool(disk_health_rows))},
        {"name": "平台", "score": platform_score, "max_score": 10, "level": _part_level(platform_score, 10), "reason": "整机平台仍可继续使用，但不是最新平台。" if platform_score >= 7 else "平台信息不完整或升级空间有限。"},
    ]
    short = _hardware_market_sentence(status, total)
    return {
        "score": total,
        "status": status,
        "upgrade_needed": upgrade_needed,
        "summary": short,
        "items": items,
        "detail": {
            "cpu": clamp_score(cpu_score / 30 * 100),
            "gpu": clamp_score(gpu_score / 30 * 100),
            "memory": clamp_score(memory_score / 15 * 100),
            "disk": clamp_score(disk_score / 15 * 100),
            "platform": clamp_score(platform_score / 10 * 100),
        },
        "raw_points": {
            "cpu": cpu_score,
            "gpu": gpu_score,
            "memory": memory_score,
            "disk": disk_score,
            "platform": platform_score,
        },
        "key_hardware": [
            f"CPU：{cpu.get('name', 'Unknown')}，{cpu_threads} 线程",
            f"显卡：{gpus[0].get('name', '已检测') if gpus else '未检测到显卡详情'}",
            f"内存：{memory_total}GB",
            f"硬盘容量：约 {disk_total}GB" if c_drive else "硬盘：未检测到",
        ],
    }


def _unknown_cpu(name: str) -> bool:
    return not name or name.lower() in {"unknown cpu", "unknown", "cpu"}


def _looks_current_high_end_cpu(name: str) -> bool:
    text = name.lower()
    return any(k in text for k in ("i9-", "ryzen 9", "ultra 9", "7950", "9950", "14900", "13900"))


def _looks_current_high_end_gpu(name: str) -> bool:
    text = name.lower()
    return any(k in text for k in ("rtx 4080", "rtx 4090", "rtx 5080", "rtx 5090", "rx 7900"))


def _part_level(score: int, max_score: int) -> str:
    ratio = score / max_score if max_score else 0
    if ratio >= 0.9:
        return "高端"
    if ratio >= 0.75:
        return "中上"
    if ratio >= 0.6:
        return "主流"
    if ratio >= 0.45:
        return "偏旧"
    return "落后"


def _hardware_market_sentence(status: str, score: int) -> str:
    if score >= 90:
        return "硬件市场水平较高，属于当前仍然很强的配置。"
    if score >= 80:
        return "硬件属于主流偏上，实用性仍然不错，但不属于当前顶级配置。"
    if score >= 70:
        return "硬件市场水平主流可用，不是顶级但仍能支撑多数日常和专业场景。"
    if score >= 60:
        return "硬件市场水平偏旧，部分新软件和重负载场景会显得吃力。"
    return "硬件市场水平明显落后，建议评估升级或更换。"


def _cpu_reason(name: str, threads: int) -> str:
    if _unknown_cpu(name):
        return "CPU 型号识别不完整，只能按线程数估算，不能给接近满分。"
    if threads >= 16:
        return f"{threads} 线程仍适合设计、开发和多任务，但不等于当前顶级 CPU。"
    if threads >= 8:
        return f"{threads} 线程属于主流水平，日常和轻专业工作仍可用。"
    return f"{threads} 线程在当前市场偏弱，多任务和专业软件会受限。"


def _gpu_reason(name: str, vram: float, has_gpu: bool) -> str:
    if not has_gpu:
        return "未检测到独立显卡或显卡详情，3D、剪辑和游戏市场分不能给高。"
    if vram >= 12:
        return f"{name}，{vram}GB 显存仍适合设计、普通 3D 和部分游戏，但是否高端取决于具体型号。"
    if vram >= 6:
        return f"{name}，{vram}GB 显存属于主流可用水平。"
    return f"{name}，显存 {vram}GB，在当前 3D、剪辑和游戏场景中偏入门。"


def _memory_reason(total: float) -> str:
    if total >= 64:
        return f"{total}GB 内存在当前市场属于很充裕配置。"
    if total >= 32:
        return f"{total}GB 内存高于普通办公、设计和开发需求，属于良好配置。"
    if total >= 16:
        return f"{total}GB 内存是当前主流水平。"
    return f"{total}GB 内存在当前市场偏小。"


def _disk_reason(total: float, has_health: bool) -> str:
    if total >= 900 and has_health:
        return "硬盘容量较充足，并读取到基础健康状态。"
    if total >= 900:
        return "硬盘容量较充足，但硬盘接口和 SMART 深度健康信息仍需完善。"
    return "硬盘容量或健康信息不完整，市场分保守处理。"
