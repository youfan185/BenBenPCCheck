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

    product = report.get("product", {})
    issues = product.get("problem_cards") or report.get("diagnosis", {}).get("main_issues", [])
    score = report.get("score", {})
    ip = report.get("ip_status", {})
    c_drive = next((d for d in report.get("disk_partitions", []) if str(d.get("drive", "")).upper().startswith("C:")), None)

    lines = [
        "BenBen 电脑卡顿分析报告",
        f"生成时间：{report.get('scan_time', '')}",
        f"电脑名称：{report.get('computer', {}).get('computer_name', '')}",
        f"系统版本：{report.get('computer', {}).get('os_name', '')} {report.get('computer', {}).get('system_type', '')}",
        "",
        "一、电脑现在怎么样",
        f"健康分：{score.get('health_score', score.get('total_score', 0))}/100",
        f"优化空间分：{score.get('optimization_score', 0)}/100",
        f"综合状态：{ip.get('display_name', '')}",
        f"一句话结论：{product.get('plain_summary', '')}",
        "",
        "二、当前最影响体验的问题",
    ]
    if issues:
        for i, issue in enumerate(issues[:5], start=1):
            if "evidence" in issue:
                lines.append(f"{i}. {issue.get('title', '')}")
                lines.append(f"   证据：{issue.get('evidence', '')}")
                lines.append(f"   影响：{issue.get('impact', '')}")
                lines.append(f"   建议：{issue.get('suggestion', '')}")
            else:
                lines.append(f"{i}. {issue.get('title', '')}：{issue.get('detail', '')}")
    else:
        lines.append("1. 未发现明显风险")

    lines += ["", "三、硬件哪里不够"]
    cpu = report.get("hardware", {}).get("cpu", {})
    mem = report.get("hardware", {}).get("memory", {})
    lines += [f"CPU：{cpu.get('name', '')}", f"内存：{mem.get('total_gb', 0)}GB，占用 {mem.get('usage_percent', 0)}%"]
    if c_drive:
        lines.append(f"C盘：剩余 {c_drive.get('free_gb', 0)}GB，占用 {c_drive.get('usage_percent', 0)}%")

    hardware = product.get("hardware_bottlenecks", [])
    for item in hardware:
        lines.append(f"- {item.get('name', '')}：{item.get('status', '')}。{item.get('suggestion', '')}")

    lines += ["", "四、我的常用软件跑得动吗"]
    for item in product.get("software_fit", []):
        lines.append(f"- {item.get('name', '')}：{item.get('summary', '')}")
        lines.append(f"  建议：{item.get('suggestion', '')}")

    lines += ["", "五、建议处理步骤"]
    tasks = product.get("optimization_tasks", [])
    if tasks:
        for i, task in enumerate(tasks, start=1):
            lines.append(f"{i}. [{task.get('group', '')}] {task.get('title', '')}：{task.get('expected_gain', '')}")
    else:
        lines.append("1. 暂未发现必须处理的事项，建议保持当前使用习惯并定期体检。")

    output.write_text("\n".join(lines), encoding="utf-8")
    return output
