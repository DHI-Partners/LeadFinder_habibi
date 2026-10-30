"""Signal-first lead finder for Habibi (cafe.habibi-erp.com).

Stages (each cached under cache/, so re-runs never re-spend):
  search  -> topic  -> engage -> people -> emails -> run.json
Run:  python3 pipeline.py            (re-run after filling judgements/answers.json if it stops)
"""
import hashlib
import json
import pathlib
import re
import subprocess
import sys
import time

import judge as J

ROOT = pathlib.Path(__file__).parent
CACHE = ROOT / "cache"
CACHE.mkdir(exist_ok=True)
RUNS = ROOT / "runs"
RUNS.mkdir(exist_ok=True)

TOPICS = [
    "restaurant online ordering",
    "orders via WhatsApp",
    "заказы через Telegram",
    "бот для кафе заказы",
    "автоматизация ресторана доставка",
    "прием заказов кафе",
]
TOPIC_CATEGORY = (
    "cafes, restaurants or food delivery businesses taking customer orders online or through "
    "messengers such as Telegram or WhatsApp (ordering bots, order automation, delivery ops)"
)
PRODUCT = (
    "Habibi (cafe.habibi-erp.com): a 'digital employee' for cafes, kitchens and delivery. A trained "
    "assistant answers customers in Telegram (WhatsApp coming) using the menu, prices and hours, "
    "collects the order and sends it to the owner to accept. Owner, kitchen and courier dashboards, "
    "chat takeover, stop-list and delivery zones. Built on ERPNext. Sold to small food businesses, "
    "starting from one location."
)
TOP_POSTS = 120
KEEP_POSTS = 15
TOPIC_MIN_P = 0.70
FIT_MIN = 1.5
EMAIL_MAX_LOOKUPS = 40
EMAIL_MAX_COST_PER_CALL = "0.03"
TREG_BUDGET_USD = 0.90  # stop spending on treg once this much has been charged in total

POST_QUESTIONS = {
    "about_topic": {
        "type": "boolean",
        "instructions": f"Is this post about {TOPIC_CATEGORY}?",
    }
}
PERSON_QUESTIONS = {
    "fit": {
        "type": "score",
        "instructions": (
            "How good a lead is this person for the product described, given their headline and "
            "what they did on the post? Score 0, 1 or 2 by the criteria."
        ),
        "criteria": [
            "not a lead: student, recruiter, HR, marketing/dev agency or freelancer, software vendor "
            "or consultant selling to restaurants, journalist, or someone with no link to food service",
            "user: a manager, operations, marketing or front-of-house employee at a cafe, restaurant, "
            "bakery, cloud kitchen or food delivery business; or a small-business adjacent operator "
            "(shop, rentals, services) who takes orders by chat",
            "decision maker: owner, co-founder, CEO, general manager, director or head at a cafe, "
            "restaurant, bakery, food chain, cloud kitchen or food delivery business",
        ],
    },
    "role": {
        "type": "choice",
        "instructions": "Which role best describes this person?",
        "criteria": {
            "owner_founder": "owns, founded or runs a cafe, restaurant, bakery, kitchen or delivery business",
            "restaurant_ops": "operations, management or staff role inside a food-service business",
            "marketing_growth": "marketing, growth or sales role at a food or hospitality business",
            "agency_freelancer": "agency, consultant or freelancer serving restaurants or small businesses",
            "vendor": "works at a software or hardware vendor selling to restaurants (POS, ordering, delivery)",
            "other": "anything else, including students, recruiters, unrelated industries",
        },
    },
}


def log(*a):
    print(*a, file=sys.stderr, flush=True)


def treg_call(tool, spend, query=None, data=None, headers=None, cache_key=None):
    """Call treg through its CLI; return parsed JSON. Caches by cache_key; tracks charged USD."""
    cf = CACHE / f"{cache_key}.json" if cache_key else None
    if cf and cf.exists():
        out = json.loads(cf.read_text())
        charged = out.get("_treg_meta", {}).get("charged", 0.0)
        spend["treg_usd"] = round(spend.get("treg_usd", 0) + charged, 6)
        spend.setdefault("treg_calls", []).append({"tool": tool, "charged": charged, "ok": True, "cached": True})
        return out
    if spend.get("treg_usd", 0) >= TREG_BUDGET_USD:
        raise RuntimeError(f"treg budget {TREG_BUDGET_USD} reached")
    cmd = ["treg", "call", tool]
    for k, v in (query or {}).items():
        cmd += ["--query", f"{k}={v}"]
    if data is not None:
        cmd += ["--method", "POST", "--data", json.dumps(data)]
    for h in headers or []:
        cmd += ["--header", h]
    p = subprocess.run(cmd, capture_output=True, text=True)
    m = re.search(r"charged \$([0-9.]+)", p.stderr)
    charged = float(m.group(1)) if m else 0.0
    spend["treg_usd"] = round(spend.get("treg_usd", 0) + charged, 6)
    spend.setdefault("treg_calls", []).append({"tool": tool, "charged": charged, "ok": p.returncode == 0})
    log(f"  treg {tool} charged ${charged} (total ${spend['treg_usd']})")
    try:
        out = json.loads(p.stdout) if p.stdout.strip() else {}
    except json.JSONDecodeError:
        out = {"_raw": p.stdout[:2000]}
    out["_treg_meta"] = {"charged": charged, "stderr": p.stderr[-500:], "rc": p.returncode}
    if cf:
        cf.write_text(json.dumps(out, ensure_ascii=False))
    return out


