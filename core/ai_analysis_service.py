from core.ai_client import AIClient
from core.ai_prompt_builder import build_ai_input, build_prompts
from core.ai_result_parser import apply_ai_result, build_local_ai_result, parse_ai_text
from core.key_manager import load_ai_config


def run_ai_analysis(report: dict, progress_callback=None) -> dict:
    def emit(message: str):
        if progress_callback:
            progress_callback(message)

    try:
        config = load_ai_config()
        if not config.get("enable_ai_analysis", True):
            raise RuntimeError("AI 分析已关闭，请在设置页开启后再重新体检。")

        emit("正在整理扫描摘要...")
        system_prompt, user_prompt = build_prompts(report)
        input_size = len(str(build_ai_input(report)))
        emit(f"AI 摘要已压缩，输入约 {input_size} 字符。")
        emit("正在连接 GPT 分析服务...")
        client = AIClient(config)
        emit("正在提交扫描结果给 GPT，最长等待约 45 秒...")
        raw_text = client.chat(system_prompt, user_prompt)
        emit(f"GPT 已返回内容，长度 {len(raw_text)} 字符，正在解析固定 JSON 结果...")
        try:
            result = parse_ai_text(raw_text)
        except Exception as parse_exc:
            preview = (raw_text or "").replace("\r", " ").replace("\n", " ")[:240]
            emit(f"GPT 返回内容预览：{preview or '<空内容>'}")
            raise parse_exc
        result["source"] = "ai"
        emit("GPT 分析完成")
        return {"success": True, "source": client.model, "message": f"{client.model} 分析成功", "result": result}
    except Exception as exc:
        message = f"AI 分析失败：{exc}"
        emit(message)
        fallback = build_local_ai_result(report, message)
        return {"success": False, "source": "local_fallback", "message": message, "result": fallback}


def analyze_report_with_ai(report: dict, progress=None) -> dict:
    if progress:
        progress("正在准备 AI 输入 JSON...")
    payload = run_ai_analysis(report, progress)
    report["ai_status"] = {k: payload.get(k) for k in ("success", "source", "message")}
    apply_ai_result(report, payload["result"])
    return report
