import pytest
from conftest import ROOT

from uatkit import cases, grade, sim_agent
from uatkit.__main__ import planted_check

CASES = ROOT / "cases" / "northgate.csv"


def test_bundled_cases_load():
    loaded = cases.load(CASES)
    assert len(loaded) == 30
    assert {c.clarity for c in loaded} == {"clear", "conflict", "gap", "judgment"}
    assert {c.batch for c in loaded} == {"A", "B", "C", "D"}


@pytest.mark.parametrize("profile", sorted(sim_agent.PROFILES))
@pytest.mark.parametrize("seed", range(40))
def test_grader_finds_exactly_what_the_sim_planted(cfg, profile, seed):
    case_list = cases.load(CASES)
    obs, planted = sim_agent.run(case_list, profile, seed, "r")
    g = grade.grade_run(case_list, {o.case: o for o in obs}, cfg, run="r")
    found, missed, extra = planted_check(g, planted)
    assert not missed and not extra


def test_sim_is_reproducible():
    case_list = cases.load(CASES)
    assert sim_agent.run(case_list, "v1", 5) == sim_agent.run(case_list, "v1", 5)


def test_bad_rows_are_refused(tmp_path):
    def write(**row):
        p = tmp_path / "c.csv"
        base = dict(id="X-1", sender="resident", clarity="clear", expect_r1="hand_off", body="hi")
        base.update(row)
        cases.write(p, [base])
        return p

    with pytest.raises(cases.CaseError, match="expect_r1"):
        cases.load(write(expect_r1="escalate"))
    with pytest.raises(cases.CaseError, match="expect_r2"):
        cases.load(write(expect_r1="one_step", turn2="still broken"))
    p = tmp_path / "d.csv"
    cases.write(p, [dict(id="X", sender="resident", clarity="clear", expect_r1="answer", body="a")] * 2)
    with pytest.raises(cases.CaseError, match="duplicate"):
        cases.load(p)
