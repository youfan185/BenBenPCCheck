import winreg


UNINSTALL_KEYS = [
    (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Uninstall"),
    (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\Uninstall"),
    (winreg.HKEY_LOCAL_MACHINE, r"Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
]


def scan_installed_software() -> list[dict]:
    rows = []
    seen = set()
    for hive, key_path in UNINSTALL_KEYS:
        try:
            with winreg.OpenKey(hive, key_path) as root:
                for index in range(winreg.QueryInfoKey(root)[0]):
                    try:
                        sub_name = winreg.EnumKey(root, index)
                        with winreg.OpenKey(root, sub_name) as sub_key:
                            item = _read_uninstall_item(sub_key)
                    except OSError:
                        continue
                    name = item.get("name", "").strip()
                    if not name or _is_noise(name):
                        continue
                    normalized = (name.lower(), item.get("publisher", "").lower())
                    if normalized in seen:
                        continue
                    seen.add(normalized)
                    rows.append(item)
        except OSError:
            continue
    return sorted(rows, key=lambda item: item.get("name", "").lower())


def _read_uninstall_item(key) -> dict:
    return {
        "name": _query_value(key, "DisplayName"),
        "version": _query_value(key, "DisplayVersion"),
        "publisher": _query_value(key, "Publisher"),
        "install_location": _query_value(key, "InstallLocation"),
        "uninstall_string": _query_value(key, "UninstallString"),
        "estimated_size_mb": _estimated_size_mb(_query_value(key, "EstimatedSize")),
    }


def _query_value(key, name: str):
    try:
        return winreg.QueryValueEx(key, name)[0]
    except OSError:
        return ""


def _estimated_size_mb(value) -> int:
    try:
        return int(value) // 1024
    except (TypeError, ValueError):
        return 0


def _is_noise(name: str) -> bool:
    lower = name.lower()
    noise = ("update for", "security update", "hotfix", "redistributable", "runtime")
    return any(item in lower for item in noise)
