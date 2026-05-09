import json
import subprocess


def scan_disk_health() -> list[dict]:
    command = [
        "powershell",
        "-NoProfile",
        "-Command",
        "Get-CimInstance Win32_DiskDrive | Select-Object Model,MediaType,InterfaceType,Status,Size | ConvertTo-Json",
    ]
    try:
        result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="ignore", timeout=8)
    except (OSError, subprocess.TimeoutExpired):
        return [{"status": "unknown", "summary": "硬盘健康信息未检测到，建议后续补充 SMART 检查。"}]
    if not result.stdout.strip():
        return [{"status": "unknown", "summary": "硬盘健康信息未检测到，建议后续补充 SMART 检查。"}]
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        return [{"status": "unknown", "summary": "硬盘健康信息解析失败。"}]
    if isinstance(data, dict):
        data = [data]
    rows = []
    for item in data:
        rows.append(
            {
                "model": item.get("Model", ""),
                "media_type": item.get("MediaType") or item.get("InterfaceType") or "Unknown",
                "interface_type": item.get("InterfaceType", ""),
                "status": item.get("Status") or "Unknown",
                "size_gb": _size_gb(item.get("Size")),
                "summary": "SMART 深度信息未读取，仅记录 Windows 磁盘状态。",
            }
        )
    return rows


def _size_gb(value) -> float:
    try:
        return round(int(value) / (1024**3), 1)
    except (TypeError, ValueError):
        return 0.0
