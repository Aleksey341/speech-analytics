import numpy as np

from live_interpreter.dsp import float_to_pcm16_mono, pcm16_to_float, resample_linear


def test_resample_48k_to_24k_halves_length():
    src = np.linspace(-1.0, 1.0, 960, dtype=np.float32)
    out = resample_linear(src, 48_000, 24_000)
    assert len(out) == 480


def test_pcm_roundtrip_is_close():
    src = np.array([-1.0, -0.5, 0.0, 0.5, 0.999], dtype=np.float32)
    pcm = float_to_pcm16_mono(src)
    out = pcm16_to_float(pcm)
    assert np.allclose(src, out, atol=1e-4)
