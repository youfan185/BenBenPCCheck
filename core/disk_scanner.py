from pathlib import Path

import psutil


def list_partitions() -> list[dict]:
    rows = []
    for p in psutil.disk_partitions(all=False):
        if not p.fstype:
            continue
        try:
            usage = psutil.disk_usage(p.mountpoint)
        except PermissionError:
            continue
        rows.append(
            {
                "drive": p.device.replace("\\", ""),
                "mountpoint": p.mountpoint,
                "total_gb": round(usage.total / (1024**3), 1),
                "used_gb": round(usage.used / (1024**3), 1),
                "free_gb": round(usage.free / (1024**3), 1),
                "usage_percent": round(usage.percent, 1),
                "risk_level": c_drive_risk(usage.free / (1024**3)) if p.device.upper().startswith("C:") else "good",
            }
        )
    return rows


def c_drive_risk(free_gb: float) -> str:
    if free_gb > 80:
        return "good"
    if free_gb > 40:
        return "normal"
    if free_gb > 20:
        return "low"
    if free_gb > 10:
        return "warning"
    return "critical"


def dir_size_gb(path: Path) -> float:
    if not path.exists():
        return 0.0
    total = 0
    for f in path.rglob("*"):
        if f.is_file():
            try:
                total += f.stat().st_size
            except OSError:
                continue
    return round(total / (1024**3), 2)


def scan_common_folders(progress=None) -> list[dict]:
    home = Path.home()
    candidates = [
        ("Desktop", home / "Desktop", "desktop_files", False),
        ("Downloads", home / "Downloads", "download_files", False),
        ("Documents", home / "Documents", "documents", False),
        ("User Temp", home / "AppData/Local/Temp", "temp", True),
        ("Chrome Cache", home / "AppData/Local/Google/Chrome/User Data/Default/Cache", "browser_cache", False),
        ("Edge Cache", home / "AppData/Local/Microsoft/Edge/User Data/Default/Cache", "browser_cache", False),
        ("WeChat Files", home / "Documents/WeChat Files", "wechat_cache", False),
        ("Tencent Files", home / "Documents/Tencent Files", "qq_cache", False),
        ("Adobe Cache", home / "AppData/Roaming/Adobe", "adobe_cache", False),
    ]
    rows = []
    for name, path, category, safe in candidates:
        if progress:
            progress(f"正在扫描 {name}: {path}")
        size_gb = dir_size_gb(path)
        if size_gb <= 0:
            continue
        rows.append(
            {
                "name": name,
                "path": str(path),
                "size_gb": size_gb,
                "category": category,
                "safe_to_clean": safe,
                "suggestion": "可安全清理" if safe else "建议先确认重要文件后清理",
            }
        )
    return sorted(rows, key=lambda x: x["size_gb"], reverse=True)
