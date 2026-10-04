from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os

from dotenv import load_dotenv

APP_NAME = "LiveInterpreter"
MODEL = "gpt-realtime-translate"
REALTIME_URL = "wss://api.openai.com/v1/realtime/translations?model=gpt-realtime-translate"
INPUT_SAMPLE_RATE = 24_000
DEVICE_SAMPLE_RATE = 48_000
BLOCK_MS = 20
BLOCK_FRAMES_48K = DEVICE_SAMPLE_RATE * BLOCK_MS // 1000
ENV_PATH = Path(__file__).resolve().parents[2] / ".env"
APP_ROOT = Path(__file__).resolve().parents[2]
LOCAL_MODELS_DIR = APP_ROOT / "models"
LOCAL_PIPER_DIR = LOCAL_MODELS_DIR / "piper"

ENGINE_MODES = {
    "Авто": "auto",
    "OpenAI Realtime": "openai",
    "Локальный каскад": "local",
}

LANGUAGES = {
    "Русский": "ru",
    "English": "en",
    "Deutsch": "de",
    "Français": "fr",
    "Español": "es",
    "Italiano": "it",
    "Português": "pt",
    "Polski": "pl",
    "Türkçe": "tr",
    "中文": "zh",
    "日本語": "ja",
    "한국어": "ko",
}

# FLORES-200 language tags used by NLLB.
NLLB_LANGUAGE_CODES = {
    "ru": "rus_Cyrl",
    "en": "eng_Latn",
    "de": "deu_Latn",
    "fr": "fra_Latn",
    "es": "spa_Latn",
    "it": "ita_Latn",
    "pt": "por_Latn",
    "pl": "pol_Latn",
    "tr": "tur_Latn",
    "zh": "zho_Hans",
    "ja": "jpn_Jpan",
    "ko": "kor_Hang",
}

# Voice defaults bundled by the optional local setup. Other languages remain
# subtitle-only unless the user provides a Piper model through env vars.
PIPER_VOICE_DEFAULTS = {
    "ru": "ru_RU-irina-medium",
    "en": "en_US-lessac-medium",
}


def load_api_key() -> str:
    load_dotenv(ENV_PATH)
    return os.getenv("OPENAI_API_KEY", "").strip()


def local_asr_model() -> str:
    return os.getenv("LIVEINTERPRETER_WHISPER_MODEL", "small").strip() or "small"


def local_asr_device() -> str:
    return os.getenv("LIVEINTERPRETER_ASR_DEVICE", "cpu").strip() or "cpu"


def local_asr_compute_type() -> str:
    default = "float16" if local_asr_device().lower() == "cuda" else "int8"
    return os.getenv("LIVEINTERPRETER_ASR_COMPUTE_TYPE", default).strip() or default


def local_translation_model() -> str:
    return os.getenv(
        "LIVEINTERPRETER_TRANSLATION_MODEL",
        "facebook/nllb-200-distilled-600M",
    ).strip()


def local_translation_device() -> str:
    return os.getenv("LIVEINTERPRETER_TRANSLATION_DEVICE", "auto").strip() or "auto"


def local_piper_voice_path(language: str) -> Path | None:
    env_name = f"LIVEINTERPRETER_PIPER_VOICE_{language.upper()}"
    override = os.getenv(env_name, "").strip()
    if override:
        return Path(override).expanduser()
    voice = PIPER_VOICE_DEFAULTS.get(language)
    if not voice:
        return None
    return LOCAL_PIPER_DIR / f"{voice}.onnx"


@dataclass(slots=True)
class DirectionConfig:
    enabled: bool
    input_device_name: str
    output_device_name: str
    target_language: str
    label: str
    engine: str = "openai"


@dataclass(slots=True)
class AppConfig:
    remote_to_me: DirectionConfig
    me_to_remote: DirectionConfig
