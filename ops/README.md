# ops/

## `bedrock_smoke.py`

Checks that the Bedrock key in `.env` works before you switch the app to the real model.

```bash
python dev.py smoke          # same as: python ops/bedrock_smoke.py
```

It reads `.env` (no extra packages), sends one short request to the Bedrock Converse API with `BEDROCK_MODEL_ID` in `AWS_REGION`, and prints the model's reply or the HTTP error. The key is never printed.

Typical errors:
- **403 / expired token:** short-term Bedrock keys last at most 12 hours; generate a new one in the AWS console (Bedrock → API keys).
- **400 on `temperature`:** Claude Haiku 5.5 rejects sampling parameters; the app doesn't send them.
- **Model not found:** model ids need the region prefix of an inference profile (`us.` or `eu.`).

## Hosting

`railway.json` (repo root) has a start command for platforms that read it:

```
python -m uvicorn backend.api:app --host 0.0.0.0 --port $PORT
```

The same command works on any Python host (Render, a VM). Set the model settings (`LLM_MODE`, `AWS_BEARER_TOKEN_BEDROCK`, `AWS_REGION`, `BEDROCK_MODEL_ID`, `LLM_SPEND_CAP_USD`) as environment variables on the host, never in the repo. The key stays on the server: the browser never receives it.

The live demo runs this way on Render: <https://ccc-claude-code-crusaders.onrender.com/>.
