import json
import os
import sys
from pathlib import Path


DEFAULT_BASE_URL = "https://aihubmix.com/v1"
DEFAULT_MODEL = "gpt-5.5"
CONFIG_FILE_NAME = "config.local.json"
PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROJECT_CONFIG_PATH = PROJECT_ROOT / CONFIG_FILE_NAME


class AIConfigError(Exception):
    pass


def writable_config_path() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent / CONFIG_FILE_NAME
    return PROJECT_CONFIG_PATH


def _config_candidates() -> list[Path]:
    candidates = []
    if getattr(sys, "frozen", False):
        candidates.append(Path(sys.executable).resolve().parent / CONFIG_FILE_NAME)
    candidates.append(Path.cwd() / CONFIG_FILE_NAME)
    candidates.append(PROJECT_CONFIG_PATH)
    return list(dict.fromkeys(candidates))


def load_ai_config() -> dict:
    env_key = os.getenv("AIHUBMIX_API_KEY", "").strip()
    config = {
        "aihubmix_api_key": env_key,
        "api_key": env_key,
        "base_url": os.getenv("AIHUBMIX_BASE_URL", DEFAULT_BASE_URL).strip() or DEFAULT_BASE_URL,
        "model": os.getenv("AIHUBMIX_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL,
        "enable_ai_analysis": True,
        "source": "env" if env_key else "default",
        "path": "",
    }

    for local_path in _config_candidates():
        if not local_path.exists():
            continue
        try:
            local = json.loads(local_path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise AIConfigError(f"读取 config.local.json 失败：{exc}") from exc

        local_key = str(local.get("aihubmix_api_key") or local.get("api_key") or "").strip()
        config.update(
            {
                "aihubmix_api_key": local_key,
                "api_key": local_key,
                "base_url": str(local.get("base_url") or DEFAULT_BASE_URL).strip(),
                "model": str(local.get("model") or DEFAULT_MODEL).strip(),
                "enable_ai_analysis": bool(local.get("enable_ai_analysis", True)),
                "source": "config.local.json",
                "path": str(local_path),
            }
        )
        break

    return config


def save_ai_config(config: dict) -> Path:
    path = writable_config_path()
    payload = {
        "aihubmix_api_key": str(config.get("aihubmix_api_key") or config.get("api_key") or "").strip(),
        "base_url": str(config.get("base_url") or DEFAULT_BASE_URL).strip(),
        "model": str(config.get("model") or DEFAULT_MODEL).strip(),
        "enable_ai_analysis": bool(config.get("enable_ai_analysis", True)),
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def validate_ai_config(config: dict) -> None:
    if not config.get("enable_ai_analysis", True):
        raise AIConfigError("AI 分析已关闭，请在设置页开启后再重新体检。")
    if not str(config.get("api_key") or config.get("aihubmix_api_key") or "").strip():
        raise AIConfigError("未配置 AI Key，请在设置页填写并保存。")
    if not str(config.get("base_url") or "").strip():
        raise AIConfigError("未配置 Base URL。")
    if not str(config.get("model") or "").strip():
        raise AIConfigError("未配置模型 ID。")


def mask_key(key: str) -> str:
    key = str(key or "").strip()
    if not key:
        return "未配置"
    if len(key) <= 10:
        return "****"
    return key[:6] + "****" + key[-4:]
