"""D2 · LLM call accounting without any live call: per-task caps, no sampling params, usage and list-price
cost per call, one retry on 429/5xx, truncation fails closed, spend cap falls back to the mock planner."""
import io
import urllib.error

import pytest

from backend.llm.adapter import LLM, LLMError, cost_estimate

RESPONSE = {
    "output": {"message": {"role": "assistant", "content": [{"text": 'Sure. {"claims": [], "gaps": []}'}]}},
    "usage": {"inputTokens": 1480, "outputTokens": 231, "cacheReadInputTokens": 1210, "cacheWriteInputTokens": 0},
    "metrics": {"latencyMs": 1740},
    "stopReason": "end_turn",
}


def http_error(code):
    return urllib.error.HTTPError("https://bedrock", code, "err", {}, io.BytesIO(b'{"message":"boom"}'))


@pytest.fixture
def llm(monkeypatch):
    monkeypatch.setenv("AWS_BEARER_TOKEN_BEDROCK", "test-token-not-real")
    monkeypatch.setenv("BEDROCK_MODEL_ID", "us.anthropic.claude-haiku-5-5")
    monkeypatch.delenv("LLM_EFFORT", raising=False)
    monkeypatch.delenv("LLM_SPEND_CAP_USD", raising=False)
    model = LLM("bedrock")
    model.retry_backoff_s = 0
    return model


def test_caps_and_no_sampling_params(llm, monkeypatch):
    bodies = []

    def fake_http(body):
        bodies.append(body)
        return RESPONSE

    monkeypatch.setattr(llm, "_http", fake_http)
    llm.complete("extract_claims", {"x": 1}, "{...}")
    llm.complete("explain_findings", {"x": 1}, "{...}", max_tokens=900)
    llm.complete("some_new_task", {"x": 1}, "{...}")
    assert [b["inferenceConfig"]["maxTokens"] for b in bodies] == [800, 800, 1500]
    for b in bodies:
        assert set(b["inferenceConfig"]) == {"maxTokens"} and "additionalModelRequestFields" not in b
        assert "UNTRUSTED DATA" in b["system"][0]["text"]


def test_usage_cost_and_no_prompt_text_in_the_log(llm, monkeypatch):
    monkeypatch.setattr(llm, "_http", lambda body: RESPONSE)
    out = llm.complete("extract_claims", {"raw_finding": "secret-ish case text"}, "{...}")
    assert out == {"claims": [], "gaps": []}
    rec = llm.calls_log[-1]
    assert rec["input_tokens"] == 1480 and rec["output_tokens"] == 231 and rec["cache_read_input_tokens"] == 1210
    assert rec["latency_ms"] == 1740 and rec["stop_reason"] == "end_turn" and rec["json_ok"] and rec["attempts"] == 1
    expected = round(1480 * 0.10 / 1e6 + 1210 * 0.01 / 1e6 + 231 * 0.50 / 1e6, 8)
    assert rec["cost_estimate_usd"] == expected == cost_estimate("us.anthropic.claude-haiku-5-5", rec)
    assert "list" in rec["cost_basis"] and len(rec["prompt_sha256"]) == 64
    assert "secret-ish" not in str(llm.calls_log) and "test-token" not in str(llm.calls_log)
    s = llm.summary()
    assert s["calls"] == 1 and s["cost_estimate_usd"] == expected and s["by_task"]["extract_claims"]["latency_ms_p50"] == 1740
    assert s["cache_hit_share"] == round(1210 / (1480 + 1210), 3)


def test_retry_once_on_429_then_success_and_fail_after_two_5xx(llm, monkeypatch):
    calls = {"n": 0}

    def flaky(body):
        calls["n"] += 1
        if calls["n"] == 1:
            raise http_error(429)
        return RESPONSE

    monkeypatch.setattr(llm, "_http", flaky)
    assert llm.complete("propose_plan", {}, "{...}")["claims"] == []
    assert llm.calls_log[-1]["attempts"] == 2

    def down(body):
        raise http_error(503)

    monkeypatch.setattr(llm, "_http", down)
    with pytest.raises(LLMError, match="gave up after 2 attempts"):
        llm.complete("propose_plan", {}, "{...}")

    def bad_request(body):
        raise http_error(400)

    monkeypatch.setattr(llm, "_http", bad_request)
    with pytest.raises(LLMError, match="HTTP 400"):
        llm.complete("propose_plan", {}, "{...}")


def test_truncated_or_non_json_answers_fail_closed(llm, monkeypatch):
    monkeypatch.setattr(llm, "_http", lambda body: {**RESPONSE, "stopReason": "max_tokens"})
    with pytest.raises(LLMError, match="truncated"):
        llm.complete("extract_claims", {}, "{...}")
    assert llm.calls_log[-1]["json_ok"] is False and llm.calls_log[-1]["stop_reason"] == "max_tokens"
    monkeypatch.setattr(llm, "_http", lambda body: {**RESPONSE, "output": {"message": {"content": [{"text": "no json here"}]}}})
    with pytest.raises(LLMError, match="no JSON"):
        llm.complete("extract_claims", {}, "{...}")


