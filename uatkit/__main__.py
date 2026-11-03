"""Command line: sim, grade, diff, report, and demo (all of them on the bundled Northgate cases).

    python -m uatkit grade --cases cases/northgate.csv --observed observed/batch-1 --out graded/batch-1.json
    python -m uatkit diff graded/batch-1.json graded/batch-2.json
    python -m uatkit report graded/batch-2.json --previous graded/batch-1.json --out report.html
    python -m uatkit demo
"""
import argparse
import json
import sys
from pathlib import Path

from . import cases, config, diff, grade, observed, report, sim_agent

ROOT = Path(__file__).resolve().parent.parent
DEMO_SEED = 37  # picked so the demo shows every finding class; any seed passes the tests


def _write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def cmd_sim(a):
    case_list = cases.load(a.cases, a.batch)
    obs, planted = sim_agent.run(case_list, a.profile, a.seed, a.run)
    observed.write_dir(a.out, obs)
    _write_json(Path(a.out).with_suffix(".planted.json"), planted)
    print(f"{len(obs)} observations to {a.out}; {len(planted)} planted defects")


def cmd_grade(a):
    case_list = cases.load(a.cases, a.batch)
    g = grade.grade_run(case_list, observed.load_dir(a.observed), config.load(a.config), run=a.run or "")
    _write_json(a.out, g)
    v = g["summary"]["verdicts"]
    print(f"{g['run']}: " + ", ".join(f"{n} {k.lower()}" for k, n in sorted(v.items())) + f" -> {a.out}")


def cmd_diff(a):
    d = diff.compare(_read_json(a.previous), _read_json(a.current))
    print(diff.summary_line(d))
    for key in ("newly_failing", "newly_passing", "still_failing"):
        for r in d[key]:
            print(f"  {key.replace('_', ' ')}: {r['case']} {r['was']} -> {r['now']} fixed={r['fixed']} new={r['new']}")


def cmd_report(a):
    g = _read_json(a.graded)
    d = diff.compare(_read_json(a.previous), g) if a.previous else None
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(report.render(g, d, a.title), encoding="utf-8")
    print(f"report -> {a.out}")
    if a.xlsx:
        runs = ([_read_json(a.previous)] if a.previous else []) + [g]
        report.write_xlsx(a.xlsx, runs)
        print(f"xlsx -> {a.xlsx}")


def planted_check(graded, planted):
    """Compare what the sim planted with what the grader found: (found, missed, extra)."""
    want = {(p["case"], p["code"], p["turn"]) for p in planted}
    got = {(g["case"], f["code"], f["turn"]) for g in graded["cases"] for f in g["findings"]}
    return want & got, want - got, got - want


def cmd_demo(a):
    case_list = cases.load(ROOT / "cases" / "northgate.csv")
    cfg = config.load()
    out = Path(a.out)
    graded = {}
    for run_name, profile in (("batch-1", "v1"), ("batch-2", "v2")):
        obs, planted = sim_agent.run(case_list, profile, DEMO_SEED, run_name)
        observed.write_dir(out / "observed" / run_name, obs)
        _write_json(out / "observed" / f"{run_name}.planted.json", planted)
        g = grade.grade_run(case_list, {o.case: o for o in obs}, cfg, run=run_name)
        _write_json(out / "graded" / f"{run_name}.json", g)
        found, missed, extra = planted_check(g, planted)
        print(f"{run_name} ({profile}): planted {len(planted)}, grader found {len(found)}, "
              f"missed {len(missed)}, extra {len(extra)}")
        if missed or extra:
            print("  missed:", sorted(missed), "\n  extra:", sorted(extra))
        graded[run_name] = g
    d = diff.compare(graded["batch-1"], graded["batch-2"])
    print(diff.summary_line(d))
    docs = out / "docs"
    docs.mkdir(parents=True, exist_ok=True)
    (docs / "index.html").write_text(report.render(graded["batch-2"], d, "Northgate Living: vendor agent UAT, batch 2"),
                                     encoding="utf-8")
    (docs / "batch-1.html").write_text(report.render(graded["batch-1"], None, "Northgate Living: vendor agent UAT, batch 1"),
                                       encoding="utf-8")
    print(f"pages -> {docs / 'index.html'} and {docs / 'batch-1.html'}")
    if a.xlsx:
        report.write_xlsx(a.xlsx, [graded["batch-1"], graded["batch-2"]])
        print(f"xlsx -> {a.xlsx}")


def main(argv=None):
    p = argparse.ArgumentParser(prog="uatkit", description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("sim", help="run the synthetic agent over a cases file")
    s.add_argument("--cases", required=True)
    s.add_argument("--batch")
    s.add_argument("--profile", default="v1", choices=sorted(sim_agent.PROFILES))
    s.add_argument("--seed", type=int, default=0)
    s.add_argument("--run", default="")
    s.add_argument("--out", required=True)
    s.set_defaults(func=cmd_sim)

    g = sub.add_parser("grade", help="grade a folder of observations against a cases file")
    g.add_argument("--cases", required=True)
    g.add_argument("--batch")
    g.add_argument("--observed", required=True)
    g.add_argument("--config")
    g.add_argument("--run")
    g.add_argument("--out", required=True)
    g.set_defaults(func=cmd_grade)

    d = sub.add_parser("diff", help="compare two graded runs")
    d.add_argument("previous")
    d.add_argument("current")
    d.set_defaults(func=cmd_diff)

    r = sub.add_parser("report", help="render a graded run as HTML (and optionally .xlsx)")
    r.add_argument("graded")
    r.add_argument("--previous")
    r.add_argument("--title")
    r.add_argument("--out", required=True)
    r.add_argument("--xlsx")
    r.set_defaults(func=cmd_report)

    m = sub.add_parser("demo", help="sim two batches on the Northgate cases, grade, diff, and render docs/")
    m.add_argument("--out", default=str(ROOT))
    m.add_argument("--xlsx")
    m.set_defaults(func=cmd_demo)

    a = p.parse_args(argv)
    try:
        a.func(a)
    except cases.CaseError as exc:
        sys.exit(f"cases: {exc}")


if __name__ == "__main__":
    main()
