# LiveInterpreter v0.3

Windows desktop application for live bidirectional speech translation during calls.

## Engines

LiveInterpreter has three translation engine modes:

- **Auto** — use OpenAI Realtime when `gpt-realtime-translate` is available; otherwise fall back to Local. If `Мой голос` is selected, Auto uses Local.
- **OpenAI Realtime** — low-latency speech translation through `gpt-realtime-translate`.
- **Local cascade** — `faster-whisper -> NLLB-200 distilled 600M -> TTS` on the local computer.

## Voice modes

Each direction has its own voice mode:

- **Стандартный** — OpenAI voice in Realtime mode or Piper in Local mode;
- **Мой голос** — local zero-shot voice cloning through Chatterbox Multilingual using your saved voice reference;
- **Только текст** — subtitles only, no translated audio playback.

`Мой голос` currently works only through the Local cascade. This is intentional: OpenAI Realtime audio is not re-voiced by the local clone layer in v0.3.

## My Voice setup

First install the normal Local engine:

```powershell
.\setup-local.ps1
```

Then install the isolated voice-clone runtime:

```powershell
.\setup-voice-clone.ps1
```

Chatterbox is installed into its own `.voice-venv` because it pins a different Torch/Transformers stack from the main local translation environment. The setup script also downloads/caches the multilingual model unless `-SkipModelDownload` is passed.

In the app:

1. Select your real microphone in `Вы -> Собеседник`.
2. Click `Записать мой голос (15 с)`.
3. Speak normally for 15 seconds with little background noise.
4. Set `Голос = Мой голос` for `Вы -> Собеседник`.
5. Use engine `Авто` or `Локальный каскад`.

The reference is stored locally as:

```text
live_interpreter\voice_profiles\my_voice.wav
```

`voice_profiles/` and `.voice-venv/` are ignored by Git.

### Voice-clone languages

The current Chatterbox Multilingual path covers all languages exposed by LiveInterpreter: Russian, English, German, French, Spanish, Italian, Portuguese, Polish, Turkish, Chinese, Japanese and Korean.

For cross-language cloning LiveInterpreter uses `cfg_weight=0`, following the Chatterbox guidance for reducing reference-language accent transfer.

## Local cascade

```text
Windows audio / microphone
        ↓
faster-whisper
        ↓
source text + language detection
        ↓
NLLB-200 distilled 600M
        ↓
translated subtitles
        ↓
Piper (standard) OR Chatterbox (My Voice)
        ↓
selected Windows output
```

Local is phrase-streaming: a phrase is emitted after a short silence or hard maximum duration. It is not yet token-level simultaneous translation.

### Default local models

- ASR: `small` faster-whisper, CPU `int8` by default;
- translation: `facebook/nllb-200-distilled-600M`;
- standard TTS Russian: `ru_RU-irina-medium`;
- standard TTS English: `en_US-lessac-medium`;
- cloned TTS: Chatterbox Multilingual 0.1.7 in isolated `.voice-venv`.

## Base install on Windows

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\setup.ps1
```

OpenAI is optional. If you want Realtime, edit `.env`:

```env
OPENAI_API_KEY=sk-...
```

Do not commit `.env`.

## Install Local engine

```powershell
.\setup-local.ps1
```

This installs Whisper/NLLB/Piper and downloads the default local models.

Diagnostics:

```powershell
.\diagnose.ps1
```

The report includes OpenAI access, Local engine readiness, Voice Clone runtime readiness and whether the local voice profile exists.

Start:

```powershell
.\run.ps1
```

or double-click `LiveInterpreter.bat` / the desktop shortcut.

## Recommended first My Voice test

Use one direction first:

- engine: `Local cascade` or `Auto`;
- `Собеседник -> Вы`: disabled;
- `Вы -> Собеседник`: enabled;
- input: your USB microphone;
- target: English;
- voice: `Мой голос`;
- output: headphones for a local test, then a virtual cable for an actual call.

## Audio routing

Full duplex translation requires isolated audio routes to avoid feedback. Recommended setup: two virtual audio cables or an equivalent mixer with independent virtual buses.

See [docs/AUDIO_ROUTING.md](docs/AUDIO_ROUTING.md).

## Local tuning

```text
LIVEINTERPRETER_WHISPER_MODEL=small
LIVEINTERPRETER_ASR_DEVICE=cpu
LIVEINTERPRETER_ASR_COMPUTE_TYPE=int8
LIVEINTERPRETER_TRANSLATION_MODEL=facebook/nllb-200-distilled-600M
LIVEINTERPRETER_TRANSLATION_DEVICE=auto
LIVEINTERPRETER_VOICE_DEVICE=auto
LIVEINTERPRETER_VOICE_PROFILE=<optional custom WAV path>
```

`LIVEINTERPRETER_VOICE_DEVICE=auto` uses CUDA when the isolated Chatterbox Torch runtime sees CUDA; otherwise CPU.

## Licensing

Check licenses before redistribution/commercial packaging:

- NLLB checkpoint: non-commercial model license (`CC-BY-NC-4.0` on the referenced checkpoint);
- current Piper development: GPLv3;
- individual Piper voice licenses may differ;
- Chatterbox code/model project is MIT licensed.

## Privacy

- API key is loaded only from environment or local `.env`;
- Local translation audio stays on the computer;
- OpenAI mode sends the active audio stream to the Realtime API;
- conversation audio and transcripts are not persisted by default;
- the explicit 15-second `Мой голос` reference is persisted locally because it is required for cloning;
- the voice reference is ignored by Git and should be treated as private biometric-like data.

## Current limitations

- cloned speech adds more latency than Piper and much more than native Realtime speech-to-speech;
- Chatterbox model loading is heavy and first use can take time;
- Local ASR/translation inference is serialized when both directions are active;
- Windows Chatterbox is integrated as an isolated optional runtime but still requires real-machine validation for the installed CUDA/PyTorch combination;
- no built-in virtual audio driver or echo cancellation layer yet.
