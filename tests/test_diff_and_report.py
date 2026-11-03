import pytest
from conftest import make_case, make_obs

from uatkit import diff, grade, report

ROUTED = "We've routed your request to our support team."


def _run(cfg, name, a_obs, b_obs):
    return grade.grade_run([make_case(id="A"), make_case(id="B")],
                           {"A": make_obs(a_obs, case="A"), "B": make_obs(b_obs, case="B")}, cfg, run=name)


def test_diff_sorts_cases_into_newly_passing_and_failing(cfg):
    good, bad = (ROUTED, ("handoff",), "with_human"), (ROUTED, (), "Resolved")
    before = _run(cfg, "batch-1", bad, good)
    after = _run(cfg, "batch-2", good, bad)
    d = diff.compare(before, after)
    assert [r["case"] for r in d["newly_passing"]] == ["A"]
    assert [r["case"] for r in d["newly_failing"]] == ["B"]
    assert d["newly_passing"][0]["fixed"] == ["CLOSED_AFTER_CLAIM", "SAID_NOT_DONE"]
    assert "1 newly passing, 1 newly failing" in diff.summary_line(d)


def test_report_escapes_text_and_lists_failures_first(cfg):
    case = make_case(id="X", body="<script>alert(1)</script>", subject="Locked out")
    g = grade.grade_run([case, make_case(id="Y")],
                        {"X": make_obs((ROUTED, (), "Resolved"), case="X"),
                         "Y": make_obs((ROUTED, ("handoff",), "with_human"), case="Y")}, cfg, run="batch-1")
    html = report.render(g)
    assert "<script>alert" not in html and "&lt;script&gt;" in html
    assert html.index('id="X"') < html.index('id="Y"')
    assert "Said a person has it; no handoff ran" in html


def test_xlsx_export(cfg, tmp_path):
    pytest.importorskip("openpyxl")
    g = _run(cfg, "batch-1", (ROUTED, (), "Resolved"), (ROUTED, ("handoff",), "with_human"))
    out = tmp_path / "r.xlsx"
    report.write_xlsx(out, [g])
    from openpyxl import load_workbook
    ws = load_workbook(out)["batch-1"]
    assert ws["A2"].value == "A" and ws["B2"].value == "Fail"
