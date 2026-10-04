from __future__ import annotations

from .api_probe import friendly_model_access_error, probe_model_access
from .audio import list_input_devices, list_output_devices
from .config import MODEL, load_api_key


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

    print("\nINPUT DEVICES:")
    for i, d in enumerate(list_input_devices()):
        print(f"  [{i}] {d.display_name}")
    print("\nOUTPUT DEVICES:")
    for i, d in enumerate(list_output_devices()):
        print(f"  [{i}] {d.display_name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