def test_spend_cap_switches_to_mock_and_says_so(llm, monkeypatch):
    llm.spend_cap_usd = 0.0001
    monkeypatch.setattr(llm, "_http", lambda body: RESPONSE)
    llm.complete("extract_claims", {}, "{...}")  # ~0.00027 USD > cap
    assert llm.spend_cap_hit and llm.mode == "mock" and llm.label == "mock (spend cap hit)"
    assert llm.calls_log[-1]["event"] == "spend_cap_hit"
    with pytest.raises(LLMError, match="mock mode"):
        llm.complete("extract_claims", {}, "{...}")


def test_effort_is_opt_in(monkeypatch):
    monkeypatch.setenv("AWS_BEARER_TOKEN_BEDROCK", "t")
    monkeypatch.setenv("LLM_EFFORT", "on")
    model = LLM("bedrock")
    assert model.build_body("propose_plan", {}, "{}", 100)["additionalModelRequestFields"] == {"output_config": {"effort": "medium"}}
    assert model.build_body("extract_claims", {}, "{}", 100)["additionalModelRequestFields"] == {"output_config": {"effort": "low"}}
    monkeypatch.setenv("LLM_EFFORT", "off")
    assert "additionalModelRequestFields" not in LLM("bedrock").build_body("propose_plan", {}, "{}", 100)


def test_sink_receives_records_and_never_breaks_the_call(llm, monkeypatch):
    seen = []
    llm.sink = lambda rec: seen.append(rec["task"]) or (_ for _ in ()).throw(RuntimeError("ledger down"))
    monkeypatch.setattr(llm, "_http", lambda body: RESPONSE)
    llm.complete("extract_claims", {}, "{...}")
    assert seen == ["extract_claims"]


OPENAI_RESPONSE = {
    "id": "x", "model": "openai/gpt-oss-120b",
    "choices": [{"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": '{"claims": [], "gaps": []}'}}],
    "usage": {"prompt_tokens": 900, "completion_tokens": 120, "total_tokens": 1020, "prompt_tokens_details": {"cached_tokens": 100}},
}


def test_featherless_and_ollama_use_the_openai_shape_with_the_same_accounting(monkeypatch):
    monkeypatch.setenv("FEATHERLESS_API_KEY", "ft-not-real")
    monkeypatch.delenv("FEATHERLESS_MODEL", raising=False)
    monkeypatch.delenv("OLLAMA_MODEL", raising=False)
    bodies = []
    for mode, expect_key in (("featherless", True), ("ollama", False)):
        model = LLM(mode)
        model.retry_backoff_s = 0
        model.calls_log.clear()

        def fake_http(body, _m=model):
            bodies.append((_m.mode, _m.endpoint(), body))
            return OPENAI_RESPONSE

        monkeypatch.setattr(model, "_http", fake_http)
        out = model.complete("extract_claims", {"raw_finding": "x"}, "{...}")
        assert out == {"claims": [], "gaps": []}
        rec = model.calls_log[-1]
        assert rec["provider"] == mode and rec["input_tokens"] == 800 and rec["cache_read_input_tokens"] == 100
        assert rec["output_tokens"] == 120 and rec["stop_reason"] == "end_turn" and rec["json_ok"]
        if mode == "featherless":
            assert model.label == "featherless:openai/gpt-oss-120b"
            assert rec["cost_estimate_usd"] == round(800 * 0.15 / 1e6 + 100 * 0.15 / 1e6 + 120 * 0.60 / 1e6, 8)
        else:
            assert model.label == "ollama:qwen3:8b" and rec["cost_estimate_usd"] == 0.0 and "local" in rec["cost_basis"]
    (m1, url1, b1), (m2, url2, b2) = bodies
    assert url1 == "https://api.featherless.ai/v1/chat/completions" and url2 == "http://127.0.0.1:11434/v1/chat/completions"
    for b in (b1, b2):
        assert b["max_tokens"] == 800 and b["temperature"] == 0 and [m["role"] for m in b["messages"]] == ["system", "user"]
        assert "UNTRUSTED DATA" in b["messages"][0]["content"]


def test_openai_length_finish_is_truncation_and_missing_key_fails_closed(monkeypatch):
    monkeypatch.delenv("FEATHERLESS_API_KEY", raising=False)
    with pytest.raises(LLMError, match="FEATHERLESS_API_KEY missing"):
        LLM("featherless").complete("extract_claims", {}, "{}")
    monkeypatch.setenv("FEATHERLESS_API_KEY", "ft-not-real")
    model = LLM("featherless")
    cut = {**OPENAI_RESPONSE, "choices": [{**OPENAI_RESPONSE["choices"][0], "finish_reason": "length"}]}
    monkeypatch.setattr(model, "_http", lambda body: cut)
    with pytest.raises(LLMError, match="truncated"):
        model.complete("extract_claims", {}, "{}")
    with pytest.raises(LLMError, match="unknown LLM_MODE"):
        LLM("gemini")


def test_call_cap_protects_models_with_no_known_price(monkeypatch):
    monkeypatch.setenv("FEATHERLESS_API_KEY", "ft-not-real")
    monkeypatch.setenv("FEATHERLESS_MODEL", "Some/Unpriced-Model")
    monkeypatch.setenv("LLM_MAX_CALLS", "2")
    model = LLM("featherless")
    monkeypatch.setattr(model, "_http", lambda body: OPENAI_RESPONSE)
    model.complete("extract_claims", {}, "{}")
    assert model.calls_log[-1]["cost_estimate_usd"] is None and model.mode == "featherless"
    model.complete("extract_claims", {}, "{}")
    assert model.mode == "mock" and model.calls_log[-1]["event"] == "call_cap_hit"
