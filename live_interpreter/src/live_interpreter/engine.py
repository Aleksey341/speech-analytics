from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from .audio import AudioCapture, AudioPlayer
from .config import DirectionConfig
from .realtime import SessionCallbacks, TranslationSession


@dataclass(slots=True)
class DirectionEvents:
    on_status: Callable[[str], None]
    on_source_text: Callable[[str], None]
    on_target_text: Callable[[str], None]
    on_error: Callable[[str], None]


class TranslationDirection:
    def __init__(self, api_key: str, config: DirectionConfig, events: DirectionEvents) -> None:
        self.api_key = api_key
        self.config = config
        self.events = events
        self.player: Optional[AudioPlayer] = None
        self.capture: Optional[AudioCapture] = None
        self.session: Optional[TranslationSession] = None

    def start(self) -> None:
        if not self.config.enabled:
            self.events.on_status("disabled")
            return
        if not self.config.input_device_name:
            raise RuntimeError(f"{self.config.label}: input device is not selected")
        if not self.config.output_device_name:
            raise RuntimeError(f"{self.config.label}: output device is not selected")

        self.player = AudioPlayer(self.config.output_device_name, self.events.on_error)
        self.player.start()
        callbacks = SessionCallbacks(
            on_status=self.events.on_status,
            on_audio=self.player.enqueue_pcm24k,
            on_source_transcript=self.events.on_source_text,
            on_target_transcript=self.events.on_target_text,
            on_error=self.events.on_error,
        )
        self.session = TranslationSession(self.api_key, self.config.target_language, callbacks)
        self.session.start()
        if not self.session.wait_until_ready(timeout=8.0):
            detail = self.session.failure_message or "OpenAI Realtime session did not become ready within 8 seconds"
            self.stop()
            raise RuntimeError(f"{self.config.label}: {detail}")

        self.capture = AudioCapture(
            self.config.input_device_name,
            on_pcm24k=self.session.send_pcm24k,
            on_error=self.events.on_error,
        )
        self.capture.start()

    def stop(self) -> None:
        if self.capture:
            self.capture.stop()
            self.capture = None
        if self.session:
            self.session.close()
            self.session = None
        if self.player:
            self.player.stop()
            self.player = None
