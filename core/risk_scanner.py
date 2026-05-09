import subprocess
from datetime import datetime

import psutil


def scan_stability_risk(startup_items: list[dict] | None = None) -> dict:
    startup_items = startup_items or []
    boot_time = datetime.fromtimestamp(psutil.boot_time())
    uptime_hours = round((datetime.now() - boot_time).total_seconds() / 3600, 1)
    memory = psutil.virtual_memory()
    suspicious_startup = [
        item for item in startup_items
        if not item.get("path") or "\\temp\\" in str(item.get("path", "")).lower()
    ]
    items = [
        {
            "name": "系统运行时长",
            "status": f"{uptime_hours} 小时",
            "level": "warning" if uptime_hours > 240 else "ok",
            "suggestion": "长时间不重启时，建议先重启再判断是否仍然卡顿。",
        },
        {
            "name": "内存长期压力",
            "status": f"当前占用 {round(memory.percent, 1)}%",
            "level": "warning" if memory.percent > 85 else "ok",
            "suggestion": "长期超过 85% 时，优先减少后台或考虑升级内存。",
        },
        {
            "name": "可疑启动项",
            "status": f"{len(suspicious_startup)} 个",
            "level": "warning" if suspicious_startup else "ok",
            "suggestion": "路径为空或位于 Temp 的启动项需要确认来源，先禁用观察，不要直接删除。",
        },
        {
            "name": "硬盘健康",
            "status": "未检测",
            "level": "unknown",
            "suggestion": "当前轻量版暂未读取 SMART，后续建议增加硬盘健康与温度检测。",
        },
        _last_system_errors_item(),
    ]
    warnings = sum(1 for item in items if item.get("level") in {"warning", "unknown"})
    summary = "当前没有明显稳定性风险。" if warnings <= 1 else f"发现 {warnings} 个稳定性/风险关注项。"
    return {"summary": summary, "boot_time": boot_time.strftime("%Y-%m-%d %H:%M:%S"), "uptime_hours": uptime_hours, "risk_items": items}


def _last_system_errors_item() -> dict:
    try:
        result = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "(Get-WinEvent -FilterHashtable @{LogName='System'; Level=2; StartTime=(Get-Date).AddDays(-7)} -MaxEvents 20 -ErrorAction SilentlyContinue | Measure-Object).Count",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
            timeout=8,
        )
        count = int((result.stdout or "0").strip() or 0)
        return {
            "name": "近 7 天系统错误",
            "status": f"{count} 条",
            "level": "warning" if count >= 10 else "ok",
            "suggestion": "错误较多时建议查看事件查看器，优先排查驱动、磁盘和更新相关错误。",
        }
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return {
            "name": "近 7 天系统错误",
            "status": "未检测",
            "level": "unknown",
            "suggestion": "暂未读取到事件日志，后续可增强蓝屏和系统错误检查。",
        }
