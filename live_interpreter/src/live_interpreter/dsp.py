from __future__ import annotations

import numpy as np


def float_to_pcm16_mono(data: np.ndarray) -> bytes:
    arr = np.asarray(data, dtype=np.float32)
    if arr.ndim == 2:
        arr = arr.mean(axis=1)
    arr = np.clip(arr, -1.0, 1.0)
    return (arr * 32767.0).astype("<i2", copy=False).tobytes()


def resample_linear(data: np.ndarray, src_rate: int, dst_rate: int) -> np.ndarray:
    arr = np.asarray(data, dtype=np.float32)
    if arr.ndim == 2:
        arr = arr.mean(axis=1)
    if src_rate == dst_rate or arr.size == 0:
        return arr.astype(np.float32, copy=False)
    out_len = max(1, int(round(arr.size * dst_rate / src_rate)))
    x_old = np.linspace(0.0, 1.0, num=arr.size, endpoint=False)
    x_new = np.linspace(0.0, 1.0, num=out_len, endpoint=False)
    return np.interp(x_new, x_old, arr).astype(np.float32)


def pcm16_to_float(data: bytes) -> np.ndarray:
    if not data:
        return np.empty(0, dtype=np.float32)
    return np.frombuffer(data, dtype="<i2").astype(np.float32) / 32768.0