# ---------- stage 1: search ----------
def stage_search(spend):
    posts = {}
    for i, topic in enumerate(TOPICS):
        res = treg_call(
            "harvestapi.linkedin.post.search", spend,
            query={"search": topic, "postedLimit": "week", "sortBy": "relevance"},
            cache_key="search_" + hashlib.sha1(topic.encode()).hexdigest()[:10],
        )
        for e in res.get("elements", []):
            pid = e.get("id")
            if not pid:
                continue
            a = e.get("author") or {}
            eng = e.get("engagement") or {}
            p = posts.setdefault(pid, {
                "id": pid,
                "url": e.get("linkedinUrl"),
                "content": e.get("content") or "",
                "author": {
                    "id": a.get("id"), "name": a.get("name"), "headline": a.get("info"),
                    "url": a.get("linkedinUrl"), "type": a.get("type"),
                },
                "posted_at": (e.get("postedAt") or {}).get("date"),
                "likes": eng.get("likes") or 0,
                "comments": eng.get("comments") or 0,
                "shares": eng.get("shares") or 0,
                "topics": [],
            })
            p["topics"].append(topic)
    ranked = sorted(posts.values(), key=lambda p: (-p["likes"], -p["comments"]))
    for r, p in enumerate(ranked, 1):
        p["rank"] = r
    return ranked, ranked[:TOP_POSTS]


# ---------- stage 2: topic judge ----------
def stage_topic(top, spend):
    pending = 0
    for p in top:
        state = {"author": {"name": p["author"]["name"], "headline": p["author"]["headline"]},
                 "post": p["content"][:3000]}
        res = J.judge(state, POST_QUESTIONS, spend)
        if res is None:
            pending += 1
            continue
        q = res["about_topic"]
        p["about_topic"] = q
        p["on_topic_p"] = float(q.get("probabilities", {}).get("true", q.get("probability", 0)))
        p["judge"] = res.get("_judge")
    if pending:
        raise J.Pending(f"{pending} post judgements pending")
    kept = [p for p in top if p.get("on_topic_p", 0) >= TOPIC_MIN_P][:KEEP_POSTS]
    for p in kept:
        p["kept"] = True
    return kept


# ---------- stage 3: reactions + comments ----------
def stage_engage(kept, spend):
    people = {}

    def person(actor):
        pid = actor.get("id") or actor.get("linkedinUrl")
        if not pid:
            return None
        return people.setdefault(pid, {
            "id": pid, "name": actor.get("name"), "headline": actor.get("position") or actor.get("info"),
            "url": actor.get("linkedinUrl"), "signals": [],
        })

    for p in kept:
        r = treg_call("harvestapi.linkedin.post.reactions", spend,
                      query={"post": p["url"], "page": 1}, cache_key=f"reactions_{p['id']}")
        for e in r.get("elements", []):
            who = person(e.get("actor") or {})
            if who:
                who["signals"].append({"type": "reaction", "post_id": p["id"],
                                       "reaction": e.get("reactionType")})
        c = treg_call("harvestapi.linkedin.post.comments", spend,
                      query={"post": p["url"], "page": 1}, cache_key=f"comments_{p['id']}")
        for e in c.get("elements", []):
            who = person(e.get("actor") or e.get("author") or {})
            if who:
                who["signals"].append({"type": "comment", "post_id": p["id"],
                                       "text": (e.get("commentary") or e.get("text") or "")[:600]})
        p["n_reactions"] = len(r.get("elements", []))
        p["n_comments"] = len(c.get("elements", []))
    return list(people.values())


# ---------- stage 4: person judge ----------
def stage_people(people, spend):
    pending = 0
    for who in people:
        sig = [f"{s['reaction']} reaction" if s["type"] == "reaction" else f"commented: {s['text']}"
               for s in who["signals"]]
        state = {"position": who["headline"] or "", "name": who["name"], "signals": sig,
                 "product": PRODUCT}
        res = J.judge(state, PERSON_QUESTIONS, spend)
        if res is None:
            pending += 1
            continue
        fit, role = res["fit"], res["role"]
        probs = fit.get("probabilities", {})
        if "score" in fit:
            score = float(fit["score"])
        else:
            score = sum(float(k) * float(v) for k, v in probs.items())
        who["fit"] = {"score": round(score, 3), "probabilities": probs, "confidence": fit.get("confidence")}
        who["role"] = {"choice": role.get("choice"), "probabilities": role.get("probabilities", {}),
                       "confidence": role.get("confidence")}
        who["tier"] = "decision_maker" if score >= FIT_MIN else ("user" if score >= 0.5 else "not_lead")
        who["judge"] = res.get("_judge")
    if pending:
        raise J.Pending(f"{pending} person judgements pending")
    people.sort(key=lambda w: -w.get("fit", {}).get("score", 0))
    return people


