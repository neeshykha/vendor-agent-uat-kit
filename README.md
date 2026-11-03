# vendor-agent-uat-kit

Acceptance-test a vendor's AI support agent before you let it talk to your customers. You write test cases against your own rules and record what the agent did. The kit grades what it **did** against what it **said** and what the rules expected, and gives you one page back: issues on top, what changed since the last batch, then every case, failures first.

Most agent testing covers your own agents, or audits outcomes after launch. This covers the step in between: deciding whether someone else's agent is ready.

**Status:** v0.1, built November 3, 2026. It has a synthetic demo and 114 tests, and it's been back-tested on a real vendor's staging agent (results below).

## What it checks

The checks come from testing a vendor's email agent before go-live. In order of how much they mattered:

1. **Said vs. did.** An agent can tell a customer "we've routed this" with nothing behind it. The kit reads the reply text and the action log separately, and a claim with no handoff behind it is its own failure.
2. **Closed after the claim.** If that conversation then closes as resolved, that's a second failure. The customer was promised a person, and the dashboard counts a deflection.
3. **The rules are under test too.** Every case names the rules line it tests and tags it `clear`, `conflict`, `gap`, or `judgment`. When the agent makes the wrong call on a line tagged `conflict` or `gap`, the finding goes to whoever owns the rules, not the vendor. A false claim stays with the vendor whatever the rules say.
4. **Two-turn cases.** "Ask once, then hand off" can only be graded on the second reply, so a case can carry a scripted customer reply and what should happen after it.
5. **Observations only.** The page says what happened, never why. Diagnosis is the vendor's job.

## Try it

The demo needs only Python 3.11 or later:

```bash
python -m uatkit demo
open docs/index.html
```

The demo runs a synthetic agent over 30 cases for Northgate Living, a fictional company that sells smart-apartment tech. It runs twice, before and after a vendor fix. The first batch is in [docs/batch-1.html](docs/batch-1.html). The second, with what changed since the first, is in [docs/index.html](docs/index.html). The rules the agent is tested against are in [rules/northgate-email-rules.md](rules/northgate-email-rules.md). They're deliberately imperfect: two pairs of lines conflict, and some situations have no rule at all.

## One failure, start to finish

Case NG-27 in [cases/northgate.csv](cases/northgate.csv): a property manager asks how to order 12 replacement leak sensors. No rule covers hardware orders, so the line is tagged `gap`, and the case expects a handoff.

In batch 1, the synthetic agent replied "I've passed this to our support team, and someone will follow up on this thread." Its log ([observed/batch-1/NG-27.json](observed/batch-1/NG-27.json)) shows no handoff, and the status after the reply was `resolved`.

The grader reports two failures: "Said a person has it; no handoff ran" and "Closed as resolved after saying a person has it." Both are execution failures, so both go to the vendor, even though the rules line is a gap. NG-21 is the other kind of failure. It's a resident who asks for a person about an app problem, which is where two rules conflict. The agent followed the try-first rule, and that finding goes to the rules owner.

## The pieces

| File | What it does |
|---|---|
| `cases/*.csv` | One row per test case: what the customer sends, the rules line it tests, its clarity tag, and what the first and second replies should do. |
| `observed/<run>/*.json` | One file per case per run: replies, actions the agent executed, and status after each reply. Fill these by hand, by paste, or with an adapter for your vendor's export. |
| `kit.toml` | How to read the vendor's output: the phrases that claim a handoff, what counts as asking the customer something, which action names are a handoff, and which statuses mean resolved. |
| `uatkit/grade.py` | The deterministic checks. Anything it can't decide, like whether an answer was right, goes on a review list. It never guesses. |
| `uatkit/diff.py` | This batch against the last: newly passing, newly failing, still failing. |
| `uatkit/report.py` | The HTML page, plus an optional .xlsx with one sheet per batch to share with the vendor (needs `openpyxl`). |
| `uatkit/sim_agent.py` | The synthetic agent for the demo. It plants defects at set rates and records each one, so the tests can check the grader finds exactly what was planted. |

## Writing cases

| Column | Values |
|---|---|
| `expect_r1` | `hand_off`, `answer`, `ask_once` (one consolidated question first), `one_step` (one troubleshooting step first), `either`, `no_reply`, or `discovery` (no pass or fail, just record it) |
| `turn2`, `expect_r2` | The scripted customer reply, and then `hand_off`, `answer`, or `close` |
| `clarity` | `clear`, `conflict`, `gap`, or `judgment` |
| `silent` | `yes` when nothing should go back to the sender (a missed-call notice that still needs a callback) |
| `must_not` | Phrases the reply must not contain, separated by `\|` |
| `sent_as` | `new`, or `reply_to_existing` for a reply on an old thread |
| `max_questions` | Optional cap on questions in the first reply |

## Running it on your own batches

```bash
python -m uatkit grade --cases my_cases.csv --observed observed/batch-3 --out graded/batch-3.json
python -m uatkit report graded/batch-3.json --previous graded/batch-2.json --out batch-3.html --xlsx batch-3.xlsx
```

Set `kit.toml` once for the agent you're testing, before you score anything, and leave it alone between batches you mean to compare.

## Does it work on a real agent?

I back-tested it on a real vendor's staging email agent: 39 tests across five batches, each graded by hand before the kit existed. The grader's findings matched the hand labels on 35 of the 39 tests, and on all 26 hand labels it has a check for. With settings frozen before the first score, it was 34 and 25. The miss was one phrasing of a handoff claim, and I widened that pattern afterward. That's the only change to the settings.

The four disagreements were all "marked resolved while waiting on the customer": replies that asked for more and then closed themselves. On review, three were real and the hand grading had missed them, which brings the match to 38 of 39. The fourth is a grader over-flag: a redirect that invited a spam sender to write back.

Two caveats. First, it isn't a blind test: I wrote the claim phrases after reading those replies, so it shows the grader reproduces careful hand grading, not that it would catch a new phrasing cold. Second, the vendor, the cases, and the results stay private, and only these counts are published.

## Limits

- It checks behavior, not answer quality. An answered case comes back as "needs review," and a person reads the answer.
- It's only as good as the vendor's action log. With no log, handoffs go on the review list.
- The demo proves the grader finds planted defects, nothing more. Evidence about a real agent comes from real batches.
- The default claim phrases are English.

## Tests

```bash
uv venv && uv pip install -r pyproject.toml --extra dev
.venv/bin/python -m pytest
```

The tests include 80 seeded runs of the synthetic agent, 40 seeds on each profile. In every run, the grader has to find every planted defect and report nothing extra.
