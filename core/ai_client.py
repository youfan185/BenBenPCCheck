import json

from openai import OpenAI

from core.key_manager import load_ai_config, validate_ai_config


REQUEST_TIMEOUT_SECONDS = 45
MAX_OUTPUT_TOKENS = 6000


class AIClient:
    def __init__(self, config: dict | None = None):
        cfg = config or load_ai_config()
        if "api_key" not in cfg:
            cfg["api_key"] = cfg.get("aihubmix_api_key", "")
        validate_ai_config(cfg)
        self.model = cfg["model"]
        self.base_url = cfg["base_url"].rstrip("/")
        self.source = cfg.get("source", "unknown")
        self.client = OpenAI(
            api_key=cfg["api_key"],
            base_url=self.base_url,
            timeout=REQUEST_TIMEOUT_SECONDS,
            max_retries=0,
        )

    def chat(self, system_prompt: str, user_prompt: str, max_tokens: int = MAX_OUTPUT_TOKENS) -> str:
        kwargs = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
            "max_completion_tokens": max_tokens,
        }
        try:
            response = self.client.chat.completions.create(**kwargs)
        except Exception as exc:
            message = str(exc)
            lower = message.lower()
            if "response_format" in message and "unsupported" in lower:
                kwargs.pop("response_format", None)
                response = self.client.chat.completions.create(**kwargs)
            elif "max_completion_tokens" in message and "unsupported" in lower:
                kwargs.pop("max_completion_tokens", None)
                kwargs["max_tokens"] = max_tokens
                response = self.client.chat.completions.create(**kwargs)
            else:
                raise
        choice = response.choices[0]
        content = choice.message.content or ""
        if not content.strip():
            finish_reason = getattr(choice, "finish_reason", "")
            raise ValueError(f"AI 返回内容为空，finish_reason={finish_reason}，请增大输出额度或换用更快的模型。")
        return content


def test_ai_connection(config: dict) -> tuple[bool, str]:
    try:
        client = AIClient(config)
        text = client.chat("你只返回 JSON，不要输出 Markdown。", '请只返回 JSON：{"ok": true}', max_tokens=40)
        clean = text.strip().removeprefix("```json").removeprefix("```JSON").removeprefix("```").removesuffix("```").strip()
        data = json.loads(clean)
        if data.get("ok") is True:
            return True, "连接成功"
        return False, "返回格式错误：没有解析到 ok=true"
    except Exception as exc:
        message = str(exc)
        lower = message.lower()
        if "401" in lower or "unauthorized" in lower or "api key" in lower:
            return False, f"Key 错误：{message}"
        if "quota" in lower or "insufficient" in lower or "429" in lower:
            return False, f"额度不足：{message}"
        if "model" in lower and ("not" in lower or "不存在" in lower):
            return False, f"模型不存在：{message}"
        if "timed out" in lower or "timeout" in lower:
            return False, f"请求超时：{message}"
        if "json" in lower:
            return False, f"返回格式错误：{message}"
        return False, f"网络或接口错误：{message}"
