import json
from datetime import datetime
from pathlib import Path

from config import APP_NAME, APP_VERSION, REPORT_DIR


def build_report_filename(computer_name: str, ext: str) -> str:
    now = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    safe_name = computer_name.replace(" ", "_") if computer_name else "PC"
    return f"BenBen_PC_Report_{safe_name}_{now}.{ext}"


def export_json(report: dict) -> Path:
    name = build_report_filename(report.get("computer", {}).get("computer_name", "PC"), "json")
    output = REPORT_DIR / name
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return output


def export_txt(report: dict) -> Path:
    name = build_report_filename(report.get("computer", {}).get("computer_name", "PC"), "txt")
    output = REPORT_DIR / name

    issues = report.get("diagnosis", {}).get("main_issues", [])
    score = report.get("score", {})
    ip = report.get("ip_status", {})
    c_drive = next((d for d in report.get("disk_partitions", []) if str(d.get("drive", "")).upper().startswith("C:")), None)

    lines = [
        "BenBen 电脑体检报告",
        f"生成时间：{report.get('scan_time', '')}",
        f"电脑名称：{report.get('computer', {}).get('computer_name', '')}",
        f"系统版本：{report.get('computer', {}).get('os_name', '')} {report.get('computer', {}).get('system_type', '')}",
        "",
        "一、电脑总分",
        f"总分：{score.get('total_score', 0)}/100",
        f"状态：{score.get('level', 'unknown')}",
        f"IP状态：{ip.get('display_name', '')}",
        "",
        "二、主要问题",
    ]
    if issues:
        for i, issue in enumerate(issues[:5], start=1):
            lines.append(f"{i}. {issue.get('title', '')}：{issue.get('detail', '')}")
    else:
        lines.append("1. 未发现明显风险")

    lines += ["", "三、硬件概览"]
    cpu = report.get("hardware", {}).get("cpu", {})
    mem = report.get("hardware", {}).get("memory", {})
    lines += [
        f"CPU：{cpu.get('name', '')}",
        f"内存：{mem.get('total_gb', 0)}GB，占用 {mem.get('usage_percent', 0)}%",
    ]
    if c_drive:
        lines.append(f"C盘：剩余 {c_drive.get('free_gb', 0)}GB，占用 {c_drive.get('usage_percent', 0)}%")

    output.write_text("\n".join(lines), encoding="utf-8")
    return output
