"""One command to start the demo:  python run.py   (then open http://127.0.0.1:8000)
LLM_MODE=bedrock in .env uses Claude on Bedrock; default is the deterministic mock planner."""
import os
import sys

import uvicorn

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    print(f"Agent Assurance demo on http://127.0.0.1:{port}  (synthetic data only)")
    uvicorn.run("backend.api:app", host="127.0.0.1", port=port, reload=False)
