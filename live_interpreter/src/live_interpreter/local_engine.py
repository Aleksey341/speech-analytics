from __future__ import annotations

import importlib.util
import queue
import threading
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

import numpy as np

from .audio import AudioCapture, AudioPlayer
from .config import (
    INPUT_SAMPLE_RATE,
    NLLB_LANGUAGE_CODES,
    DirectionConfig,
    local_asr_compute_type,
    local_asr_device,
    local_asr_model,
    local_piper_voice_path,
    local_translation_device,
    local_translation_model,
    voice_clone_profile_path,
)
from .dsp import float_to_pcm16_mono, pcm16_to_float, resample_linear
from .voice_clone import get_voice_clone_client, probe_voice_clone

ASR_SAMPLE_RATE = 16_000


@dataclass(frozen=True, slots=True)
class LocalEngineReport:
    available: bool
    detail: str
    missing: tuple[str, ...] = ()


def probe_local_engine(target_languages: tuple[str, ...] = ()) -> LocalEngineReport:
    required = {
        "faster_whisper": "faster-whisper",
        "torch": "torch",
        "transformers": "transformers",
        "sentencepiece": "sentencepiece",
        "piper": "piper-tts",
    }
    missing = tuple(pkg for module, pkg in required.items() if importlib.util.find_spec(module) is None)
    if missing:
        return LocalEngineReport(
            False,
            "Не установлены локальные зависимости: " + ", ".join(missing) + ". Запустите setup-local.ps1.",
            missing,
        )

    absent_voices: list[str] = []
    for language in target_languages:
        model_path = local_piper_voice_path(language)
        if model_path is not None and not model_path.exists():
            absent_voices.append(f"{language}: {model_path.name}")

    if absent_voices:
        return LocalEngineReport(
            True,
            "Локальный перевод доступен; стандартный голос для части направлений не найден, поэтому там будут только субтитры: "
            + "; ".join(absent_voices),
        )

    return LocalEngineReport(True, "Локальный каскад готов.")


class SpeechSegmenter:
    """Dependency-free RMS segmenter for 24 kHz PCM16 streaming chunks."""

    def __init__(
        self,
        on_segment: Callable[[bytes], None],
        *,
        threshold: float = 0.012,
        silence_ms: int = 650,
        min_speech_ms: int = 500,
        max_segment_ms: int = 5500,
        pre_roll_ms: int = 180,
    ) -> None:
        self.on_segment = on_segment
        self.threshold = threshold
        self.silence_samples = INPUT_SAMPLE_RATE * silence_ms // 1000
        self.min_speech_samples = INPUT_SAMPLE_RATE * min_speech_ms // 1000
        self.max_segment_samples = INPUT_SAMPLE_RATE * max_segment_ms // 1000
        self.pre_roll_samples = INPUT_SAMPLE_RATE * pre_roll_ms // 1000
        self._pre_roll: deque[np.ndarray] = deque()
        self._pre_roll_count = 0
        self._active: list[np.ndarray] = []
        self._active_count = 0
        self._silence_count = 0
        self._speech_count = 0

    @staticmethod
    def _rms(samples: np.ndarray) -> float:
        if samples.size == 0:
            return 0.0
        work = samples.astype(np.float32, copy=False)
        return float(np.sqrt(np.mean(work * work)))

    def push(self, pcm16: bytes) -> None:
        if not pcm16:
            return
        samples = pcm16_to_float(pcm16).reshape(-1)
        if samples.size == 0:
            return
        is_speech = self._rms(samples) >= self.threshold

        if not self._active:
            self._pre_roll.append(samples)
            self._pre_roll_count += samples.size
            while self._pre_roll and self._pre_roll_count > self.pre_roll_samples:
                removed = self._pre_roll.popleft()
                self._pre_roll_count -= removed.size
            if not is_speech:
                return
            self._active = list(self._pre_roll)
            self._active_count = sum(chunk.size for chunk in self._active)
            self._speech_count = samples.size
            self._silence_count = 0
            self._pre_roll.clear()
            self._pre_roll_count = 0
            return

        self._active.append(samples)
        self._active_count += samples.size
        if is_speech:
            self._speech_count += samples.size
            self._silence_count = 0
        else:
            self._silence_count += samples.size

        if self._active_count >= self.max_segment_samples:
            self._emit()
        elif self._silence_count >= self.silence_samples and self._speech_count >= self.min_speech_samples:
            self._emit()

    def flush(self) -> None:
        if self._active and self._speech_count >= self.min_speech_samples:
            self._emit()
        else:
            self._reset_active()

    def _emit(self) -> None:
        merged = np.concatenate(self._active) if self._active else np.empty(0, dtype=np.float32)
        self._reset_active()
        if merged.size:
            self.on_segment(float_to_pcm16_mono(merged))

    def _reset_active(self) -> None:
        self._active = []
        self._active_count = 0
        self._silence_count = 0
        self._speech_count = 0