# ---------- stage 5: emails ----------
def stage_emails(people, spend):
    targets = [w for w in people if w.get("fit", {}).get("score", 0) >= FIT_MIN and w.get("url")]
    n = 0
    for who in targets:
        if n >= EMAIL_MAX_LOOKUPS:
            who["email"] = {"status": "skipped", "reason": "lookup cap"}
            continue
        try:
            res = treg_call("treg.people.email.find", spend,
                            data={"linkedin_url": who["url"].split("?")[0], "full_name": who["name"]},
                            headers=[f"X-Treg-Route-Max-Cost: {EMAIL_MAX_COST_PER_CALL}"],
                            cache_key=f"email_{re.sub(r'[^A-Za-z0-9_-]', '_', who['id'])}")
        except RuntimeError as e:
            who["email"] = {"status": "skipped", "reason": str(e)}
            continue
        n += 1
        out = res.get("output") or {}
        meta = res.get("_treg") or {}
        email = out.get("email") if isinstance(out, dict) else None
        who["email"] = {
            "status": "hit" if email else "miss",
            "email": email,
            "provider": meta.get("served_by"),
            "tried": meta.get("tried"),
            "charged": res.get("_treg_meta", {}).get("charged"),
        }
        if email:
            v = treg_call("treg.people.email.verify", spend, data={"email": email},
                          headers=["X-Treg-Route-Max-Cost: 0.02"],
                          cache_key=f"verify_{re.sub(r'[^A-Za-z0-9_-]', '_', email)}")
            vo = v.get("output") or {}
            who["email"]["verify"] = {
                "verdict": vo.get("verdict") or vo.get("status") or vo.get("result"),
                "provider": (v.get("_treg") or {}).get("served_by"),
                "charged": v.get("_treg_meta", {}).get("charged"),
            }
    return targets


def main():
    spend = {}
    t0 = time.time()
    try:
        all_posts, top = stage_search(spend)
        log(f"search: {len(all_posts)} unique posts, judging top {len(top)}")
        kept = stage_topic(top, spend)
        log(f"topic: kept {len(kept)} posts")
        people = stage_engage(kept, spend)
        log(f"engage: {len(people)} people")
        people = stage_people(people, spend)
        dm = [w for w in people if w["tier"] == "decision_maker"]
        log(f"people: {len(dm)} decision makers")
        targets = stage_emails(people, spend)
        hits = [w for w in targets if w["email"].get("status") == "hit"]
        log(f"emails: {len(hits)} hits of {len(targets)} lookups")
    except J.Pending as e:
        log(f"STOP: {e}. Fill judgements/answers.json from judgements/pending.json and re-run.")
        sys.exit(2)

    run = {
        "ran_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "duration_s": round(time.time() - t0, 1),
        "product": PRODUCT,
        "topics": TOPICS,
        "config": {"top_posts": TOP_POSTS, "keep_posts": KEEP_POSTS, "topic_min_p": TOPIC_MIN_P,
                   "fit_min": FIT_MIN, "judge_backend": J.JUDGE_BACKEND},
        "funnel": {
            "posts_found": len(all_posts), "posts_judged": len(top), "posts_on_topic": len(kept),
            "people": len(people), "decision_makers": len(dm), "emails": len(hits),
        },
        "posts": top,
        "people": people,
        "spend": {
            "treg_usd": spend.get("treg_usd", 0),
            "treg_calls": spend.get("treg_calls", []),
            "jev_usd": round(spend.get("jev_usd", 0), 6),
            "jev_calls": spend.get("jev_calls", 0),
            "claude_usd": round(spend.get("claude_usd", 0), 6),
            "claude_calls": spend.get("claude_calls", 0) + spend.get("claude_calls_cached", 0),
            "claude_tokens_in": spend.get("claude_tokens_in", 0),
            "claude_tokens_out": spend.get("claude_tokens_out", 0),
            "agent_calls": spend.get("agent_calls", 0),
        },
    }
    out = RUNS / f"run_{run['ran_at'].replace(':', '')}.json"
    out.write_text(json.dumps(run, indent=1, ensure_ascii=False))
    (RUNS / "latest.json").write_text(json.dumps(run, ensure_ascii=False))
    log(f"wrote {out}")


if __name__ == "__main__":
    main()
