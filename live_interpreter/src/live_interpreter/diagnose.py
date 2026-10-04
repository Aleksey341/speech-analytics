from __future__ import annotations

from .audio import list_input_devices, list_output_devices
from .config import load_api_key


def main() -> int:
    print("LiveInterpreter diagnostics")
    print(f"OPENAI_API_KEY: {'OK' if load_api_key() else 'MISSING'}")
    print("\nINPUT DEVICES:")
    for i, d in enumerate(list_input_devices()):
        print(f"  [{i}] {d.display_name}")
    print("\nOUTPUT DEVICES:")
    for i, d in enumerate(list_output_devices()):
        print(f"  [{i}] {d.display_name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