class LocalModelBundle:
    """One shared model bundle for both translation directions."""

    def __init__(self, on_status: Callable[[str], None]) -> None:
        on_status("local-loading-asr")
        from faster_whisper import WhisperModel

        self.asr = WhisperModel(
            local_asr_model(),
            device=local_asr_device(),
            compute_type=local_asr_compute_type(),
        )

        on_status("local-loading-translation")
        import torch
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

        self.torch = torch
        model_name = local_translation_model()
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.translation_model = AutoModelForSeq2SeqLM.from_pretrained(model_name)
        requested = local_translation_device().lower()
        if requested == "auto":
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            self.device = requested
        self.translation_model.to(self.device)
        self.translation_model.eval()
        self.inference_lock = threading.RLock()
        self.tts_lock = threading.RLock()
        self.voices: dict[str, object] = {}

    def transcribe(self, pcm24k: bytes) -> tuple[str, str]:
        samples24 = pcm16_to_float(pcm24k).reshape(-1)
        samples16 = resample_linear(samples24, INPUT_SAMPLE_RATE, ASR_SAMPLE_RATE).astype(np.float32, copy=False)
        with self.inference_lock:
            segments, info = self.asr.transcribe(
                samples16,
                beam_size=1,
                vad_filter=False,
                condition_on_previous_text=False,
            )
            text = " ".join(seg.text.strip() for seg in segments if seg.text.strip()).strip()
            language = (getattr(info, "language", "") or "").lower()
        return text, language

    def translate(self, text: str, source_language: str, target_language: str) -> str:
        if source_language == target_language:
            return text
        src = NLLB_LANGUAGE_CODES.get(source_language)
        tgt = NLLB_LANGUAGE_CODES.get(target_language)
        if not src or not tgt:
            raise RuntimeError(
                f"NLLB language mapping missing: source={source_language or 'unknown'}, target={target_language}"
            )

        with self.inference_lock:
            self.tokenizer.src_lang = src
            encoded = self.tokenizer(text, return_tensors="pt", truncation=True, max_length=512)
            encoded = {k: v.to(self.device) for k, v in encoded.items()}
            forced_id = self.tokenizer.convert_tokens_to_ids(tgt)
            with self.torch.inference_mode():
                generated = self.translation_model.generate(
                    **encoded,
                    forced_bos_token_id=forced_id,
                    max_new_tokens=256,
                    num_beams=1,
                )
            return self.tokenizer.batch_decode(generated, skip_special_tokens=True)[0].strip()

    def synthesize_pcm24k(
        self,
        text: str,
        language: str,
        voice_mode: str,
        voice_profile: str = "",
    ) -> list[bytes]:
        if voice_mode == "text":
            return []
        if voice_mode == "clone":
            profile = Path(voice_profile) if voice_profile else voice_clone_profile_path()
            report = probe_voice_clone(require_profile=True, target_language=language)
            if not report.available:
                raise RuntimeError(report.detail)
            return get_voice_clone_client().synthesize_pcm24k(text, language, profile)

        voice_path = local_piper_voice_path(language)
        if voice_path is None or not voice_path.exists():
            return []

        from piper import PiperVoice

        with self.tts_lock:
            voice = self.voices.get(language)
            if voice is None:
                voice = PiperVoice.load(str(voice_path))
                self.voices[language] = voice
            result: list[bytes] = []
            for chunk in voice.synthesize(text):
                audio = np.asarray(chunk.audio_float_array, dtype=np.float32)
                if audio.ndim > 1:
                    audio = audio.mean(axis=1)
                mono24 = resample_linear(audio.reshape(-1), int(chunk.sample_rate), INPUT_SAMPLE_RATE)
                result.append(float_to_pcm16_mono(mono24))
            return result


