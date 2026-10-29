"""Smoke test for the Bedrock key. Run from the repo root:  python ops/bedrock_smoke.py
import urllib.parse
Reads .env (no extra packages needed), calls the Converse REST API, prints the reply.
The key is never printed."""
import json, os, pathlib, sys, urllib.request, urllib.error

env = pathlib.Path(__file__).resolve().parent.parent / ".env"
if env.exists():
    for line in env.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip() if not line.startswith("AWS_BEARER") else line.strip()
        if "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

token = os.environ.get("AWS_BEARER_TOKEN_BEDROCK")
region = os.environ.get("AWS_REGION", "us-west-2")
models = sys.argv[1:] or [os.environ.get("BEDROCK_MODEL_ID", "us.anthropic.claude-haiku-5-5"),
                          "us.anthropic.claude-haiku-4-5-20251001-v1:0"]
if not token:
    sys.exit("AWS_BEARER_TOKEN_BEDROCK missing: put it in .env")

body = json.dumps({"messages": [{"role": "user", "content": [{"text": "Reply with: ok"}]}],
                   "inferenceConfig": {"maxTokens": 20}}).encode()
ok = True
for m in models:
    url = f"https://bedrock-runtime.{region}.amazonaws.com/model/{urllib.parse.quote(m, safe='')}/converse"
    req = urllib.request.Request(url, data=body, method="POST", headers={
        "Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            out = json.load(r)
        print(f"OK   {m}: {out['output']['message']['content'][0]['text']!r}")
    except urllib.error.HTTPError as e:
        ok = False
        print(f"FAIL {m}: HTTP {e.code} {e.read().decode()[:300]}")
        if e.code == 403:
            print("     403 = expired key, wrong region, or no model access. Expired? Generate a new short-term key.")
    except Exception as e:
        ok = False
        print(f"FAIL {m}: {e}")
sys.exit(0 if ok else 1)
