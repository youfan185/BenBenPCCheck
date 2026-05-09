from openai import OpenAI

from core.key_manager import load_ai_config, validate_ai_config


class AIClient:
    def __init__(self):
        cfg = load_ai_config()
        validate_ai_config(cfg)
        self.model = cfg["model"]
        self.base_url = cfg["base_url"].rstrip("/")
        self.source = cfg.get("source", "unknown")
        self.client = OpenAI(api_key=cfg["api_key"], base_url=self.base_url)

    def chat(self, system_prompt: str, user_prompt: str) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
        )
        return response.choices[0].message.content or ""
