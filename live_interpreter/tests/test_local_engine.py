from __future__ import annotations

import numpy as np

from live_interpreter.config import CHATTERBOX_LANGUAGES, INPUT_SAMPLE_RATE, LANGUAGES, NLLB_LANGUAGE_CODES
from live_interpreter.dsp import float_to_pcm16_mono, pcm16_to_float
from live_interpreter.local_engine import SpeechSegmenter


def _tone(ms: int, amplitude: float) -> bytes:
    count = INPUT_SAMPLE_RATE * ms // 1000
    samples = np.full(count, amplitude, dtype=np.float32)
    return float_to_pcm16_mono(samples)


def test_segmenter_emits_after_silence() -> None:
    emitted: list[bytes] = []
    segmenter = SpeechSegmenter(
        emitted.append,
        threshold=0.01,
        silence_ms=200,
        min_speech_ms=200,
        pre_roll_ms=40,
    )

    for _ in range(3):
        segmenter.push(_tone(40, 0.0))
    for _ in range(8):
        segmenter.push(_tone(40, 0.1))
    for _ in range(6):
        segmenter.push(_tone(40, 0.0))

    assert len(emitted) == 1
    assert pcm16_to_float(emitted[0]).size >= INPUT_SAMPLE_RATE * 0.4


def test_segmenter_ignores_short_noise() -> None:
    emitted: list[bytes] = []
    segmenter = SpeechSegmenter(
        emitted.append,
        threshold=0.01,
        silence_ms=120,
        min_speech_ms=300,
        pre_roll_ms=20,
    )
    segmenter.push(_tone(80, 0.2))
    for _ in range(5):
        segmenter.push(_tone(40, 0.0))
    segmenter.flush()
    assert emitted == []


def test_primary_language_maps_exist() -> None:
    assert NLLB_LANGUAGE_CODES["ru"] == "rus_Cyrl"
    assert NLLB_LANGUAGE_CODES["en"] == "eng_Latn"


def test_all_ui_languages_can_use_chatterbox_clone() -> None:
    assert set(LANGUAGES.values()) <= CHATTERBOX_LANGUAGES
