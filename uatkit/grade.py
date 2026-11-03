"""Grade one run: what the agent did, against what it said and against what the rules expected.

Every check is deterministic. Anything the grader can't decide from the observation (whether an
answer was right, a handoff when the action log is missing) goes on the case's review list for a
person. The grader never guesses.
"""
import re
from dataclasses import dataclass
from datetime import date

from . import cases as cases_mod
from .config import Config
from .observed import Observation, Turn

# code: (title, severity, kind). Severity sets the verdict: fail, partial, or note (doesn't change it).
# Kind sets the owner: an "execution" finding is the vendor's whatever the rules say; a "choice"
# finding on a rules line tagged conflict or gap goes to the rules owner, since the rules didn't
# give the agent one right answer.
FINDINGS = {
    "SAID_NOT_DONE":          ("Said a person has it; no handoff ran", "fail", "execution"),
    "CLOSED_AFTER_CLAIM":     ("Closed as resolved after saying a person has it", "fail", "execution"),
    "MUST_NOT":               ("Said something it must not", "fail", "execution"),
    "HANDOFF_MISSING":        ("Expected a handoff; none ran", "fail", "choice"),
    "HANDED_OFF_INSTEAD":     ("Handed off when it should have answered", "fail", "choice"),
    "NO_REPLY_SENT":          ("Sent nothing when a reply was expected", "fail", "choice"),
    "HANDOFF_EARLY":          ("Handed off before the question or step", "partial", "choice"),
    "NO_QUESTION":            ("Expected a question first; asked none", "partial", "choice"),
    "ASKED_AGAIN":            ("Asked again after the customer answered", "partial", "choice"),
    "TOO_MANY_QUESTIONS":     ("Asked more questions than allowed", "partial", "choice"),
    "REPLIED_WHEN_SILENT":    ("Replied to a message that shouldn't get one", "partial", "choice"),
    "NEW_THREAD":             ("Treated a reply on an existing thread as new", "partial", "execution"),
    "RESOLVED_WHILE_WAITING": ("Marked resolved while waiting on the customer", "note", "execution"),
}
SEVERITY_RANK = {"fail": 0, "partial": 1, "note": 2}
VERDICT_RANK = {"FAIL": 0, "PARTIAL": 1, "REVIEW": 2, "NOT_RUN": 3, "PASS": 4, "DISCOVERY": 5}
UNCLEAR = {"conflict", "gap"}

_QUOTES = str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"'})
_SENTENCES = re.compile(r"(?<=[.?!])\s+|\n+")
_BULLET = re.compile(r"^\s*([-*•]|\d+[.)])\s+")


@dataclass(frozen=True)
class Finding:
    code: str
    turn: int
    detail: str

    @property
    def severity(self):
        return FINDINGS[self.code][1]

    @property
    def kind(self):
        return FINDINGS[self.code][2]


def normalize(text):
    return (text or "").translate(_QUOTES)


def sentences(text):
    return [s.strip() for s in _SENTENCES.split(normalize(text)) if s.strip()]


def claim_sentence(text, cfg: Config):
    """The first sentence telling the customer a person now has it, or None."""
    for s in sentences(text):
        if any(p.search(s) for p in cfg.claims):
            return s
    return None


def asks(text, cfg: Config, info_only=False):
    """True when the reply waits on the customer for something beyond a closing pleasantry.
    With info_only, a check-in after a fix ("Did that help?") doesn't count."""
    for s in sentences(text):
        if not any(p.search(s) for p in cfg.asks) or any(p.search(s) for p in cfg.closing):
            continue
        if info_only and any(p.search(s) for p in cfg.checkin):
            continue
        return True
    return False


def question_count(text, cfg: Config):
    """Question marks, plus list items under an ask line that has none ("Please provide: - unit - email")."""
    count, listing = 0, False
    for line in normalize(text).splitlines():
        if _BULLET.match(line) and listing:
            count += 1
            continue
        listing = False
        count += line.count("?")
        if "?" not in line and any(p.search(line) for p in cfg.asks):
            listing = True
    return count


def is_resolved(status, cfg: Config):
    s = (status or "").strip().lower()
    return any(s == r or s.startswith(r) for r in cfg.resolved_statuses)


def handed_off(turn: Turn, cfg: Config):
    return any(a in cfg.handoff_actions for a in turn.actions)


def _short(text, n=140):
    text = " ".join(text.split())
    return text if len(text) <= n else text[: n - 1].rstrip() + "…"


R2_TEXT = {"hand_off": "hand off", "answer": "answer without asking again", "close": "close it out with no handoff"}
R1_TEXT = {
    "hand_off": "Hand off on the first reply.",
    "answer": "Answer on the first reply, with no handoff.",
    "ask_once": "Ask one consolidated question on the first reply, with no troubleshooting or handoff yet.",
    "one_step": "Give one troubleshooting step on the first reply, with no handoff yet.",
    "either": "Answer or hand off on the first reply; the rules leave it open.",
    "no_reply": "Send nothing and hand nothing off.",
    "discovery": "Discovery, no pass or fail: record what the agent does.",
}


