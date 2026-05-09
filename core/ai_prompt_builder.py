import json


SYSTEM_PROMPT = """你是 Windows 电脑诊断专家。
请只根据我提供的 JSON 输出诊断，不要猜测不存在的数据。
必须返回 JSON，不要输出 Markdown。

你需要输出：overall、hardware_market_review、software_smoothness_review、system_review、brief_report、optimization_guide。

一、硬件市场水平规则：
硬件市场水平只看硬件在当前市场中的档次，类似硬件天梯 / 跑分评估。
不要把当前是否卡顿、当前 CPU 占用、当前内存占用、系统缓存、后台进程算进硬件市场分。
硬件市场水平总分 100 = CPU 30 + 显卡 30 + 内存 15 + 硬盘 15 + 平台 10。
每个硬件必须独立给分，并说明原因。
如果硬件能满足当前使用，但不是当前顶级硬件，不允许给 95 分以上。
如果 CPU 型号识别不完整，不允许 CPU 分接近满分。
如果硬盘信息不完整，需要在硬盘评分原因里说明。

二、软件运行流畅度规则：
“软件运行流畅度”用于判断这台电脑运行当前常用软件是否流畅。
如果所有软件需求都是适配，且没有 weak_hardware，不允许输出“部分软件吃力”。
没有明显硬件短板时，状态必须是“常用软件能跑，多开时有压力”或“运行流畅，重度多开需注意”。
如果压力来自 Chrome、微信、QQ、PyCharm、Adobe 后台等累计内存，归类为“多软件叠加压力”，不要归类为“硬件跑不动”。

三、系统可用性规则：
如果 C 盘剩余空间大于 100GB，不要把 C 盘空间列为前三问题。
如果临时文件小于 5GB，不要把清理临时文件列为前三动作。
如果启动项数量不超过 12 个，不要夸大启动项问题。
可疑启动项只能建议核实或禁用观察，不要建议直接删除。

四、问题排序规则：
硬件市场水平明显落后 > 硬件无法支撑当前软件 > 多软件聚合占用过高 > 系统错误/可疑启动项/驱动风险 > 硬盘健康未知或异常 > 大文件堆积 > 普通后台 > 普通启动项 > 临时文件。
"""


def build_ai_input(report: dict) -> dict:
    compact = {
        "report_version": report.get("report_version"),
        "scan_time": report.get("scan_time"),
        "computer": report.get("computer", {}),
        "scores": report.get("scores", {}),
        "ai_input_summary": report.get("ai_input_summary", {}),
        "software": {
            "categories": report.get("software", {}).get("software_categories", []),
            "process_groups": report.get("software", {}).get("process_groups", [])[:10],
            "requirement_match": report.get("software", {}).get("software_requirement_match", []),
        },
        "storage": {
            "partitions": report.get("storage", {}).get("partitions", []),
            "large_folders": report.get("storage", {}).get("large_folders", [])[:10],
            "disk_health": report.get("storage", {}).get("disk_health", []),
        },
        "system": {
            "startup_count": len(report.get("system", {}).get("startup_items", [])),
            "settings": report.get("system", {}).get("settings", {}),
            "events": report.get("system", {}).get("system_events", {}),
        },
    }
    return compact


def build_prompts(report: dict) -> tuple[str, str]:
    user_prompt = "请根据下面 JSON 输出电脑诊断。只能使用 JSON 中已有数据，不要脑补。必须返回 JSON，不要返回 Markdown。\n\n"
    user_prompt += json.dumps(build_ai_input(report), ensure_ascii=False, indent=2)
    return SYSTEM_PROMPT, user_prompt


def build_ai_prompt(report: dict) -> str:
    system_prompt, user_prompt = build_prompts(report)
    return system_prompt + "\n\n" + user_prompt
