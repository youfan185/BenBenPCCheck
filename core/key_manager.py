import json
import os
import sys
from pathlib import Path


DEFAULT_BASE_URL = "https://aihubmix.com/v1"
DEFAULT_MODEL = "gpt-5.5"
PROJECT_CONFIG_PATH = Path(__file__).resolve().parents[1] / "config.local.json"


def _config_candidates() -> list[Path]:
    candidates = []
    if getattr(sys, "frozen", False):
        candidates.append(Path(sys.executable).resolve().parent / "config.local.json")
    candidates.append(Path.cwd() / "config.local.json")
    candidates.append(PROJECT_CONFIG_PATH)
    return list(dict.fromkeys(candidates))


class AIConfigError(Exception):
    pass


def load_ai_config() -> dict:
    env_key = os.getenv("AIHUBMIX_API_KEY", "").strip()
    config = {
        "api_key": env_key,
        "base_url": os.getenv("AIHUBMIX_BASE_URL", DEFAULT_BASE_URL).strip(),
        "model": os.getenv("AIHUBMIX_MODEL", DEFAULT_MODEL).strip(),
        "source": "env" if env_key else "none",
    }

    for local_path in _config_candidates():
        if not local_path.exists():
            continue
        try:
            local = json.loads(local_path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise AIConfigError(f"读取 config.local.json 失败：{exc}") from exc
        local_key = str(local.get("aihubmix_api_key") or local.get("api_key") or "").strip()
        if local_key:
            config["api_key"] = local_key
            config["source"] = str(local_path)
        config["base_url"] = str(local.get("base_url") or config["base_url"]).strip()
        config["model"] = str(local.get("model") or config["model"]).strip()
        break

    return config


def validate_ai_config(config: dict) -> None:
    if not config.get("api_key"):
        raise AIConfigError("未配置 AI Key，请在项目根目录创建 config.local.json")
    if not config.get("base_url"):
        raise AIConfigError("未配置 base_url")
    if not config.get("model"):
        raise AIConfigError("未配置 model")


def mask_key(key: str) -> str:
    if not key:
        return "未配置"
    if len(key) <= 10:
        return "****"
    return key[:6] + "****" + key[-4:]