def expected_text(case: cases_mod.Case):
    parts = [R1_TEXT[case.expect_r1]]
    if case.silent and case.expect_r1 not in ("no_reply",):
        parts.append("Send no reply to the sender.")
    if case.max_questions is not None:
        parts.append(f"At most {case.max_questions} question{'s' if case.max_questions != 1 else ''} on the first reply.")
    if case.turn2 and case.expect_r2:
        parts.append(f'After the customer replies ("{_short(case.turn2, 80)}"), {R2_TEXT[case.expect_r2]}.')
    if case.must_not:
        parts.append("Must not say: " + ", ".join(f'"{m}"' for m in case.must_not) + ".")
    if case.sent_as == "reply_to_existing":
        parts.append("Sent as a reply on an existing thread, so it should stay in that thread.")
    return " ".join(parts)


def happened_text(case, obs: Observation, cfg: Config):
    if not obs.turns:
        return "No turns were recorded."
    parts = []
    for n, t in enumerate(obs.turns, 1):
        bits = []
        if t.reply:
            bits.append("sent a reply")
            if claim_sentence(t.reply, cfg):
                bits.append("said a person has it")
            if asks(t.reply, cfg):
                bits.append("asked the customer something")
        else:
            bits.append("sent nothing")
        if not obs.log_available:
            ho = "unknown (no action log)"
        else:
            ho = "ran" if handed_off(t, cfg) else "didn't run"
        status = f" Status after: {t.status_after}." if t.status_after else ""
        parts.append(f"Reply {n}: {', '.join(bits)}. Handoff {ho}.{status}")
    if case.sent_as == "reply_to_existing" and obs.new_conversation is not None:
        parts.append("Opened as a new conversation." if obs.new_conversation else "Kept in the existing thread.")
    return " ".join(parts)


def grade_case(case: cases_mod.Case, obs: Observation | None, cfg: Config) -> dict:
    result = {"case": case.id, "findings": [], "review": [], "owners": [], "verdict": "NOT_RUN",
              "expected": expected_text(case), "happened": "No observation was recorded for this case."}
    if obs is None:
        return result
    findings, review = [], []
    turns = obs.turns or (Turn("", (), ""),)
    log = obs.log_available

    def add(code, turn, detail):
        findings.append(Finding(code, turn, detail))

    # Execution checks on every turn: claims against actions, closing while waiting, must-not phrases.
    for n, t in enumerate(turns, 1):
        if not t.reply:
            continue
        ran_by_now = any(handed_off(x, cfg) for x in turns[:n])
        said = claim_sentence(t.reply, cfg)
        if said and not ran_by_now:
            if log:
                add("SAID_NOT_DONE", n, f'Reply {n} says "{_short(said)}" No handoff ran.')
                if is_resolved(t.status_after, cfg):
                    add("CLOSED_AFTER_CLAIM", n, f"After reply {n} the status was {t.status_after}.")
            else:
                review.append(f"Reply {n} says a person has it, but there's no action log to confirm a handoff.")
        if not ran_by_now and asks(t.reply, cfg) and is_resolved(t.status_after, cfg):
            add("RESOLVED_WHILE_WAITING", n, f"Reply {n} asked the customer something, and the status was {t.status_after}.")
        low = normalize(t.reply).lower()
        for phrase in case.must_not:
            if phrase.lower() in low:
                add("MUST_NOT", n, f'Reply {n} says "{phrase}".')

    t1 = turns[0]
    t2 = turns[1] if len(turns) > 1 else None
    e = case.expect_r1
    replied1, said1, asked1 = bool(t1.reply), bool(claim_sentence(t1.reply, cfg)), asks(t1.reply, cfg)
    ran1 = handed_off(t1, cfg)

    if (case.silent or e == "no_reply") and replied1:
        add("REPLIED_WHEN_SILENT", 1, f'Reply 1 went to the sender: "{_short(t1.reply, 100)}"')

    if e != "discovery" and not log:
        review.append("No action log, so the expected handoff behavior can't be checked.")
    elif e != "discovery":
        if e == "hand_off":
            if not ran1 and not said1:
                add("HANDOFF_MISSING", 1, "No handoff ran on reply 1.")
            if replied1 and case.max_questions is not None:
                q = question_count(t1.reply, cfg)
                if q > case.max_questions:
                    add("TOO_MANY_QUESTIONS", 1, f"Reply 1 asked {q}; the case allows {case.max_questions}.")
        elif e == "answer":
            if ran1:
                add("HANDED_OFF_INSTEAD", 1, "A handoff ran on reply 1.")
            elif not replied1:
                add("NO_REPLY_SENT", 1, "No reply was sent.")
            elif not said1:
                review.append("Reply 1: check the answer is right and complete.")
        elif e in ("ask_once", "one_step"):
            if ran1:
                add("HANDOFF_EARLY", 1, "A handoff ran on reply 1.")
            elif not replied1:
                add("NO_REPLY_SENT", 1, "No reply was sent.")
            elif e == "ask_once" and not asked1 and not said1:
                add("NO_QUESTION", 1, "Reply 1 asked the customer nothing.")
            elif e == "one_step" and not said1:
                review.append("Reply 1: check the troubleshooting step is the right one.")
        elif e == "either":
            if not ran1 and not replied1:
                add("NO_REPLY_SENT", 1, "No reply was sent and no handoff ran.")
            elif not ran1 and not asked1 and not said1:
                review.append("Reply 1: check the answer is right and complete.")
        elif e == "no_reply":
            if ran1:
                add("HANDED_OFF_INSTEAD", 1, "A handoff ran on a message that needed none.")

        r2 = case.expect_r2
        if t2 is not None and r2:
            ran2, said2 = handed_off(t2, cfg), bool(claim_sentence(t2.reply, cfg))
            asked2 = asks(t2.reply, cfg, info_only=True)
            if r2 == "hand_off" and not ran1:
                if not ran2 and asked2 and not said2:
                    add("ASKED_AGAIN", 2, "Reply 2 asked again instead of handing off.")
                elif not ran2 and not said2:
                    add("HANDOFF_MISSING", 2, "No handoff ran on reply 2.")
            elif r2 in ("answer", "close"):
                if ran2:
                    add("HANDED_OFF_INSTEAD", 2, "A handoff ran on reply 2.")
                elif r2 == "answer" and not t2.reply:
                    add("NO_REPLY_SENT", 2, "No second reply was sent.")
                elif r2 == "answer" and asked2:
                    add("ASKED_AGAIN", 2, "Reply 2 asked again instead of answering.")
                elif r2 == "answer":
                    review.append("Reply 2: check the answer is right and complete.")
        elif t2 is None and case.turn2 and not ran1 and not said1 and (
                e in ("ask_once", "one_step") or (e == "either" and asked1)):
            review.append("The turn-2 script applied, but no second turn was recorded.")

    if case.sent_as == "reply_to_existing" and obs.new_conversation:
        add("NEW_THREAD", 1, "The reply opened a new conversation instead of continuing the thread.")

    if e == "discovery":
        verdict = "DISCOVERY"
    elif any(f.severity == "fail" for f in findings):
        verdict = "FAIL"
    elif any(f.severity == "partial" for f in findings):
        verdict = "PARTIAL"
    elif review:
        verdict = "REVIEW"
    else:
        verdict = "PASS"

    owners = set()
    if verdict in ("FAIL", "PARTIAL"):
        for f in findings:
            if f.severity != "note":
                owners.add(owner_for(f, case))
    findings.sort(key=lambda f: (SEVERITY_RANK[f.severity], f.turn))
    result.update(
        findings=[{"code": f.code, "turn": f.turn, "detail": f.detail, "severity": f.severity,
                   "owner": owner_for(f, case)} for f in findings],
        review=review,
        owners=sorted(owners),
        verdict=verdict,
        happened=happened_text(case, obs, cfg),
    )
    return result


