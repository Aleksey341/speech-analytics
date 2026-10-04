# LiveInterpreter MVP

Windows desktop application for live bidirectional speech translation during calls.

## What works in v0.1

- two independent translation directions;
- automatic source-language detection by the translation model;
- selectable target language for each direction;
- selectable Windows input and output audio devices;
- streaming source and translated subtitles;
- translated audio playback to headphones or a virtual cable;
- no recording or transcript persistence by default;
- local device/settings persistence only.

## OpenAI transport

The app uses the dedicated Realtime Translation WebSocket endpoint and `gpt-realtime-translate`.

Each direction streams mono PCM16 at 24 kHz and receives translated PCM audio plus source/target transcript deltas.

For a two-person conversation, the two source tracks stay separate and each direction gets its own Realtime Translation session.

## Important audio-routing requirement

Full duplex translation requires isolated audio routes to avoid feedback. Recommended setup: two virtual audio cables or an equivalent mixer with two independent virtual buses.

See [docs/AUDIO_ROUTING.md](docs/AUDIO_ROUTING.md).

## Install on Windows

Open PowerShell in this folder:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\setup.ps1
```

Edit `.env`:

```env
OPENAI_API_KEY=sk-...
```

Do not commit `.env`.

Diagnostics:

```powershell
.\diagnose.ps1
```

Start:

```powershell
.\run.ps1
```

## Recommended first test

Start with a single direction:

- `Собеседник -> Вы`: enabled
- `Вы -> Собеседник`: disabled
- input: a virtual cable receiving the call's speaker output
- output: physical headphones
- target: Russian

Once this works without echo/feedback, configure the reverse direction using a second virtual cable.

## Cost note

OpenAI currently prices `gpt-realtime-translate` by audio duration at **$0.034/minute per active translation stream**. Two continuously active directions therefore have an upper-order cost around $0.068/minute, before any future architecture changes.

## Current limitations

- device-level routing, not per-process WASAPI capture;
- no built-in virtual audio driver;
- no glossary injection into spoken translation yet because the dedicated translation session configuration currently exposes target-language/audio settings rather than general assistant instructions;
- no automatic reconnection UI yet;
- no echo cancellation/mixing layer;
- Windows-first; other OSes are not tested.

## Planned v0.2

- reconnect/backoff and latency indicator;
- original/translated volume controls;
- push-to-talk option for the outbound direction;
- optional transcript export;
- terminology test suite / golden phrases;
- installer packaging;
- optional VoiceMeeter/VB-CABLE setup assistant.

## Security

- API key is loaded only from environment or local `.env`;
- no API key is stored in QSettings;
- no call audio is written to disk;
- no transcript is written to disk by default.
