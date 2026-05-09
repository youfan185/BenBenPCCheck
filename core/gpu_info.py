import csv
import json
import subprocess


def get_gpu_info() -> tuple[list[dict], dict]:
    for getter in (_get_gpu_by_nvidia_smi, _get_gpu_by_powershell, _get_gpu_by_wmic):
        gpus = getter()
        if gpus:
            return gpus, {"status": "ok", "message": "已读取到显卡信息。"}
    return [], {
        "status": "not_detected",
        "message": "暂未读取到显卡信息，无法判断 3D、AI 生图和视频剪辑性能。",
    }


def _get_gpu_by_powershell() -> list[dict]:
    command = [
        "powershell",
        "-NoProfile",
        "-Command",
        "Get-CimInstance Win32_VideoController | "
        "Select-Object Name,AdapterRAM,DriverVersion,VideoProcessor | ConvertTo-Json",
    ]
    try:
        result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="ignore", timeout=8)
    except (OSError, subprocess.TimeoutExpired):
        return []
    text = result.stdout.strip()
    if not text:
        return []
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return []
    if isinstance(data, dict):
        data = [data]
    rows = []
    for item in data:
        name = item.get("Name") or item.get("VideoProcessor") or ""
        if not name:
            continue
        rows.append(
            {
                "name": name,
                "vram_gb": _vram_to_gb(item.get("AdapterRAM")),
                "driver_version": item.get("DriverVersion") or "",
                "vendor": _vendor_from_name(name),
                "source": "powershell-cim",
                "status": "detected",
            }
        )
    return rows


def _get_gpu_by_wmic() -> list[dict]:
    command = ["wmic", "path", "win32_VideoController", "get", "name,AdapterRAM,DriverVersion", "/format:csv"]
    try:
        result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="ignore", timeout=8)
    except (OSError, subprocess.TimeoutExpired):
        return []
    if result.returncode != 0 or not result.stdout.strip():
        return []
    rows = []
    for line in result.stdout.splitlines():
        parts = [part.strip() for part in line.split(",")]
        if len(parts) < 4 or parts[0].lower() == "node":
            continue
        name = parts[3]
        if not name:
            continue
        rows.append(
            {
                "name": name,
                "vram_gb": _vram_to_gb(parts[1]),
                "driver_version": parts[2],
                "vendor": _vendor_from_name(name),
                "source": "wmic",
                "status": "detected",
            }
        )
    return rows


def _get_gpu_by_nvidia_smi() -> list[dict]:
    command = [
        "nvidia-smi",
        "--query-gpu=name,memory.total,driver_version,temperature.gpu,utilization.gpu",
        "--format=csv,noheader,nounits",
    ]
    try:
        result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="ignore", timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        return []
    if result.returncode != 0 or not result.stdout.strip():
        return []
    rows = []
    for parts in csv.reader(result.stdout.splitlines()):
        if len(parts) < 3:
            continue
        name = parts[0].strip()
        try:
            vram_gb = round(float(parts[1].strip()) / 1024, 1)
        except ValueError:
            vram_gb = 0
        rows.append(
            {
                "name": name,
                "vram_gb": vram_gb,
                "driver_version": parts[2].strip(),
                "temperature_c": _safe_float(parts[3]) if len(parts) > 3 else None,
                "utilization_percent": _safe_float(parts[4]) if len(parts) > 4 else None,
                "vendor": "NVIDIA",
                "source": "nvidia-smi",
                "status": "detected",
            }
        )
    return rows


def _vram_to_gb(value) -> float:
    try:
        raw = int(value)
        return round(raw / (1024**3), 1) if raw > 0 else 0
    except (TypeError, ValueError, OverflowError):
        return 0


def _vendor_from_name(name: str) -> str:
    text = name.lower()
    if "nvidia" in text or "geforce" in text or "rtx" in text or "gtx" in text:
        return "NVIDIA"
    if "amd" in text or "radeon" in text:
        return "AMD"
    if "intel" in text or "iris" in text or "uhd" in text:
        return "Intel"
    return "Unknown"


def _safe_float(value: str) -> float | None:
    try:
        return float(value.strip())
    except (TypeError, ValueError):
        return None
