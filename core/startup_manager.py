import winreg


def get_startup_items() -> list[dict]:
    rows = []
    key_paths = [
        (winreg.HKEY_CURRENT_USER, r"Software\\Microsoft\\Windows\\CurrentVersion\\Run", "HKCU Run"),
        (winreg.HKEY_LOCAL_MACHINE, r"Software\\Microsoft\\Windows\\CurrentVersion\\Run", "HKLM Run"),
    ]
    for hive, key_path, source in key_paths:
        try:
            with winreg.OpenKey(hive, key_path) as key:
                i = 0
                while True:
                    try:
                        name, value, _ = winreg.EnumValue(key, i)
                        rows.append(
                            {
                                "name": name,
                                "path": str(value),
                                "source": source,
                                "status": "enabled",
                                "recommendation": recommend(name),
                            }
                        )
                        i += 1
                    except OSError:
                        break
        except OSError:
            continue
    return rows


def recommend(name: str) -> str:
    n = name.lower()
    keep_keywords = ["defender", "security", "driver", "audio", "nvidia", "amd", "intel"]
    if any(k in n for k in keep_keywords):
        return "keep"
    return "optional_disable"
