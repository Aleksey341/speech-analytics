# LiveInterpreter agent rules

Scope: only `live_interpreter/`.

## Product intent

Windows desktop MVP for low-latency bidirectional speech translation during calls (TrueConf, Telemost, Zoom, Teams, etc.).

## Non-negotiable architecture

- Dedicated OpenAI Realtime Translation endpoint `/v1/realtime/translations`.
- Model: `gpt-realtime-translate` unless current OpenAI docs explicitly supersede it.
- Two-person conversational translation uses one independent translation session per direction.
- Source speaker tracks must remain separate.
- WebSocket input: PCM16 mono 24 kHz.
- Never commit or log the OpenAI API key.
- Never store call audio or transcripts by default.
- Audio routing must prevent translated output from feeding back into its own input.

## UX

- Desktop-first working tool, not landing page.
- Device routing must be explicit and understandable.
- Always surface connecting/online/error/offline states.
- Show source and translated transcripts.
- Long device names must remain usable.
- No decorative motion that can harm latency or clarity.

## Safety / privacy

- API key only from environment/.env.
- `.env` stays ignored.
- Do not upload recordings automatically.
- Do not add hidden telemetry.

## Testing

Before declaring work complete:

1. `python -m compileall src`
2. `pytest`
3. verify `diagnose.ps1` still enumerates devices
4. if changing Realtime events, re-check the current official OpenAI docs
