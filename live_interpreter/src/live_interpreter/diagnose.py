from __future__ import annotations

from .api_probe import friendly_model_access_error, probe_model_access
from .audio import list_input_devices, list_output_devices
from .config import MODEL, load_api_key, voice_clone_profile_path
from .local_engine import probe_local_engine
from .voice_clone import probe_voice_clone


def main() -> int:
    print("LiveInterpreter diagnostics")
    api_key = load_api_key()
    print(f"OPENAI_API_KEY: {'OK' if api_key else 'MISSING'}")

    if api_key:
        print(f"MODEL: {MODEL}")
        probe = probe_model_access(api_key)
        print(f"MODEL ACCESS: {probe.display}")
        if probe.available is False:
            print(f"MODEL ACCESS DETAIL: {friendly_model_access_error(probe)}")
        elif probe.available is None:
            print("MODEL ACCESS DETAIL: preflight inconclusive; WebSocket may still be attempted")

    local = probe_local_engine(("ru", "en"))
    print(f"LOCAL ENGINE: {'AVAILABLE' if local.available else 'UNAVAILABLE'}")
    print(f"LOCAL ENGINE DETAIL: {local.detail}")

    clone_runtime = probe_voice_clone(require_profile=False, target_language="en")
    print(f"VOICE CLONE RUNTIME: {'AVAILABLE' if clone_runtime.available else 'UNAVAILABLE'}")
    print(f"VOICE CLONE DETAIL: {clone_runtime.detail}")
    profile = voice_clone_profile_path()
    print(f"VOICE PROFILE: {'READY' if profile.exists() else 'MISSING'} · {profile}")

    print("\nINPUT DEVICES:")
    for i, d in enumerate(list_input_devices()):
        print(f"  [{i}] {d.display_name}")
    print("\nOUTPUT DEVICES:")
    for i, d in enumerate(list_output_devices()):
        print(f"  [{i}] {d.display_name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
