"""One judging interface, two backends.

judge(state, questions) -> {question_key: {type, probabilities, ...}}

JUDGE_BACKEND = "jev"   -> POST to Vercel AI Gateway evaluation model (needs AI_GATEWAY_API_KEY)
JUDGE_BACKEND = "haiku" -> stand-in: Claude Haiku 5.5 through the Anthropic SDK (needs ANTHROPIC_API_KEY),
                           same {state, questions} in, same shape out, labelled judge: haiku.
                           Not calibrated the way jev is; roughly 4x jev's price per decision.
JUDGE_BACKEND = "agent" -> stand-in: the coding agent answers the same {state, questions}
                           offline. Pending items are written to judgements/pending.json; the
                           agent fills judgements/answers.json and the pipeline is re-run.
                           Slower, dearer per decision, and not calibrated the way jev is.

Switching backend is the one-line change at the bottom of this file.
"""
import hashlib
import json
import os
import pathlib
import urllib.request

ROOT = pathlib.Path(__file__).parent
JDIR = ROOT / "judgements"
JDIR.mkdir(exist_ok=True)
PENDING = JDIR / "pending.json"
ANSWERS = JDIR / "answers.json"
JEV_CACHE = JDIR / "jev_cache.json"
HAIKU_CACHE = JDIR / "haiku_cache.json"
HAIKU_MODEL = "claude-haiku-5-5"
HAIKU_PRICE_IN, HAIKU_PRICE_OUT, HAIKU_PRICE_CACHE_READ = 0.10, 0.50, 0.01  # USD per 1M tokens

JEV_PRICE_PER_M_INPUT = 0.042  # USD, list price, input tokens only


def _key(state, questions):
    raw = json.dumps({"state": state, "questions": questions}, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _load(p):
    return json.loads(p.read_text()) if p.exists() else {}


def _save(p, d):
    p.write_text(json.dumps(d, indent=1, ensure_ascii=False))


class Pending(Exception):
    """Raised by the agent backend when judgements are missing; fill answers.json and re-run."""


def _env_key(name="AI_GATEWAY_API_KEY"):
    key = os.environ.get(name)
    if not key and (ROOT / ".env").exists():
        for line in (ROOT / ".env").read_text().splitlines():
            if line.startswith(name + "="):
                key = line.split("=", 1)[1].strip()
    return key


HAIKU_SYSTEM = (
    "You are an evaluation model. You receive a JSON state and a set of questions about it. "
    "For every question return a probability distribution over its options that reflects your "
    "honest uncertainty (probabilities sum to 1). Options: a boolean question has options "
    "true/false; a score question's options are the 0-based indices of its criteria list, as "
    "strings; a choice question's options are its criteria keys. Judge only from the state given."
)


def _options(q):
    if q["type"] == "boolean":
        return ["true", "false"]
    if q["type"] == "score":
        return [str(i) for i in range(len(q["criteria"]))]
    return list(q["criteria"].keys())


def judge_haiku(state, questions, spend):
    k = _key(state, questions)
    cache = _load(HAIKU_CACHE)
    if k in cache:
        spend["claude_calls_cached"] = spend.get("claude_calls_cached", 0) + 1
        return cache[k]
    import anthropic  # .venv/bin/python
    key = _env_key("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY missing: put it in .env or the environment")
    client = anthropic.Anthropic(api_key=key)
    schema = {"type": "object", "additionalProperties": False, "required": list(questions),
              "properties": {}}
    for qk, q in questions.items():
        opts = _options(q)
        schema["properties"][qk] = {
            "type": "object", "additionalProperties": False, "required": ["probabilities"],
            "properties": {"probabilities": {
                "type": "object", "additionalProperties": False, "required": opts,
                "properties": {o: {"type": "number"} for o in opts}}}}
    body = json.dumps({"state": state, "questions": questions}, ensure_ascii=False)
    resp = client.messages.create(
        model=HAIKU_MODEL, max_tokens=1024,
        output_config={"effort": "low", "format": {"type": "json_schema", "schema": schema}},
        system=[{"type": "text", "text": HAIKU_SYSTEM, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": body}],
    )
    if resp.stop_reason == "refusal":
        raise RuntimeError(f"haiku refused: {resp.stop_details}")
    data = json.loads(next(b.text for b in resp.content if b.type == "text"))
    u = resp.usage
    cost = (u.input_tokens * HAIKU_PRICE_IN + u.output_tokens * HAIKU_PRICE_OUT
            + (u.cache_read_input_tokens or 0) * HAIKU_PRICE_CACHE_READ
            + (u.cache_creation_input_tokens or 0) * HAIKU_PRICE_IN * 1.25) / 1e6
    spend["claude_usd"] = spend.get("claude_usd", 0) + cost
    spend["claude_calls"] = spend.get("claude_calls", 0) + 1
    spend["claude_tokens_in"] = spend.get("claude_tokens_in", 0) + u.input_tokens + (u.cache_read_input_tokens or 0) + (u.cache_creation_input_tokens or 0)
    spend["claude_tokens_out"] = spend.get("claude_tokens_out", 0) + u.output_tokens
    result = {}
    for qk, q in questions.items():
        probs = data[qk]["probabilities"]
        tot = sum(probs.values()) or 1.0
        probs = {o: round(v / tot, 4) for o, v in probs.items()}
        best = max(probs, key=probs.get)
        r = {"type": q["type"], "probabilities": probs, "confidence": probs[best]}
        if q["type"] == "boolean":
            r["value"] = probs["true"] >= 0.5
        elif q["type"] == "score":
            r["score"] = round(sum(int(o) * v for o, v in probs.items()), 3)
        else:
            r["choice"] = best
        result[qk] = r
    result["_judge"] = "haiku"
    cache[k] = result
    _save(HAIKU_CACHE, cache)
    return result


def judge_jev(state, questions, spend):
    k = _key(state, questions)
    cache = _load(JEV_CACHE)
    if k in cache:
        return cache[k]
    body = json.dumps({"state": state, "questions": questions}).encode()
    req = urllib.request.Request(
        "https://ai-gateway.vercel.sh/v4/ai/evaluation-model",
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {_env_key()}",
            "ai-model-id": "typesafe-ai/jev",
            "ai-evaluation-model-specification-version": "4",
            "ai-gateway-protocol-version": "0.0.1",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        out = json.loads(r.read())
    tokens = out.get("usage", {}).get("input_tokens") or len(body) // 4
    spend["jev_usd"] = spend.get("jev_usd", 0) + tokens * JEV_PRICE_PER_M_INPUT / 1e6
    spend["jev_calls"] = spend.get("jev_calls", 0) + 1
    result = out.get("results", out)
    result["_judge"] = "jev"
    cache[k] = result
    _save(JEV_CACHE, cache)
    return result


def judge_agent(state, questions, spend):
    k = _key(state, questions)
    answers = _load(ANSWERS)
    if k in answers:
        res = dict(answers[k])
        res["_judge"] = "agent"
        spend["agent_calls"] = spend.get("agent_calls", 0) + 1
        return res
    pending = _load(PENDING)
    pending[k] = {"state": state, "questions": questions}
    _save(PENDING, pending)
    return None


def judge(state, questions, spend):
    """Returns the per-question result dict, or None (agent backend) when the answer is pending."""
    return BACKENDS[JUDGE_BACKEND](state, questions, spend)


BACKENDS = {"jev": judge_jev, "haiku": judge_haiku, "agent": judge_agent}
JUDGE_BACKEND = os.environ.get("JUDGE_BACKEND", "haiku")  # <- the one-line switch: "jev", "haiku" or "agent"
