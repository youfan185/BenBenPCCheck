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
    issues = product.get("top3_experience_issues") or report.get("top3_experience_issues") or product.get("problem_cards") or report.get("diagnosis", {}).get("main_issues", [])
    score = report.get("score", {})
    ip = report.get("ip_status", {})
    emotion = product.get("current_emotion") or report.get("current_emotion", {})
    scores = report.get("scores", {})
    dimensions = product.get("six_dimensions") or product.get("four_dimension_score") or report.get("six_dimensions", {})
    c_drive = next((d for d in report.get("disk_partitions", []) if str(d.get("drive", "")).upper().startswith("C:")), None)

    lines = [
        "BenBen AI 电脑诊断报告",
        f"生成时间：{report.get('scan_time', '')}",
        f"电脑名称：{report.get('computer', {}).get('computer_name', '')}",
        f"系统版本：{report.get('computer', {}).get('os_name', '')} {report.get('computer', {}).get('system_type', '')}",
        "",
        "一、电脑现在怎么样",
        f"综合参考分：{scores.get('total_score', score.get('total_score', score.get('health_score', 0)))}/100",
        f"硬件状态：{scores.get('hardware_score', {}).get('score', '--')}/100，{scores.get('hardware_score', {}).get('status', '')}",
        f"常用软件适配：{scores.get('software_fit_score', {}).get('score', '--')}/100，{scores.get('software_fit_score', {}).get('status', '')}",
        f"系统可用性：{scores.get('system_usability_score', {}).get('score', '--')}/100，{scores.get('system_usability_score', {}).get('status', '')}",
        f"综合状态：{emotion.get('status') or ip.get('display_name', '')}",
        f"一句话结论：{product.get('plain_summary', '') or emotion.get('message', '')}",
        "",
        "二、三大核心结论",
    ]
    for key, title in [
        ("hardware_score", "硬件是否还 OK"),
        ("software_fit_score", "常用软件是否跑得动"),
        ("system_usability_score", "系统环境是否拖后腿"),
    ]:
        item = scores.get(key, {})
        lines.append(f"{title}：{item.get('score', '--')}分，{item.get('status', '')}。{item.get('summary', '')}")
    lines += ["", "三、详细维度参考"]
    for key, title in [
        ("space", "空间"),
        ("hardware", "硬件"),
        ("common_software", "常用软件"),
        ("system_background", "后台自启"),
        ("windows_settings", "Windows 设置"),
        ("stability_risk", "稳定风险"),
    ]:
        item = dimensions.get(key, {})
        lines.append(f"{title}：{item.get('score', '--')}分，{item.get('status', '')}。{item.get('summary', '')}")
        evidence = item.get("evidence", [])
        if evidence:
            lines.append(f"   证据：{'；'.join(evidence[:3])}")
    lines += [
        "",
        "四、当前最影响体验的问题",
    ]
    if issues:
        for i, issue in enumerate(issues[:5], start=1):
            if "why" in issue:
                lines.append(f"{i}. {issue.get('title', '')}")
                lines.append(f"   原因：{issue.get('why', '')}")
                lines.append(f"   影响：{issue.get('impact', '')}")
                lines.append(f"   建议：{issue.get('action', '')}")
            elif "evidence" in issue:
                lines.append(f"{i}. {issue.get('title', '')}")
                lines.append(f"   证据：{issue.get('evidence', '')}")
                lines.append(f"   影响：{issue.get('impact', '')}")
                lines.append(f"   建议：{issue.get('suggestion', '')}")
            else:
                lines.append(f"{i}. {issue.get('title', '')}：{issue.get('detail', '')}")
    else:
        lines.append("1. 未发现明显风险")

    lines += ["", "五、硬件哪里不够"]
    cpu = report.get("hardware", {}).get("cpu", {})
    mem = report.get("hardware", {}).get("memory", {})
    lines += [f"CPU：{cpu.get('name', '')}", f"内存：{mem.get('total_gb', 0)}GB，占用 {mem.get('usage_percent', 0)}%"]
    if c_drive:
        lines.append(f"C盘：剩余 {c_drive.get('free_gb', 0)}GB，占用 {c_drive.get('usage_percent', 0)}%")

    hardware = product.get("hardware_bottlenecks", [])
    for item in hardware:
        lines.append(f"- {item.get('name', '')}：{item.get('status', '')}。{item.get('suggestion', '')}")

    lines += ["", "六、我的常用软件跑得动吗"]
    profile = product.get("user_software_profile") or report.get("user_software_profile", [])
    if profile:
        lines.append("常用软件画像：" + "、".join(item.get("name", "") for item in profile[:8]))
    for item in product.get("software_fit", []):
        lines.append(f"- {item.get('name', '')}：{item.get('summary', '')}（适配 {item.get('fit_score', '--')}分）")
        lines.append(f"  建议：{item.get('suggestion', '')}")
    for item in scores.get("software_fit_score", {}).get("multi_app_pressure", []):
        lines.append(f"- 多开压力：{item}")

    lines += ["", "七、建议处理步骤"]
    tasks = product.get("optimization_tasks", [])
    if tasks:
        for i, task in enumerate(tasks, start=1):
            lines.append(f"{i}. [{task.get('group', '')}] {task.get('title', '')}：{task.get('expected_gain', '')}")
    else:
        lines.append("1. 暂未发现必须处理的事项，建议保持当前使用习惯并定期体检。")

    output.write_text("\n".join(lines), encoding="utf-8")
    return output
