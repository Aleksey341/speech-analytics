from __future__ import annotations

import base64
import hashlib
import json
import socket
import threading
import uuid
from dataclasses import dataclass
from typing import Callable, Optional

import websocket

from .config import REALTIME_URL


@dataclass(slots=True)
class SessionCallbacks:
    on_status: Callable[[str], None]
    on_audio: Callable[[bytes], None]
    on_source_transcript: Callable[[str], None]
    on_target_transcript: Callable[[str], None]
    on_error: Callable[[str], None]


def safety_identifier() -> str:
    raw = f"live-interpreter:{socket.gethostname()}:{uuid.getnode()}".encode("utf-8", errors="ignore")
    return hashlib.sha256(raw).hexdigest()[:32]


class TranslationSession:
    """One source stream -> one translated output language."""

    def __init__(self, api_key: str, target_language: str, callbacks: SessionCallbacks) -> None:
        self.api_key = api_key
        self.target_language = target_language
        self.callbacks = callbacks
        self._ws: Optional[websocket.WebSocketApp] = None
        self._thread: Optional[threading.Thread] = None
        self._opened = threading.Event()
        self._closed = threading.Event()
        self._closing = threading.Event()
        self._send_lock = threading.Lock()

    @property
    def connected(self) -> bool:
        return self._opened.is_set() and not self._closed.is_set()

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._opened.clear()
        self._closed.clear()
        self._closing.clear()
        self._thread = threading.Thread(target=self._run, name=f"translate->{self.target_language}", daemon=True)
        self._thread.start()

    def wait_until_open(self, timeout: float = 8.0) -> bool:
        return self._opened.wait(timeout=timeout)

    def send_pcm24k(self, pcm16: bytes) -> None:
        if not self.connected or self._closing.is_set() or not pcm16:
            return
        event = {
            "type": "session.input_audio_buffer.append",
            "audio": base64.b64encode(pcm16).decode("ascii"),
        }
        try:
            with self._send_lock:
                if self._ws and self.connected:
                    self._ws.send(json.dumps(event))
        except Exception as exc:
            self.callbacks.on_error(f"Realtime send error: {exc}")

    def close(self, timeout: float = 4.0) -> None:
        if self._closing.is_set():
            return
        self._closing.set()
        try:
            with self._send_lock:
                if self._ws and self.connected:
                    self._ws.send(json.dumps({"type": "session.close"}))
        except Exception:
            pass
        self._closed.wait(timeout=timeout)
        try:
            if self._ws:
                self._ws.close()
        except Exception:
            pass
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)

    def _run(self) -> None:
        headers = [
            f"Authorization: Bearer {self.api_key}",
            f"OpenAI-Safety-Identifier: {safety_identifier()}",
        ]

        def on_open(ws):
            ws.send(json.dumps({
                "type": "session.update",
                "session": {"audio": {"output": {"language": self.target_language}}},
            }))
            self._opened.set()
            self.callbacks.on_status("online")

        def on_message(ws, message: str):
            try:
                event = json.loads(message)
            except json.JSONDecodeError:
                return
            etype = event.get("type", "")
            if etype == "session.output_audio.delta":
                delta = event.get("delta")
                if delta:
                    self.callbacks.on_audio(base64.b64decode(delta))
            elif etype == "session.output_transcript.delta":
                self.callbacks.on_target_transcript(str(event.get("delta", "")))
            elif etype == "session.input_transcript.delta":
                self.callbacks.on_source_transcript(str(event.get("delta", "")))
            elif etype == "session.closed":
                self._closed.set()
                self.callbacks.on_status("closed")
                try:
                    ws.close()
                except Exception:
                    pass
            elif etype == "error":
                err = event.get("error") or event
                self.callbacks.on_error(f"OpenAI Realtime error: {err}")

        def on_error(ws, error):
            if not self._closing.is_set():
                self.callbacks.on_error(f"Realtime connection error: {error}")
            self.callbacks.on_status("error")

        def on_close(ws, code, reason):
            self._closed.set()
            if not self._closing.is_set():
                self.callbacks.on_status("offline")

        self._ws = websocket.WebSocketApp(
            REALTIME_URL,
            header=headers,
            on_open=on_open,
            on_message=on_message,
            on_error=on_error,
            on_close=on_close,
        )
        self.callbacks.on_status("connecting")
        self._ws.run_forever(ping_interval=20, ping_timeout=10)
