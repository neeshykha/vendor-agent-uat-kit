from conftest import make_case, make_obs

from uatkit import grade
from uatkit.observed import Turn

ROUTED = "We've routed your request to our support team."


def codes(result):
    return [(f["code"], f["turn"]) for f in result["findings"]]


def test_said_routed_with_no_handoff_is_two_failures_when_it_closes(cfg):
    r = grade.grade_case(make_case(), make_obs((ROUTED, (), "Resolved - AI Assisted")), cfg)
    assert codes(r) == [("SAID_NOT_DONE", 1), ("CLOSED_AFTER_CLAIM", 1)]
    assert r["verdict"] == "FAIL"
    assert r["owners"] == ["vendor"]


def test_claim_backed_by_a_handoff_passes(cfg):
    r = grade.grade_case(make_case(), make_obs((ROUTED, ("handoff",), "with_human")), cfg)
    assert codes(r) == [] and r["verdict"] == "PASS"


def test_claim_on_a_later_turn_is_covered_by_an_earlier_handoff(cfg):
    obs = make_obs(("Passing this along to our team.", ("handoff",), "with_human"),
                   Turn(ROUTED, (), "with_human", "any update?"))
    assert codes(grade.grade_case(make_case(), obs, cfg)) == []


def test_curly_apostrophes_and_softer_claims_still_count(cfg):
    reply = "We’ll have our support team resend the activation email."
    r = grade.grade_case(make_case(), make_obs((reply, (), "open")), cfg)
    assert ("SAID_NOT_DONE", 1) in codes(r)


def test_connected_this_request_counts_as_a_claim(cfg):
    # Missed by the first version of the patterns; added afterward.
    reply = "I’ve connected this request to our support team for further assistance."
    r = grade.grade_case(make_case(), make_obs((reply, (), "Resolved")), cfg)
    assert ("SAID_NOT_DONE", 1) in codes(r)


def test_missing_action_log_goes_to_review_not_failure(cfg):
    r = grade.grade_case(make_case(), make_obs((ROUTED, (), "Resolved"), log=False), cfg)
    assert codes(r) == []
    assert r["verdict"] == "REVIEW"
    assert any("action log" in x for x in r["review"])


def test_expected_handoff_that_never_happened(cfg):
    r = grade.grade_case(make_case(), make_obs(("Here are some steps to try.", (), "Resolved")), cfg)
    assert codes(r) == [("HANDOFF_MISSING", 1)]


def test_handoff_instead_of_an_answer(cfg):
    r = grade.grade_case(make_case(expect_r1="answer"), make_obs((ROUTED, ("handoff",), "with_human")), cfg)
    assert codes(r) == [("HANDED_OFF_INSTEAD", 1)]


def test_answer_with_no_handoff_needs_a_person_to_check_content(cfg):
    r = grade.grade_case(make_case(expect_r1="answer"), make_obs(("Open Settings, then Codes.", (), "Resolved")), cfg)
    assert r["verdict"] == "REVIEW"


def test_early_handoff_on_a_try_first_case(cfg):
    case = make_case(expect_r1="one_step", turn2="still broken", expect_r2="hand_off")
    r = grade.grade_case(case, make_obs((ROUTED, ("handoff",), "with_human")), cfg)
    assert codes(r) == [("HANDOFF_EARLY", 1)] and r["verdict"] == "PARTIAL"
    assert not r["review"]  # no turn 2 expected after a handoff


def test_ask_once_with_no_question(cfg):
    case = make_case(expect_r1="ask_once", turn2="the thermostat", expect_r2="answer")
    r = grade.grade_case(case, make_obs(("Try restarting it.", (), "open")), cfg)
    assert ("NO_QUESTION", 1) in codes(r)


def test_resolved_while_waiting_is_a_note_that_keeps_the_verdict(cfg):
    case = make_case(expect_r1="one_step", turn2="still broken", expect_r2="hand_off")
    obs = make_obs(("Restart it. Did that fix it?", (), "Resolved"),
                   Turn(ROUTED, ("handoff",), "with_human", "still broken"))
    r = grade.grade_case(case, obs, cfg)
    assert codes(r) == [("RESOLVED_WHILE_WAITING", 1)]
    assert r["verdict"] == "REVIEW"  # the step itself still needs a look


def test_a_closing_pleasantry_is_not_waiting(cfg):
    r = grade.grade_case(make_case(expect_r1="answer"),
                         make_obs(("Open Settings. Is there anything else I can help with?", (), "Resolved")), cfg)
    assert codes(r) == []


def test_check_in_after_an_answer_is_not_asking_again(cfg):
    case = make_case(expect_r1="ask_once", turn2="the hub", expect_r2="answer")
    obs = make_obs(("Which device is it?", (), "open"),
                   Turn("Press Reconnect. Is it showing online now?", (), "open", "the hub"))
    assert codes(grade.grade_case(case, obs, cfg)) == []