_bundle: Optional[LocalModelBundle] = None
_bundle_lock = threading.Lock()


def get_local_model_bundle(on_status: Callable[[str], None]) -> LocalModelBundle:
    global _bundle
    if _bundle is not None:
        return _bundle
    with _bundle_lock:
        if _bundle is None:
            _bundle = LocalModelBundle(on_status)
    return _bundle


class LocalCascadeDirection:
    """Audio -> faster-whisper -> NLLB -> Piper/Chatterbox -> selected output."""

    def __init__(self, config: DirectionConfig, events) -> None:
        self.config = config
        self.events = events
        self.capture: Optional[AudioCapture] = None
        self.player: Optional[AudioPlayer] = None
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._segments: queue.Queue[bytes | None] = queue.Queue(maxsize=8)
        self._segmenter = SpeechSegmenter(self._enqueue_segment)
        self._bundle: Optional[LocalModelBundle] = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        report = probe_local_engine((self.config.target_language,))
        if not report.available:
            raise RuntimeError(report.detail)
        if self.config.voice_mode == "clone":
            clone = probe_voice_clone(require_profile=True, target_language=self.config.target_language)
            if not clone.available:
                raise RuntimeError(clone.detail)
        self._stop.clear()
        self.events.on_status("local-loading")
        self._thread = threading.Thread(target=self._worker, name=f"local:{self.config.label}", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self.capture:
            self.capture.stop()
            self.capture = None
        self._segmenter.flush()
        try:
            self._segments.put_nowait(None)
        except queue.Full:
            pass
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3.0)
        if self.player:
            self.player.stop()
            self.player = None
        self.events.on_status("closed")

    def _enqueue_segment(self, data: bytes) -> None:
        if self._stop.is_set() or not data:
            return
        try:
            self._segments.put_nowait(data)
        except queue.Full:
            try:
                self._segments.get_nowait()
            except queue.Empty:
                pass
            try:
                self._segments.put_nowait(data)
            except queue.Full:
                pass

    def _worker(self) -> None:
        try:
            self._bundle = get_local_model_bundle(self.events.on_status)
            if self._stop.is_set():
                return
            if self.config.voice_mode != "text":
                self.player = AudioPlayer(self.config.output_device_name, self.events.on_error)
                self.player.start()
            self.capture = AudioCapture(
                self.config.input_device_name,
                on_pcm24k=self._segmenter.push,
                on_error=self.events.on_error,
            )
            self.capture.start()
            self.events.on_status("local-online")

            while not self._stop.is_set():
                segment = self._segments.get()
                if segment is None:
                    break
                self._process_segment(segment)
        except Exception as exc:
            if not self._stop.is_set():
                self.events.on_status("error")
                self.events.on_error(f"{self.config.label}: local engine error: {exc}")

    def _process_segment(self, pcm24k: bytes) -> None:
        if self._bundle is None:
            return
        source, source_language = self._bundle.transcribe(pcm24k)
        if not source:
            return
        self.events.on_source_text(source + "\n")

        target = self._bundle.translate(source, source_language, self.config.target_language)
        if not target:
            return
        self.events.on_target_text(target + "\n")

        if self.config.voice_mode == "clone":
            self.events.on_status("local-cloning")
        chunks = self._bundle.synthesize_pcm24k(
            target,
            self.config.target_language,
            self.config.voice_mode,
            self.config.voice_profile_path,
        )
        if not chunks:
            self.events.on_status("local-text-only")
            return
        if self.player:
            for chunk in chunks:
                self.player.enqueue_pcm24k(chunk)
        self.events.on_status("local-online")
