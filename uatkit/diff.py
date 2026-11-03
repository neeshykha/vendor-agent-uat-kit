"""Compare two graded runs case by case: newly passing, newly failing, and what changed in between."""

PASSING = {"PASS", "REVIEW"}
FAILING = {"FAIL", "PARTIAL"}


def _codes(g):
    return sorted({f["code"] for f in g["findings"]})


def compare(previous: dict, current: dict) -> dict:
    prev = {g["case"]: g for g in previous["cases"]}
    cur = {g["case"]: g for g in current["cases"]}
    out = {"previous": previous["run"], "current": current["run"], "newly_passing": [], "newly_failing": [],
           "still_failing": [], "changed": [], "added": sorted(set(cur) - set(prev)),
           "dropped": sorted(set(prev) - set(cur))}
    for cid in sorted(set(prev) & set(cur)):
        a, b = prev[cid], cur[cid]
        row = {"case": cid, "was": a["verdict"], "now": b["verdict"],
               "fixed": sorted(set(_codes(a)) - set(_codes(b))), "new": sorted(set(_codes(b)) - set(_codes(a)))}
        if a["verdict"] in FAILING and b["verdict"] in PASSING:
            out["newly_passing"].append(row)
        elif a["verdict"] in PASSING and b["verdict"] in FAILING:
            out["newly_failing"].append(row)
        elif a["verdict"] in FAILING and b["verdict"] in FAILING:
            out["still_failing"].append(row)
        if (row["fixed"] or row["new"]) or a["verdict"] != b["verdict"]:
            out["changed"].append(row)
    return out


def summary_line(d: dict) -> str:
    return (f"{d['current']} against {d['previous']}: {len(d['newly_passing'])} newly passing, "
            f"{len(d['newly_failing'])} newly failing, {len(d['still_failing'])} still failing")
