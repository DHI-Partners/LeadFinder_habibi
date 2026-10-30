# Habibi lead finder

Signal-first LinkedIn lead finder for https://cafe.habibi-erp.com, built on treg + jev.

    python3 pipeline.py      # search → topic judge → reactions/comments → people judge → emails → runs/latest.json
    python3 build_page.py    # → page/index.html (open it in a browser)

jev needs `AI_GATEWAY_API_KEY` in `.env` and a credit card on the Vercel account.
Every treg call is cached under `cache/`, so re-running never re-spends. Judgements go through
`judge.judge(state, questions)`; the backend is the one line at the bottom of `judge.py`
(`JUDGE_BACKEND = "jev"`, `"haiku"` or `"agent"`, or env `JUDGE_BACKEND`). Default is `haiku`:
Claude Haiku 5.5 through the Anthropic SDK, needs `ANTHROPIC_API_KEY` in `.env` and the venv
(`uv venv .venv && uv pip install -p .venv/bin/python anthropic`, run with `.venv/bin/python`). With the agent backend the pipeline
stops and writes `judgements/pending.json`; the agent fills `judgements/answers.json` and you re-run.

Config at the top of `pipeline.py`: topics, product description, top/keep post counts, thresholds,
email lookup cap and per-call cost cap, overall treg budget.
