from __future__ import annotations

import json
import sys


def main() -> int:
    # Keep imports inside main so this script can show a clean error
    # if the venv is not set up.
    from app.doctor import run_mix_smoke_check

    mode = "mix"
    if len(sys.argv) >= 2:
        mode = (sys.argv[1] or "mix").strip().lower()
    if mode not in ("mix", "mix-smoke"):
        print("Usage: python run_doctor.py mix")
        return 2

    out = run_mix_smoke_check(require_llm=True, require_media=True)
    print(json.dumps(out.model_dump(), ensure_ascii=True, indent=2))
    return 0 if out.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
