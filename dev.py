"""Cross-platform task runner (works the same on Windows, macOS and Linux).

    python dev.py check    tests + eval (run before every push)
    python dev.py test     pytest
    python dev.py eval     evaluation table -> eval/report.md
    python dev.py bench    seconds, tokens, cost per case over 3 runs -> eval/bench.md (--llm for the live model)
    python dev.py run      start the UI on http://127.0.0.1:8000
    python dev.py smoke    check the Bedrock key in .env
    python dev.py setup    install requirements and create .env from .env.example if missing
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PY = sys.executable
ENV = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "PYTHONIOENCODING": "utf-8"}  # eval prints ✅/Ș; cp1252 consoles crash without this


def sh(*args: str) -> int:
    print("$", " ".join(args), flush=True)
    return subprocess.call(list(args), cwd=ROOT, env=ENV)


def main() -> int:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "help"
    if cmd == "setup":
        rc = sh(PY, "-m", "pip", "install", "-r", "requirements.txt")
        if not (ROOT / ".env").exists():
            shutil.copy(ROOT / ".env.example", ROOT / ".env")
            print("Created .env from .env.example (LLM_MODE=mock). Add the Bedrock key there to use Claude.")
        return rc
    if cmd == "test":
        return sh(PY, "-m", "pytest", "-q", "-p", "no:cacheprovider", "tests")
    if cmd == "eval":
        return sh(PY, "eval/run_eval.py")
    if cmd == "check":
        rc = sh(PY, "-m", "pytest", "-q", "-p", "no:cacheprovider", "tests")
        rc2 = sh(PY, "eval/run_eval.py")
        print("\nCHECK", "PASSED" if rc == 0 and rc2 == 0 else "FAILED")
        return rc or rc2
    if cmd == "bench":
        return sh(PY, "eval/bench.py", *sys.argv[2:])
    if cmd == "run":
        return sh(PY, "run.py")
    if cmd == "smoke":
        return sh(PY, "ops/bedrock_smoke.py")
    print(__doc__)
    return 0


if __name__ == "__main__":
    sys.exit(main())
