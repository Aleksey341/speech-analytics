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


def load_api_key() -> str:
    load_dotenv(ENV_PATH)
    value = os.getenv("OPENAI_API_KEY", "").strip()
    return value


@dataclass(slots=True)
class DirectionConfig:
    enabled: bool
    input_device_name: str
    output_device_name: str
    target_language: str
    label: str


@dataclass(slots=True)
class AppConfig:
    remote_to_me: DirectionConfig
    me_to_remote: DirectionConfig
