from pathlib import Path

from core.disk_scanner import dir_size_gb


def scan_cleanable_items(progress=None) -> list[dict]:
    home = Path.home()
    targets = [
        ("Windows Temp", Path("C:/Windows/Temp"), "safe", True),
        ("User Temp", home / "AppData/Local/Temp", "safe", True),
        ("Recycle Bin", Path("C:/$Recycle.Bin"), "need_confirm", False),
    ]
    rows = []
    for name, path, risk, selected in targets:
        if progress:
            progress(f"正在估算可清理项 {name}: {path}")
        size = dir_size_gb(path)
        if size <= 0:
            continue
        rows.append(
            {
                "name": name,
                "path": str(path),
                "size_gb": size,
                "risk": risk,
                "default_selected": selected,
            }
        )
    return rows
