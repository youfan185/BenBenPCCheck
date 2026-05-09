from core.software_rules import classify_software_name


GROUP_RULES = [
    ("Chrome", ("chrome.exe", "google chrome")),
    ("Edge", ("msedge.exe", "microsoft edge")),
    ("微信", ("wechat.exe", "weixin", "wechatapp")),
    ("QQ", ("qq.exe", "tim.exe", "tencent")),
    ("Codex", ("codex",)),
    ("Cursor", ("cursor.exe",)),
    ("VS Code", ("code.exe", "visual studio code")),
    ("PyCharm", ("pycharm",)),
    ("Photoshop", ("photoshop",)),
    ("Illustrator", ("illustrator",)),
    ("CorelDRAW", ("coreldraw",)),
    ("Premiere Pro", ("premiere",)),
    ("After Effects", ("afterfx",)),
    ("剪映", ("jianying", "capcut",)),
    ("Blender", ("blender",)),
    ("百度网盘", ("baidunetdisk",)),
    ("OneDrive", ("onedrive",)),
    ("千牛", ("qianniu", "千牛", "aliworkbench")),
    ("AliRender", ("alirender",)),
    ("Adobe 后台", ("creative cloud", "adobe")),
]


def group_processes(process_rows: list[dict]) -> list[dict]:
    groups: dict[str, dict] = {}
    for process in process_rows:
        group_name = _group_name(process)
        group = groups.setdefault(
            group_name,
            {
                "name": group_name,
                "category": classify_software_name(group_name),
                "process_count": 0,
                "memory_mb": 0.0,
                "cpu_percent": 0.0,
                "paths": set(),
                "processes": [],
            },
        )
        group["process_count"] += 1
        group["memory_mb"] += float(process.get("memory_mb") or 0)
        group["cpu_percent"] += float(process.get("cpu_percent") or 0)
        if process.get("path"):
            group["paths"].add(process.get("path"))
        group["processes"].append(
            {
                "name": process.get("name", ""),
                "pid": process.get("pid"),
                "memory_mb": process.get("memory_mb", 0),
                "cpu_percent": process.get("cpu_percent", 0),
            }
        )

    rows = []
    for group in groups.values():
        group["memory_mb"] = round(group["memory_mb"], 1)
        group["cpu_percent"] = round(group["cpu_percent"], 1)
        group["paths"] = sorted(group["paths"])[:5]
        group["pressure_level"] = _pressure_level(group)
        group["explain"] = _explain_group(group)
        rows.append(group)
    rows.sort(key=lambda item: (item["memory_mb"], item["process_count"]), reverse=True)
    return rows


def _group_name(process: dict) -> str:
    text = f"{process.get('name', '')} {process.get('path', '')}".lower()
    for name, keywords in GROUP_RULES:
        if any(keyword in text for keyword in keywords):
            return name
    raw = process.get("name") or "未知进程"
    return raw.removesuffix(".exe").removesuffix(".EXE")


def _pressure_level(group: dict) -> str:
    memory = float(group.get("memory_mb") or 0)
    count = int(group.get("process_count") or 0)
    if memory >= 2048 or count >= 20:
        return "高"
    if memory >= 800 or count >= 8:
        return "中"
    return "低"


def _explain_group(group: dict) -> str:
    if group["process_count"] <= 1:
        return f"单进程占用 {group['memory_mb']}MB。"
    return f"已按应用聚合 {group['process_count']} 个进程，累计占用 {group['memory_mb']}MB。"