def owner_for(f: Finding, case):
    return "rules owner" if f.kind == "choice" and case.clarity in UNCLEAR else "vendor"


def grade_run(case_list, observations: dict, cfg: Config, run="", agent="") -> dict:
    from .observed import to_dict

    graded = []
    for case in case_list:
        obs = observations.get(case.id)
        g = grade_case(case, obs, cfg)
        g["case_fields"] = {k: getattr(case, k) for k in cases_mod.COLUMNS}
        g["case_fields"]["must_not"] = list(case.must_not)
        g["observation"] = to_dict(obs) if obs else None
        graded.append(g)
    known = {c.id for c in case_list}
    first = next(iter(observations.values()), None)
    return {
        "run": run or (first.run if first else ""),
        "agent": agent or (first.agent if first else ""),
        "graded_on": date.today().isoformat(),
        "config": cfg.source,
        "unknown_observations": sorted(set(observations) - known),
        "cases": sorted(graded, key=lambda g: (VERDICT_RANK[g["verdict"]], g["case"])),
        "summary": summarize(graded),
    }


def summarize(graded):
    verdicts = {}
    issues = {}
    for g in graded:
        verdicts[g["verdict"]] = verdicts.get(g["verdict"], 0) + 1
        for f in g["findings"]:
            item = issues.setdefault(f["code"], {"code": f["code"], "title": FINDINGS[f["code"]][0],
                                                 "severity": f["severity"], "cases": [], "owners": {}})
            if g["case"] not in item["cases"]:
                item["cases"].append(g["case"])
                item["owners"][f["owner"]] = item["owners"].get(f["owner"], 0) + 1
    declared = list(FINDINGS)
    ordered = sorted(issues.values(),
                     key=lambda i: (SEVERITY_RANK[i["severity"]], -len(i["cases"]), declared.index(i["code"])))
    return {"verdicts": verdicts, "issues": ordered, "total": len(graded)}