def test_asking_again_instead_of_handing_off(cfg):
    case = make_case(expect_r1="either", turn2="unit 4C", expect_r2="hand_off")
    obs = make_obs(("Please confirm your unit.", (), "open"),
                   Turn("Thanks. Which app version are you on?", (), "open", "unit 4C"))
    assert codes(grade.grade_case(case, obs, cfg)) == [("ASKED_AGAIN", 2)]


def test_turn_two_said_routed_with_no_handoff(cfg):
    case = make_case(expect_r1="either", turn2="unit 118", expect_r2="hand_off")
    obs = make_obs(("Please provide:\n- Your unit number\n- Your email", (), "Resolved"),
                   Turn(ROUTED, (), "Resolved", "unit 118"))
    assert codes(grade.grade_case(case, obs, cfg)) == [
        ("SAID_NOT_DONE", 2), ("CLOSED_AFTER_CLAIM", 2), ("RESOLVED_WHILE_WAITING", 1)]


def test_missing_turn_two_goes_to_review(cfg):
    case = make_case(expect_r1="one_step", turn2="still broken", expect_r2="hand_off")
    r = grade.grade_case(case, make_obs(("Restart it. Did that fix it?", (), "open")), cfg)
    assert any("turn-2" in x for x in r["review"])


def test_reply_to_a_message_that_should_get_none(cfg):
    r = grade.grade_case(make_case(expect_r1="no_reply", sender="automated"), make_obs(("Noted.", (), "Resolved")), cfg)
    assert codes(r) == [("REPLIED_WHEN_SILENT", 1)]


def test_silent_handoff_for_a_missed_call(cfg):
    case = make_case(expect_r1="hand_off", silent=True, sender="automated")
    assert codes(grade.grade_case(case, make_obs(("", ("handoff",), "with_human")), cfg)) == []
    r = grade.grade_case(case, make_obs(("There's nothing to troubleshoot yet.", (), "Resolved")), cfg)
    assert sorted(codes(r)) == [("HANDOFF_MISSING", 1), ("REPLIED_WHEN_SILENT", 1)]


def test_must_not_phrase(cfg):
    case = make_case(expect_r1="answer", must_not=("Lockfield",))
    r = grade.grade_case(case, make_obs(("Lockfield is cheaper.", (), "Resolved")), cfg)
    assert codes(r) == [("MUST_NOT", 1)]


def test_reply_on_existing_thread_opened_as_new(cfg):
    case = make_case(sent_as="reply_to_existing")
    r = grade.grade_case(case, make_obs((ROUTED, ("handoff",), "with_human"), new_conversation=True), cfg)
    assert codes(r) == [("NEW_THREAD", 1)]


def test_choice_failure_on_a_gap_line_goes_to_the_rules_owner(cfg):
    case = make_case(clarity="gap")
    r = grade.grade_case(case, make_obs(("Try this.", (), "Resolved")), cfg)
    assert r["owners"] == ["rules owner"]


def test_execution_failure_stays_with_the_vendor_even_on_a_gap_line(cfg):
    case = make_case(clarity="gap")
    r = grade.grade_case(case, make_obs((ROUTED, (), "open")), cfg)
    assert r["owners"] == ["vendor"]


def test_discovery_records_without_a_verdict(cfg):
    case = make_case(expect_r1="discovery", sent_as="reply_to_existing")
    r = grade.grade_case(case, make_obs((ROUTED, ("handoff",), "with_human"), new_conversation=True), cfg)
    assert r["verdict"] == "DISCOVERY" and codes(r) == [("NEW_THREAD", 1)]


def test_no_observation_is_not_run(cfg):
    assert grade.grade_case(make_case(), None, cfg)["verdict"] == "NOT_RUN"


def test_question_count_reads_bullets_under_an_ask(cfg):
    text = "Please provide:\n- Your unit number\n- Your email\nAlso, which community?"
    assert grade.question_count(text, cfg) == 3


def test_too_many_questions(cfg):
    case = make_case(max_questions=1)
    obs = make_obs(("Which unit? Which community? I've passed this to our team.", ("handoff",), "with_human"))
    assert codes(grade.grade_case(case, obs, cfg)) == [("TOO_MANY_QUESTIONS", 1)]


def test_run_puts_failures_first_and_counts_issues(cfg):
    a, b = make_case(id="A"), make_case(id="B")
    obs = {"A": make_obs(("Done, routed.", ("handoff",), "with_human"), case="A"),
           "B": make_obs((ROUTED, (), "Resolved"), case="B")}
    g = grade.grade_run([a, b], obs, cfg, run="r")
    assert [c["case"] for c in g["cases"]] == ["B", "A"]
    assert g["summary"]["verdicts"] == {"PASS": 1, "FAIL": 1}
    assert g["summary"]["issues"][0]["code"] == "SAID_NOT_DONE"
