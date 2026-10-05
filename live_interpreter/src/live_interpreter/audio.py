from __future__ import annotations

import queue
import threading
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

import soundcard as sc

from .config import BLOCK_FRAMES_48K, DEVICE_SAMPLE_RATE, INPUT_SAMPLE_RATE
from .dsp import float_to_pcm16_mono, pcm16_to_float, resample_linear


@dataclass(frozen=True, slots=True)
class AudioDevice:
    name: str
    kind: str  # input | output
    is_loopback: bool = False

    @property
    def display_name(self) -> str:
        suffix = " · loopback" if self.is_loopback else ""
        return f"{self.name}{suffix}"


def list_input_devices() -> list[AudioDevice]:
    devices: list[AudioDevice] = []
    seen: set[tuple[str, bool]] = set()
    for mic in sc.all_microphones(include_loopback=True):
        name = str(mic.name)
        is_loopback = bool(getattr(mic, "isloopback", False)) or "loopback" in name.lower()
        key = (name, is_loopback)
        if key in seen:
            continue
        seen.add(key)
        devices.append(AudioDevice(name=name, kind="input", is_loopback=is_loopback))
    return devices


def list_output_devices() -> list[AudioDevice]:
    devices: list[AudioDevice] = []
    seen: set[str] = set()
    for speaker in sc.all_speakers():
        name = str(speaker.name)
        if name in seen:
            continue
        seen.add(name)
        devices.append(AudioDevice(name=name, kind="output"))
    return devices


def _find_microphone(name: str):
    candidates = sc.all_microphones(include_loopback=True)
    exact = [d for d in candidates if str(d.name) == name]
    if exact:
        return exact[0]
    partial = [d for d in candidates if name.lower() in str(d.name).lower()]
    if partial:
        return partial[0]
    raise RuntimeError(f"Input audio device not found: {name}")


def _find_speaker(name: str):
    candidates = sc.all_speakers()
    exact = [d for d in candidates if str(d.name) == name]
    if exact:
        return exact[0]
    partial = [d for d in candidates if name.lower() in str(d.name).lower()]
    if partial:
        return partial[0]
    raise RuntimeError(f"Output audio device not found: {name}")


def record_voice_reference(device_name: str, path: Path, duration_seconds: int = 15) -> Path:
    if not device_name:
        raise RuntimeError("Voice profile input device is not selected")
    if duration_seconds < 5:
        raise ValueError("Voice reference must be at least 5 seconds")

    mic = _find_microphone(device_name)
    total_frames = DEVICE_SAMPLE_RATE * duration_seconds
    captured = 0
    pcm_parts: list[bytes] = []
    with mic.recorder(samplerate=DEVICE_SAMPLE_RATE, channels=None, blocksize=BLOCK_FRAMES_48K) as recorder:
        while captured < total_frames:
            count = min(BLOCK_FRAMES_48K, total_frames - captured)
            frames = recorder.record(numframes=count)
            mono24 = resample_linear(frames, DEVICE_SAMPLE_RATE, INPUT_SAMPLE_RATE)
            pcm_parts.append(float_to_pcm16_mono(mono24))
            captured += count

    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(INPUT_SAMPLE_RATE)
        wav.writeframes(b"".join(pcm_parts))
    return path


class AudioCapture:
    def __init__(self, device_name: str, on_pcm24k: Callable[[bytes], None], on_error: Callable[[str], None]) -> None:
        self.device_name = device_name
        self.on_pcm24k = on_pcm24k
        self.on_error = on_error
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name=f"capture:{self.device_name}", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.5)

    def _run(self) -> None:
        try:
            mic = _find_microphone(self.device_name)
            with mic.recorder(samplerate=DEVICE_SAMPLE_RATE, channels=None, blocksize=BLOCK_FRAMES_48K) as recorder:
                while not self._stop.is_set():
                    frames = recorder.record(numframes=BLOCK_FRAMES_48K)
                    mono24 = resample_linear(frames, DEVICE_SAMPLE_RATE, INPUT_SAMPLE_RATE)
                    self.on_pcm24k(float_to_pcm16_mono(mono24))
        except Exception as exc:
            self.on_error(f"Audio capture error [{self.device_name}]: {exc}")


class AudioPlayer:
    def __init__(self, device_name: str, on_error: Callable[[str], None]) -> None:
        self.device_name = device_name
        self.on_error = on_error
        self._queue: queue.Queue[bytes | None] = queue.Queue(maxsize=250)
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name=f"playback:{self.device_name}", daemon=True)
        self._thread.start()

    def enqueue_pcm24k(self, data: bytes) -> None:
        if not data:
            return
        try:
            self._queue.put_nowait(data)
        except queue.Full:
            try:
                self._queue.get_nowait()
            except queue.Empty:
                pass
            try:
                self._queue.put_nowait(data)
            except queue.Full:
                pass

    def stop(self) -> None:
        self._stop.set()
        try:
            self._queue.put_nowait(None)
        except queue.Full:
            pass
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.5)
        self.clear()

    def clear(self) -> None:
        while True:
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break

    def _run(self) -> None:
        try:
            speaker = _find_speaker(self.device_name)
            with speaker.player(samplerate=DEVICE_SAMPLE_RATE, channels=1, blocksize=BLOCK_FRAMES_48K) as player:
                while not self._stop.is_set():
                    item = self._queue.get()
                    if item is None:
                        break
                    mono24 = pcm16_to_float(item)
                    mono48 = resample_linear(mono24, INPUT_SAMPLE_RATE, DEVICE_SAMPLE_RATE)
                    player.play(mono48.reshape(-1, 1))
        except Exception as exc:
            self.on_error(f"Audio playback error [{self.device_name}]: {exc}")
