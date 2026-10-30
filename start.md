# Build a signal-first lead finder for my software product (https://cafe.habibi-erp.com) and a page to browse the run.

# Before you build
Treat every step below as a reference implementation, not a spec. Ask me first, a few
short questions at a time: my product and who buys it, the topics those buyers post
about, which networks to read, how many leads one run should produce, and where they
should land (a page, a CSV, my CRM). Then tell me the plan and what one run should
cost, wait for my go-ahead, and build for MY answers rather than the examples written
here.

## Setup
1. Set up treg: read https://treg.to/llms.txt and follow it (install the CLI,
   then `treg login`).
2. jev, optional to start. If I have a Vercel AI Gateway key
   (https://vercel.com/ai-gateway), put it in .env as AI_GATEWAY_API_KEY. jev: POST
   https://ai-gateway.vercel.sh/v4/ai/evaluation-model with headers Authorization: Bearer $KEY,
   ai-model-id: typesafe-ai/jev, ai-evaluation-model-specification-version: 4,
   ai-gateway-protocol-version: 0.0.1; body {"state", "questions"}. Types: choice, boolean, score.
   No key yet? Ask me whether to get one now or start without it. Without it, make
   each judgement yourself behind the same interface: take the same {"state",
   "questions"}, return the same shape with your own probabilities, and label those
   results judge: agent. Keep it to one function so switching to jev later is a one-
   line change, and tell me it is a stand-in: slower, dearer per decision and not
   calibrated the way jev is.

## Pipeline
3. Topics: <4 phrases buyers post about, e.g. "enrichment waterfall", "RevOps tooling">.
   `treg call harvestapi.linkedin.post.search --query search=<topic> --query postedLimit=week
   --query sortBy=relevance`. Rank candidates by likes, take the top 20.
4. jev per post: about_topic: boolean, "is this post about <category>?" over {author, post}.
   Keep the first 3 with probability ≥ 0.70.
5. For each kept post: `harvestapi.linkedin.post.reactions` and `harvestapi.linkedin.post.comments`
   (post=<url>). Merge people by id; record each signal (reacted with what / commented what).
6. jev per person over {position (headline), signals, product description}:
   fit: score over not a lead / user / decision maker, with signals for each level (students,
   recruiters and agencies are not leads; ICs in growth, RevOps, data or engineering are users;
   heads, directors, VPs, founders are decision makers);
   role: choice gtm_ops / engineer / founder_exec / agency_freelancer / vendor / other.
7. For everyone with fit ≥ 1.5: `treg call treg.people.email.find --data '{"full_name": "...",
   "company_name": "..."}'`. Routed; misses are free; cap with X-Treg-Route-Max-Cost.

## Page
8. Funnel (posts → on topic → people → decision makers → emails), the posts as LinkedIn-style
   cards with the on-topic score, the people ranked by fit with role and tier filters, and an
   inspector with the signals, both jev distributions and the contact with which provider hit.
   Show treg and jev spend separately.

# Sourced from: https://treg.to/jev
