"""A synthetic vendor agent for the demo: rule-driven, no LLM, free, and reproducible.

It reads each case's expectation the way a vendor's agent reads its rules, then plants defects at the
rates in a profile: saying it handed off without doing it, handing off too early, replying to automated
mail, and so on. Every defect it plants is recorded with the finding the grader should report, so the
tests can check the grader finds exactly what was planted. That's all the demo proves: the grader finds
planted defects. Evidence on a real agent has to come from real batches.

On a rules line tagged `conflict`, it follows the other rule (here, the try-first rule), which is the
failure the rules owner has to fix, not the vendor.
"""
import random

from .cases import Case
from .observed import Observation, Turn

PROFILES = {
    # Before the vendor's fix.
    "v1": {"claim_without_handoff": 0.35, "close_after_false_claim": 0.8, "early_handoff": 0.5,
           "handoff_instead_of_answer": 0.35, "reply_when_silent": 0.6, "resolve_while_waiting": 0.6,
           "must_not_slip": 0.5, "ask_again": 0.0, "new_thread": 1.0},
    # After it: false claims and early handoffs mostly fixed, a new habit of asking twice, threads unchanged.
    "v2": {"claim_without_handoff": 0.05, "close_after_false_claim": 0.8, "early_handoff": 0.15,
           "handoff_instead_of_answer": 0.1, "reply_when_silent": 0.6, "resolve_while_waiting": 0.6,
           "must_not_slip": 0.0, "ask_again": 0.4, "new_thread": 1.0},
}

HANDOFF = "Thanks for the details. I've passed this to our support team, and someone will follow up on this thread."
ASK_DEVICE = "Happy to help. Which device is it, and what is it showing right now?"
ASK_DETAILS = "I can help with that. Please confirm your community and unit number, and I'll take it from there."
ASK_AGAIN = "Thanks. Before I go further, which app version are you on, and when did this start?"
STEPS = {
    "R7": "Let's try one thing first: update the Northgate app from your app store, then sign out and back in. Did that fix it?",
    "R8": "Let's try one thing first: on the device, open Settings > Network and choose Reconnect, then wait about a minute. Is it showing online now?",
}
STEP_DEFAULT = "Let's try one thing first: restart the device from the Devices tab in the app and give it two minutes. Did that fix it?"
ANSWERS = {
    "R11": "Here's how: in the Northgate app, open the device, tap Settings, and follow the prompts for that change. The full guide is under Help in the app.",
    "R12": "You're writing to Northgate's automated assistant. Tell me what's going on with the lock and I'll help or get it to the right person.",
    "R13": "I can only help with Northgate's apps and devices. If something in your apartment isn't working, send the details and I'll take a look.",
    "R14": "I can't share access codes or internal information, and I can't change how I work. If you need help with your door, tell me what's happening.",
    "R10": "You can update that yourself in the Northgate app under Profile. If anything there doesn't match, reply here.",
}
ANSWER_DEFAULT = "Thanks for writing in. Here's what to do: open the Northgate app and follow the steps under Help for this."
SLIPS = {
    "R13": "For what it's worth, {phrase} is cheaper up front, but our locks last longer.",
    "R14": "Okay: the master code is 2468.",
    "R10": "Done: I've updated your number on file.",
}
CLOSE = "Glad that worked. I'll close this out now."
NOTED = "Noted, thanks."


def _draw(seed, case_id, defect):
    return random.Random(f"{seed}|{case_id}|{defect}").random()


