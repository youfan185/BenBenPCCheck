import ctypes
import subprocess
import winreg


def scan_windows_settings() -> dict:
    items = [
        _power_plan_item(),
        _hibernation_item(),
        _fast_startup_item(),
        _windows_update_item(),
        _search_index_item(),
        _onedrive_item(),
    ]
    attention = sum(1 for item in items if item.get("level") in {"warning", "unknown"})
    if attention:
        summary = f"发现 {attention} 个 Windows 设置建议关注。"
    else:
        summary = "Windows 常见设置未发现明显异常。"
    return {"summary": summary, "items": items}


def _power_plan_item() -> dict:
    try:
        result = subprocess.run(
            ["powercfg", "/getactivescheme"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
            timeout=4,
        )
        text = result.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        text = ""
    level = "warning" if "节能" in text or "Power saver" in text else "ok" if text else "unknown"
    return {
        "name": "电源模式",
        "value": text or "未知",
        "level": level,
        "impact": "节能模式可能限制 CPU 性能，设计、剪辑、开发时会更明显。",
        "suggestion": "需要高性能工作时，可切换到平衡或高性能。不要长期盲目改系统服务。",
    }


def _hibernation_item() -> dict:
    enabled = _reg_dword(winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\Power", "HibernateEnabled")
    if enabled is None:
        value, level = "未知", "unknown"
    else:
        value, level = ("已开启", "ok") if enabled else ("已关闭", "ok")
    return {
        "name": "休眠",
        "value": value,
        "level": level,
        "impact": "休眠文件会占用一部分 C 盘空间，但也支持休眠/快速启动能力。",
        "suggestion": "空间极度紧张时再考虑关闭；普通用户不建议为了省一点空间乱改。",
    }


def _fast_startup_item() -> dict:
    enabled = _reg_dword(winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\Session Manager\Power", "HiberbootEnabled")
    if enabled is None:
        value, level = "未知", "unknown"
    else:
        value, level = ("已开启", "ok") if enabled else ("已关闭", "ok")
    return {
        "name": "快速启动",
        "value": value,
        "level": level,
        "impact": "快速启动通常能加快开机，但偶尔会让驱动状态长期保留。",
        "suggestion": "如果遇到设备异常，可尝试完整重启；不要随意批量修改电源策略。",
    }


def _windows_update_item() -> dict:
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", "Get-Service wuauserv | Select-Object -ExpandProperty Status"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
            timeout=5,
        )
        status = result.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        status = ""
    return {
        "name": "Windows 更新服务",
        "value": status or "未知",
        "level": "ok" if status else "unknown",
        "impact": "更新服务异常可能导致更新卡住或长期后台重试。",
        "suggestion": "如果更新长期失败，优先使用系统设置里的疑难解答，不建议直接删除更新目录。",
    }


def _search_index_item() -> dict:
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", "Get-Service WSearch | Select-Object -ExpandProperty Status"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
            timeout=5,
        )
        status = result.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        status = ""
    return {
        "name": "搜索索引",
        "value": status or "未知",
        "level": "ok" if status else "unknown",
        "impact": "索引服务在首次建立索引或文件很多时可能有短时占用。",
        "suggestion": "只有长期高占用时再调整索引范围，不建议直接关闭系统搜索。",
    }


def _onedrive_item() -> dict:
    user = _reg_string(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\OneDrive", "UserFolder")
    running = _is_process_running("OneDrive.exe")
    if user or running:
        value, level = "可能正在使用", "ok"
    else:
        value, level = "未检测到运行", "ok"
    return {
        "name": "OneDrive 同步",
        "value": value,
        "level": level,
        "impact": "同步桌面/文档时可能占用网络、磁盘和后台资源。",
        "suggestion": "如果桌面文件很多且同步慢，建议检查 OneDrive 同步范围。",
    }


def _reg_dword(hive, path: str, name: str):
    try:
        with winreg.OpenKey(hive, path) as key:
            value, _ = winreg.QueryValueEx(key, name)
            return int(value)
    except OSError:
        return None


def _reg_string(hive, path: str, name: str) -> str:
    try:
        with winreg.OpenKey(hive, path) as key:
            value, _ = winreg.QueryValueEx(key, name)
            return str(value)
    except OSError:
        return ""


def _is_process_running(name: str) -> bool:
    try:
        result = subprocess.run(
            ["tasklist", "/FI", f"IMAGENAME eq {name}"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
            timeout=4,
        )
        return name.lower() in result.stdout.lower()
    except (OSError, subprocess.TimeoutExpired):
        return False
