from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import traceback


def _resolve_device(requested: str) -> str:
    import torch

    requested = requested.lower().strip()
    if requested == "auto":
        return "cuda" if torch.cuda.is_available() else "cpu"
    return requested


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--device", default="auto")
    args = parser.parse_args()

    model = None
    sample_rate = None
    device = None

    print("LI_READY", flush=True)

    for raw in sys.stdin:
        try:
            req = json.loads(raw)
            if req.get("cmd") == "close":
                return 0
            if req.get("cmd") != "synthesize":
                continue

            request_id = str(req.get("id") or "")
            text = str(req.get("text") or "").strip()
            language = str(req.get("language") or "").strip().lower()
            reference = Path(str(req.get("reference") or ""))
            output = Path(str(req.get("output") or ""))

            if not text:
                raise ValueError("empty text")
            if not reference.exists():
                raise FileNotFoundError(reference)

            if model is None:
                import torch
                from chatterbox.mtl_tts import ChatterboxMultilingualTTS

                device = _resolve_device(args.device)
                model = ChatterboxMultilingualTTS.from_pretrained(device=device)
                sample_rate = int(model.sr)

            import torchaudio as ta

            # cfg_weight=0 is recommended by Chatterbox for cross-language
            # voice transfer so the reference-language accent is not imposed on
            # translated speech.
            wav = model.generate(
                text,
                language_id=language,
                audio_prompt_path=str(reference),
                exaggeration=0.5,
                cfg_weight=0.0,
            )
            if wav.ndim == 1:
                wav = wav.unsqueeze(0)
            output.parent.mkdir(parents=True, exist_ok=True)
            ta.save(
                str(output),
                wav.detach().cpu(),
                sample_rate,
                encoding="PCM_S",
                bits_per_sample=16,
            )
            response = {"id": request_id, "ok": True, "output": str(output), "device": device}
        except Exception as exc:
            response = {
                "id": str(locals().get("request_id", "")),
                "ok": False,
                "error": f"{type(exc).__name__}: {exc}",
            }
            traceback.print_exc(file=sys.stderr)

        print("LI_RESPONSE:" + json.dumps(response, ensure_ascii=False), flush=True)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
