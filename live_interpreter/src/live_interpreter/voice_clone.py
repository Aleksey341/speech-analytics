from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import subprocess
import tempfile
import threading
import uuid
import wave

import numpy as np

from .config import (
    APP_ROOT,
    CHATTERBOX_LANGUAGES,
    INPUT_SAMPLE_RATE,
    VOICE_VENV_DIR,
    VOICE_WORKER_PATH,
    voice_clone_device,
    voice_clone_profile_path,
)
from .dsp import float_to_pcm16_mono, resample_linear


@dataclass(frozen=True, slots=True)
class VoiceCloneReport:
    available: bool
    detail: str


def voice_python_path() -> Path:
    return VOICE_VENV_DIR / "Scripts" / "python.exe"


def probe_voice_clone(require_profile: bool = True, target_language: str | None = None) -> VoiceCloneReport:
    py = voice_python_path()
    if not py.exists():
        return VoiceCloneReport(False, "Voice Clone не установлен. Запустите setup-voice-clone.ps1.")
    if not VOICE_WORKER_PATH.exists():
        return VoiceCloneReport(False, f"Не найден worker: {VOICE_WORKER_PATH.name}")
    if target_language and target_language not in CHATTERBOX_LANGUAGES:
        return VoiceCloneReport(False, f"Chatterbox не поддерживает язык '{target_language}'.")
    profile = voice_clone_profile_path()
    if require_profile and not profile.exists():
        return VoiceCloneReport(False, "Профиль голоса не записан. Нажмите «Записать мой голос (15 с)».")
    return VoiceCloneReport(True, f"Voice Clone готов. Профиль: {profile.name}")


class ChatterboxClient:
    """Persistent client for an isolated Chatterbox process.

    Chatterbox pins a different Torch/Transformers stack than the main local
    translation engine, so it intentionally lives in `.voice-venv`.
    """

    def __init__(self) -> None:
        self._process: subprocess.Popen[str] | None = None
        self._lock = threading.RLock()

    def _ensure_process(self) -> subprocess.Popen[str]:
        if self._process and self._process.poll() is None:
            return self._process

        report = probe_voice_clone(require_profile=False)
        if not report.available:
            raise RuntimeError(report.detail)

        cmd = [
            str(voice_python_path()),
            "-u",
            str(VOICE_WORKER_PATH),
            "--device",
            voice_clone_device(),
        ]
        self._process = subprocess.Popen(
            cmd,
            cwd=str(APP_ROOT),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )
        ready = self._read_until("LI_READY", request_id=None)
        if ready != "LI_READY":
            raise RuntimeError("Voice Clone worker не запустился.")
        return self._process

    def _read_until(self, prefix: str, request_id: str | None) -> str:
        process = self._process
        if process is None or process.stdout is None:
            raise RuntimeError("Voice Clone worker не запущен.")
        while True:
            line = process.stdout.readline()
            if line == "":
                code = process.poll()
                raise RuntimeError(f"Voice Clone worker завершился неожиданно (code={code}).")
            line = line.rstrip("\r\n")
            if prefix == "LI_READY" and line == "LI_READY":
                return line
            if prefix == "LI_RESPONSE:" and line.startswith(prefix):
                payload = json.loads(line[len(prefix):])
                if request_id is None or payload.get("id") == request_id:
                    if not payload.get("ok"):
                        raise RuntimeError(str(payload.get("error") or "Voice Clone synthesis failed"))
                    return str(payload.get("output") or "")

    def synthesize_pcm24k(self, text: str, language: str, reference_path: Path) -> list[bytes]:
        if language not in CHATTERBOX_LANGUAGES:
            raise RuntimeError(f"Voice Clone: неподдерживаемый язык {language}")
        if not reference_path.exists():
            raise RuntimeError(f"Voice Clone: профиль голоса не найден: {reference_path}")
        if not text.strip():
            return []

        with self._lock:
            process = self._ensure_process()
            if process.stdin is None:
                raise RuntimeError("Voice Clone worker stdin недоступен.")

            request_id = uuid.uuid4().hex
            temp_dir = APP_ROOT / "voice_profiles" / ".tmp"
            temp_dir.mkdir(parents=True, exist_ok=True)
            output_path = temp_dir / f"clone-{request_id}.wav"
            request = {
                "id": request_id,
                "cmd": "synthesize",
                "text": text,
                "language": language,
                "reference": str(reference_path),
                "output": str(output_path),
            }
            process.stdin.write(json.dumps(request, ensure_ascii=False) + "\n")
            process.stdin.flush()
            response_path = Path(self._read_until("LI_RESPONSE:", request_id))

            try:
                return _read_wav_as_pcm24k(response_path)
            finally:
                try:
                    response_path.unlink(missing_ok=True)
                except OSError:
                    pass

    def close(self) -> None:
        with self._lock:
            process = self._process
            self._process = None
            if not process or process.poll() is not None:
                return
            try:
                if process.stdin:
                    process.stdin.write(json.dumps({"cmd": "close"}) + "\n")
                    process.stdin.flush()
            except OSError:
                pass
            try:
                process.terminate()
                process.wait(timeout=2)
            except Exception:
                try:
                    process.kill()
                except Exception:
                    pass


def _read_wav_as_pcm24k(path: Path) -> list[bytes]:
    with wave.open(str(path), "rb") as wav:
        channels = wav.getnchannels()
        sampwidth = wav.getsampwidth()
        sample_rate = wav.getframerate()
        frames = wav.readframes(wav.getnframes())
    if sampwidth != 2:
        raise RuntimeError(f"Voice Clone returned unsupported WAV sample width: {sampwidth}")
    samples = np.frombuffer(frames, dtype="<i2").astype(np.float32) / 32768.0
    if channels > 1:
        samples = samples.reshape(-1, channels).mean(axis=1)
    samples24 = resample_linear(samples, sample_rate, INPUT_SAMPLE_RATE)
    pcm = float_to_pcm16_mono(samples24)
    chunk_bytes = INPUT_SAMPLE_RATE * 2 // 2  # 500 ms chunks
    return [pcm[i:i + chunk_bytes] for i in range(0, len(pcm), chunk_bytes) if pcm[i:i + chunk_bytes]]


_client: ChatterboxClient | None = None
_client_lock = threading.Lock()


def get_voice_clone_client() -> ChatterboxClient:
    global _client
    if _client is not None:
        return _client
    with _client_lock:
        if _client is None:
            _client = ChatterboxClient()
    return _client
