# LiveInterpreter v0.2

Windows desktop application for live bidirectional speech translation during calls.

## Engines

LiveInterpreter now has three engine modes:

- **Auto** — use OpenAI Realtime when `gpt-realtime-translate` is available for the API project; otherwise fall back to Local.
- **OpenAI Realtime** — dedicated low-latency speech translation through `gpt-realtime-translate`.
- **Local cascade** — `faster-whisper -> NLLB-200 distilled 600M -> Piper` on the local computer.

The two conversation directions stay independent, but Local shares one Whisper/NLLB/Piper model bundle so bidirectional mode does not load duplicate model copies.

## Core features

- two independent translation directions;
- selectable engine: Auto / OpenAI / Local;
- automatic source-language detection by Whisper/OpenAI;
- selectable target language for each direction;
- selectable Windows input and output audio devices;
- source and translated subtitles;
- translated audio playback to headphones or a virtual cable;
- no recording or transcript persistence by default;
- local device/settings persistence only.

## OpenAI Realtime

The cloud engine uses the dedicated Realtime Translation WebSocket endpoint and `gpt-realtime-translate`.

Each direction streams mono PCM16 at 24 kHz and receives translated PCM audio plus source/target transcript deltas. For a two-person conversation, each source track gets its own Realtime session.

If the API project cannot resolve the model, Auto can continue through Local instead of blocking the app.

## Local cascade

Pipeline:

```text
Windows audio / microphone
        ↓
faster-whisper (stream chunks)
        ↓
source text + language detection
        ↓
NLLB-200 distilled 600M
        ↓
translated subtitles
        ↓
Piper voice (when a voice is installed)
        ↓
selected Windows output
```

The first local version intentionally uses a simple low-latency RMS speech segmenter: a phrase is emitted after a short silence or a hard maximum segment duration. This is less simultaneous than a native simultaneous-translation model, but it is substantially easier to run locally and does not depend on a paid realtime API.

### Default local models

- ASR: `small` faster-whisper, CPU `int8` by default;
- translation: `facebook/nllb-200-distilled-600M`;
- TTS Russian: `ru_RU-irina-medium`;
- TTS English: `en_US-lessac-medium`.

Russian/English voices are installed by `setup-local.ps1`. Other target languages still produce translated subtitles; spoken output requires a compatible Piper voice path configured separately.

## Important audio-routing requirement

Full duplex translation requires isolated audio routes to avoid feedback. Recommended setup: two virtual audio cables or an equivalent mixer with two independent virtual buses.

See [docs/AUDIO_ROUTING.md](docs/AUDIO_ROUTING.md).

## Base install on Windows

Open PowerShell in this folder:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\setup.ps1
```

OpenAI is optional in v0.2. If you want the Realtime engine, edit `.env`:

```env
OPENAI_API_KEY=sk-...
```

Do not commit `.env`.

## Install Local engine

After the base install:

```powershell
.\setup-local.ps1
```

This installs the optional Local dependencies and downloads/caches the default Whisper, NLLB and Russian/English Piper models. Expect several gigabytes of downloads.

Then run:

```powershell
.\diagnose.ps1
.\run.ps1
```

Diagnostics reports both `MODEL ACCESS` for OpenAI and `LOCAL ENGINE` readiness.

## Recommended first test

Start with a single direction:

- engine: `Local cascade` or `Auto`;
- `Собеседник -> Вы`: enabled;
- `Вы -> Собеседник`: disabled;
- input: loopback of the Windows output device that receives call/video audio;
- output: physical headphones or another isolated output;
- target: Russian.

Once this works without echo/feedback, configure the reverse direction through a second virtual cable.

## Local tuning

Defaults prioritize reliability over minimum latency. Environment overrides are available:

```text
LIVEINTERPRETER_WHISPER_MODEL=small
LIVEINTERPRETER_ASR_DEVICE=cpu
LIVEINTERPRETER_ASR_COMPUTE_TYPE=int8
LIVEINTERPRETER_TRANSLATION_MODEL=facebook/nllb-200-distilled-600M
LIVEINTERPRETER_TRANSLATION_DEVICE=auto
```

For CTranslate2/Whisper GPU mode, only switch after the NVIDIA CUDA/cuDNN runtime is known-good:

```cmd
set LIVEINTERPRETER_ASR_DEVICE=cuda
set LIVEINTERPRETER_ASR_COMPUTE_TYPE=float16
```

NLLB uses CUDA automatically when the installed PyTorch build sees CUDA; otherwise it runs on CPU.

## Troubleshooting `model_not_found`

If OpenAI Realtime returns 404 / `model_not_found`, run:

```powershell
.\diagnose.ps1
```

If `MODEL ACCESS` is unavailable but `LOCAL ENGINE` is available, choose `Auto` or `Local cascade`. Auto will bypass the unavailable OpenAI model.

## Licensing note for Local

The local stack is intentionally optional. Check licenses before redistributing or commercializing a packaged application:

- Meta NLLB checkpoints use a non-commercial model license (`CC-BY-NC-4.0` on the referenced Hugging Face model);
- current Piper development (`OHF-Voice/piper1-gpl`) is GPLv3;
- individual Piper voice model/dataset licenses can differ. The Russian Irina model card currently lists the underlying dataset license as unknown.

This is fine for personal experimentation, but a commercial product should select models/voices with appropriate licenses before distribution.

## Current limitations

- Local is phrase-streaming, not true token-level simultaneous translation;
- Local ASR/translation inference is serialized when both directions are active, to avoid duplicated model memory and unpredictable GPU contention;
- device-level routing, not per-process WASAPI capture;
- no built-in virtual audio driver;
- no automatic echo cancellation/mixing layer;
- Piper voice output is bundled only for Russian/English setup defaults;
- Windows-first; other OSes are not tested.

## Next improvements

- GPU setup assistant for CTranslate2 + PyTorch;
- lower-latency streaming policy / WhisperLiveKit adapter;
- reconnect/backoff and latency indicator;
- original/translated volume controls;
- push-to-talk for the outbound direction;
- terminology/glossary layer;
- optional transcript export;
- installer packaging;
- VoiceMeeter/VB-CABLE setup assistant.

## Security and privacy

- API key is loaded only from environment or local `.env`;
- no API key is stored in QSettings;
- Local audio stays on the computer;
- OpenAI mode sends the active audio stream to the Realtime API;
- no call audio is written to disk;
- no transcript is written to disk by default.