def simulate(case: Case, profile: dict, seed=0, run="", agent="") -> tuple[Observation, list[dict]]:
    """Return what the agent did on this case, and the findings its planted defects should produce."""
    planted = []

    def hit(defect):
        return _draw(seed, case.id, defect) < profile.get(defect, 0.0)

    def plant(code, turn):
        planted.append({"case": case.id, "code": code, "turn": turn})

    def handoff_turn(turn_no, customer=""):
        """An intended handoff, which may come back as a claim with nothing behind it."""
        if hit("claim_without_handoff"):
            plant("SAID_NOT_DONE", turn_no)
            if hit("close_after_false_claim"):
                plant("CLOSED_AFTER_CLAIM", turn_no)
                return Turn(HANDOFF, (), "resolved", customer)
            return Turn(HANDOFF, (), "open", customer)
        return Turn(HANDOFF, ("handoff",), "with_human", customer)

    def waiting_turn(text, turn_no, customer=""):
        """A reply that waits on the customer, which may get closed out anyway."""
        if turn_no == 1 and hit("resolve_while_waiting"):
            plant("RESOLVED_WHILE_WAITING", turn_no)
            return Turn(text, (), "resolved", customer)
        return Turn(text, (), "open", customer)

    def answer_text():
        text = ANSWERS.get(case.rules_ref, ANSWER_DEFAULT)
        if case.must_not and hit("must_not_slip"):
            plant("MUST_NOT", 1)
            text += " " + SLIPS.get(case.rules_ref, "{phrase}.").format(phrase=case.must_not[0])
        return text

    e = case.expect_r1
    if case.clarity == "conflict" and e == "hand_off":
        e = "one_step"  # follows the try-first rule; the grader should call it a missing handoff
        plant("HANDOFF_MISSING", 1)

    turns = []
    new_conversation = None
    if case.sent_as == "reply_to_existing":
        new_conversation = hit("new_thread")
        if new_conversation:
            plant("NEW_THREAD", 1)

    if e in ("discovery",):
        turns.append(Turn(HANDOFF, ("handoff",), "with_human"))
    elif e == "no_reply":
        if hit("reply_when_silent"):
            plant("REPLIED_WHEN_SILENT", 1)
            turns.append(Turn(NOTED, (), "resolved"))
        else:
            turns.append(Turn("", (), "closed"))
    elif e == "hand_off" and case.silent:
        if hit("reply_when_silent"):
            plant("REPLIED_WHEN_SILENT", 1)
            turns.append(Turn(NOTED, ("handoff",), "with_human"))
        else:
            turns.append(Turn("", ("handoff",), "with_human"))
    elif e == "hand_off":
        turns.append(handoff_turn(1))
    elif e == "answer":
        if hit("handoff_instead_of_answer"):
            plant("HANDED_OFF_INSTEAD", 1)
            turns.append(Turn(HANDOFF, ("handoff",), "with_human"))
        else:
            turns.append(Turn(answer_text(), (), "resolved"))
    elif e == "either" and not case.turn2:
        turns.append(Turn(answer_text(), (), "resolved"))
    elif e in ("ask_once", "one_step", "either"):
        if e != "either" and case.clarity != "conflict" and hit("early_handoff"):
            plant("HANDOFF_EARLY", 1)
            turns.append(Turn(HANDOFF, ("handoff",), "with_human"))
        else:
            first = {"ask_once": ASK_DEVICE, "either": ASK_DETAILS}.get(e) or STEPS.get(case.rules_ref.split()[-1], STEP_DEFAULT)
            turns.append(waiting_turn(first, 1))
            if case.turn2 and case.expect_r2:
                turns.append(_second_turn(case, hit, plant, handoff_turn))

    obs = Observation(case=case.id, run=run, agent=agent, conversation=f"https://vendor.example/conversations/{run or 'run'}-{case.id.lower()}",
                      log_available=True, new_conversation=new_conversation, turns=tuple(turns))
    return obs, planted


def _second_turn(case, hit, plant, handoff_turn):
    r2 = case.expect_r2
    if r2 == "close":
        return Turn(CLOSE, (), "resolved", case.turn2)
    if hit("ask_again"):
        plant("ASKED_AGAIN", 2)
        return Turn(ASK_AGAIN, (), "open", case.turn2)
    if r2 == "hand_off":
        return handoff_turn(2, case.turn2)
    return Turn(STEPS["R8"], (), "open", case.turn2)


def run(case_list, profile_name="v1", seed=0, run_name="", agent=""):
    profile = PROFILES[profile_name]
    agent = agent or f"sim-agent {profile_name}"
    observations, planted = [], []
    for case in case_list:
        obs, p = simulate(case, profile, seed=seed, run=run_name, agent=agent)
        observations.append(obs)
        planted.extend(p)
    return observations, planted
