from core.ai_client import AIClient
from core.ai_prompt_builder import build_prompts
from core.ai_result_parser import apply_ai_result, build_local_ai_result, parse_ai_text


def run_ai_analysis(report: dict, progress_callback=None) -> dict:
    def emit(message: str):
        if progress_callback:
            progress_callback(message)

    try:
        emit("正在整理扫描摘要...")
        system_prompt, user_prompt = build_prompts(report)
        emit("正在连接 GPT 分析服务...")
        client = AIClient()
        emit("正在提交扫描结果给 GPT...")
        raw_text = client.chat(system_prompt, user_prompt)
        emit("正在解析 GPT 分析结果...")
        result = parse_ai_text(raw_text)
        emit("GPT 分析完成")
        return {"success": True, "source": client.model, "message": f"{client.model} 分析成功", "result": result}
    except Exception as exc:
        emit(f"AI 分析失败：{exc}")
        fallback = build_local_ai_result(report, str(exc))
        return {"success": False, "source": "local_fallback", "message": f"AI 分析失败，已使用本地规则：{exc}", "result": fallback}


def analyze_report_with_ai(report: dict, progress=None) -> dict:
    if progress:
        progress("正在准备 AI 输入 JSON...")
    payload = run_ai_analysis(report, progress)
    report["ai_status"] = {k: payload.get(k) for k in ("success", "source", "message")}
    apply_ai_result(report, payload["result"])
    return report
