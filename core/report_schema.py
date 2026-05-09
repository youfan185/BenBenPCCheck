from core.software_rules import analyze_software_fit


def apply_v2_schema(report: dict, hardware_score: dict, system_score: dict) -> dict:
    software_fit = analyze_software_fit(report)
    report["report_version"] = "2.0"
    report["software_version"] = "2.0.0"
    report.setdefault("software", {})
    report.setdefault("system", {})
    report.setdefault("storage", {})

    report["software"].update(
        {
            "installed_software": report.get("installed_software", []),
            "running_processes": report.get("process_list", []),
            "software_usage": report.get("software_usage", {}),
            "software_categories": software_fit.get("detected_categories", []),
            "process_groups": report.get("process_groups", []),
            "software_requirement_match": software_fit.get("software_requirement_match", []),
        }
    )
    report["system"].update(
        {
            "windows": report.get("computer", {}),
            "startup_items": report.get("startup_items", {}).get("items", []),
            "background_summary": report.get("processes", {}),
            "system_events": report.get("stability_risk", {}),
            "settings": report.get("windows_settings", {}),
        }
    )
    report["storage"].update(
        {
            "partitions": report.get("disk_partitions", []),
            "large_folders": report.get("large_folders", []),
            "cleanable_items": report.get("cleanable_items", []),
            "app_cache": [i for i in report.get("large_folders", []) if "cache" in i.get("category", "")],
            "chat_files": [i for i in report.get("large_folders", []) if i.get("category") in {"wechat_cache", "qq_cache"}],
            "disk_health": report.get("disk_health", []),
        }
    )
    total = round(hardware_score["score"] * 0.30 + software_fit["score"] * 0.40 + system_score["score"] * 0.30)
    report["scores"] = {
        "hardware_market_score": hardware_score,
        "software_smoothness_score": software_fit,
        "system_usability_score": system_score,
        "total_score": total,
    }
    report["scores"]["hardware_score"] = hardware_score
    report["scores"]["software_fit_score"] = software_fit
    report["ai_input_summary"] = {
        "detected_use_cases": software_fit.get("detected_use_cases", []),
        "main_bottlenecks": _top_bottlenecks(hardware_score, software_fit, system_score),
        "risk_flags": _risk_flags(report),
    }
    return report


def _top_bottlenecks(hardware_score: dict, software_fit: dict, system_score: dict) -> list[str]:
    rows = []
    rows.extend([item for item in software_fit.get("bottlenecks", []) if item != "暂未发现明显硬件短板"])
    if hardware_score.get("score", 100) < 70:
        rows.append(hardware_score.get("summary", "硬件状态需要关注"))
    if system_score.get("score", 100) < 70:
        rows.append(system_score.get("summary", "系统可用性需要整理"))
    return list(dict.fromkeys(rows))[:5]


def _risk_flags(report: dict) -> list[str]:
    flags = []
    startup = report.get("startup_items", {})
    if startup.get("total_count", 0) >= 20:
        flags.append("启动项较多")
    if report.get("stability_risk", {}).get("risk_items"):
        flags.append("存在稳定性/可疑项需要核实")
    if not report.get("disk_health"):
        flags.append("硬盘健康信息缺失")
    return flags
