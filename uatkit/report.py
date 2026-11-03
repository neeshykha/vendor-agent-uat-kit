"""Render a graded run as one self-contained HTML page, plus an optional .xlsx to share with the vendor.

The page puts the Issues summary on top, then what changed since the last batch, then every case with
failures first. It states what happened, never why: diagnosis is the vendor's job.
"""
from html import escape

from . import __version__
from .grade import FINDINGS

VERDICT_LABEL = {"FAIL": "Fail", "PARTIAL": "Partial", "REVIEW": "Needs review", "PASS": "Pass",
                 "DISCOVERY": "Discovery", "NOT_RUN": "Not run"}
SEV_LABEL = {"fail": "Fail", "partial": "Partial", "note": "Note"}

CSS = """
:root{--bg:#f7f7f5;--card:#fff;--ink:#1d1d1b;--muted:#5f5f5a;--line:#e3e2dd;--fail:#b42318;--fail-bg:#fde8e6;
--partial:#8a5a00;--partial-bg:#fdf1d6;--review:#2f5d8a;--review-bg:#e3edf7;--pass:#1f6f43;--pass-bg:#e1f3e8;
--disc:#5b5b66;--disc-bg:#ececf1;--chip:#f0efea;--link:#1d5fa8}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#151514;--card:#1f1f1d;--ink:#ecebe6;
--muted:#a3a29b;--line:#34332f;--fail:#ff8a7a;--fail-bg:#3a1d1a;--partial:#f2c46b;--partial-bg:#33290f;--review:#8fbcec;
--review-bg:#172a3d;--pass:#7fd3a3;--pass-bg:#15301f;--disc:#b9b9c6;--disc-bg:#2a2a31;--chip:#2a2a27;--link:#8fbcec}}
:root[data-theme="dark"]{--bg:#151514;--card:#1f1f1d;--ink:#ecebe6;--muted:#a3a29b;--line:#34332f;--fail:#ff8a7a;
--fail-bg:#3a1d1a;--partial:#f2c46b;--partial-bg:#33290f;--review:#8fbcec;--review-bg:#172a3d;--pass:#7fd3a3;
--pass-bg:#15301f;--disc:#b9b9c6;--disc-bg:#2a2a31;--chip:#2a2a27;--link:#8fbcec}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);
font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}
main{max-width:980px;margin:0 auto;padding:24px 16px 48px}h1{font-size:24px;margin:0 0 4px}
h2{font-size:18px;margin:32px 0 12px}a{color:var(--link)}.muted{color:var(--muted)}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(110px,1fr));gap:8px;margin:16px 0}
.tile{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:10px 12px}
.tile b{display:block;font-size:22px}.tile span{font-size:13px;color:var(--muted)}
table{width:100%;border-collapse:collapse;background:var(--card);border:1px solid var(--line);border-radius:10px;overflow:hidden}
th,td{text-align:left;padding:8px 10px;border-bottom:1px solid var(--line);vertical-align:top;font-size:14px}
th{font-size:12px;text-transform:uppercase;letter-spacing:.03em;color:var(--muted)}tr:last-child td{border-bottom:0}
.wrap{overflow-x:auto}.badge{display:inline-block;font-size:12px;font-weight:600;padding:2px 8px;border-radius:999px;white-space:nowrap}
.FAIL,.fail{color:var(--fail);background:var(--fail-bg)}.PARTIAL,.partial{color:var(--partial);background:var(--partial-bg)}
.REVIEW,.note{color:var(--review);background:var(--review-bg)}.PASS{color:var(--pass);background:var(--pass-bg)}
.DISCOVERY,.NOT_RUN{color:var(--disc);background:var(--disc-bg)}
.chip{display:inline-block;font-size:12px;padding:1px 7px;border-radius:6px;background:var(--chip);margin:0 4px 4px 0}
.case{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px 16px;margin:0 0 12px}
.case h3{font-size:16px;margin:0 0 6px;display:flex;gap:8px;align-items:baseline;flex-wrap:wrap}
.case h3 code{font-size:13px;color:var(--muted)}.eh{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin:10px 0}
@media (max-width:640px){.eh{grid-template-columns:1fr}}
.eh div{border:1px solid var(--line);border-radius:8px;padding:8px 10px}.eh b{display:block;font-size:12px;
text-transform:uppercase;letter-spacing:.03em;color:var(--muted);margin-bottom:2px}
ul.f{margin:6px 0;padding-left:18px}ul.f li{margin:2px 0}
details{margin-top:6px}summary{cursor:pointer;color:var(--muted);font-size:14px}
.msg{border-left:3px solid var(--line);padding:4px 10px;margin:8px 0;white-space:pre-wrap;font-size:14px}
.msg.agent{border-color:var(--review)}.meta{font-size:12px;color:var(--muted)}
footer{margin-top:40px;font-size:13px;color:var(--muted)}
"""

FAVICON = ("data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'>"
           "<text y='.9em' font-size='90'>\U0001F9EA</text></svg>")


def _e(text):
    return escape(str(text or ""))


def _tiles(summary):
    v = summary["verdicts"]
    order = ["FAIL", "PARTIAL", "REVIEW", "PASS", "DISCOVERY", "NOT_RUN"]
    return "".join(f'<div class="tile"><b>{v.get(k, 0)}</b><span>{VERDICT_LABEL[k]}</span></div>'
                   for k in order if v.get(k) or k in ("FAIL", "PARTIAL", "PASS"))


def _issues(summary):
    if not summary["issues"]:
        return '<p class="muted">No findings in this run.</p>'
    rows = []
    for i in summary["issues"]:
        owners = ", ".join(f"{n} {o}" for o, n in sorted(i["owners"].items()))
        cases = " ".join(f'<a href="#{_e(c)}">{_e(c)}</a>' for c in i["cases"])
        rows.append(f'<tr><td><span class="badge {i["severity"]}">{SEV_LABEL[i["severity"]]}</span></td>'
                    f'<td><b>{_e(i["title"])}</b><div class="meta">{_e(i["code"])}</div></td>'
                    f'<td>{len(i["cases"])}</td><td>{_e(owners)}</td><td>{cases}</td></tr>')
    return ('<div class="wrap"><table><tr><th>Severity</th><th>Issue</th><th>Cases</th><th>Owner</th><th>Which</th></tr>'
            + "".join(rows) + "</table></div>")


def _changes(d):
    if not d:
        return ""

    def block(title, rows):
        if not rows:
            return f"<p><b>{title}:</b> <span class='muted'>none</span></p>"
        items = []
        for r in rows:
            bits = []
            if r["fixed"]:
                bits.append("gone: " + ", ".join(FINDINGS[c][0].lower() for c in r["fixed"]))
            if r["new"]:
                bits.append("new: " + ", ".join(FINDINGS[c][0].lower() for c in r["new"]))
            move = (f"{VERDICT_LABEL[r['now']]}, same as before" if r["was"] == r["now"]
                    else f"{VERDICT_LABEL[r['was']]} to {VERDICT_LABEL[r['now']]}")
            items.append(f'<li><a href="#{_e(r["case"])}">{_e(r["case"])}</a>: {move}'
                         f'{" (" + _e("; ".join(bits)) + ")" if bits else ""}</li>')
        return f"<p><b>{title}</b></p><ul class='f'>{''.join(items)}</ul>"

    return (f'<h2>Since {_e(d["previous"])}</h2>' + block("Newly failing", d["newly_failing"])
            + block("Newly passing", d["newly_passing"]) + block("Still failing", d["still_failing"]))


def _conversation(g):
    obs, cf = g["observation"], g["case_fields"]
    parts = [f'<div class="meta">Customer ({_e(cf["sender"])}), subject "{_e(cf["subject"])}"</div>'
             f'<div class="msg">{_e(cf["body"])}</div>']
    if obs:
        for n, t in enumerate(obs["turns"], 1):
            if n > 1 and t.get("customer"):
                parts.append(f'<div class="meta">Customer, turn {n}</div><div class="msg">{_e(t["customer"])}</div>')
            actions = ", ".join(t["actions"]) or "none"
            meta = f"Agent, reply {n}. Actions: {_e(actions)}. Status after: {_e(t['status_after'] or 'not recorded')}."
            body = _e(t["reply"]) if t["reply"] else '<span class="muted">(no reply sent)</span>'
            parts.append(f'<div class="meta">{meta}</div><div class="msg agent">{body}</div>')
        if obs.get("conversation"):
            parts.append(f'<div class="meta"><a href="{_e(obs["conversation"])}">Conversation link</a></div>')
    return "".join(parts)


def _case(g):
    cf = g["case_fields"]
    chips = [f'<span class="chip">{_e(cf["rules_ref"] or "no rule")}: {_e(cf["clarity"])}</span>',
             f'<span class="chip">{_e(cf["sender"])}</span>']
    chips += [f'<span class="chip">owner: {_e(o)}</span>' for o in g["owners"]]
    findings = "".join(f'<li><span class="badge {f["severity"]}">{SEV_LABEL[f["severity"]]}</span> '
                       f'<b>{_e(FINDINGS[f["code"]][0])}</b>. {_e(f["detail"])}</li>' for f in g["findings"])
    review = "".join(f'<li><span class="badge note">Review</span> {_e(r)}</li>' for r in g["review"])
    note = f'<p class="meta">Case note: {_e(cf["note"])}</p>' if cf.get("note") else ""
    open_attr = " open" if g["verdict"] in ("FAIL", "PARTIAL") else ""
    return (f'<section class="case" id="{_e(g["case"])}"><h3><span class="badge {g["verdict"]}">'
            f'{VERDICT_LABEL[g["verdict"]]}</span> {_e(cf["subject"])} <code>{_e(g["case"])}</code></h3>'
            f'<div>{"".join(chips)}</div>'
            + (f'<ul class="f">{findings}{review}</ul>' if findings or review else "")
            + f'<div class="eh"><div><b>Expected</b>{_e(g["expected"])}</div><div><b>Happened</b>{_e(g["happened"])}</div></div>'
            + note + f'<details{open_attr}><summary>Conversation</summary>{_conversation(g)}</details></section>')


def render(graded: dict, diff: dict | None = None, title=None) -> str:
    s = graded["summary"]
    title = title or f"Vendor agent UAT: {graded['run']}"
    cases_html = "".join(_case(g) for g in graded["cases"])
    unknown = graded.get("unknown_observations") or []
    warn = (f'<p class="muted">Observations with no matching case: {_e(", ".join(unknown))}</p>' if unknown else "")
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{_e(title)}</title><link rel="icon" href="{FAVICON}"><style>{CSS}</style></head>
<body><main>
<h1>{_e(title)}</h1>
<p class="muted">Agent: {_e(graded['agent'] or 'not named')}. Graded {_e(graded['graded_on'])} against {s['total']} cases.</p>
<div class="tiles">{_tiles(s)}</div>
<h2>Issues</h2>
{_issues(s)}
<p class="meta">An execution issue is the vendor's whatever the rules say. A choice issue on a rules line tagged conflict or gap goes to the rules owner.</p>
{_changes(diff)}
<h2>Cases, failures first</h2>
{warn}{cases_html}
<footer>Generated by vendor-agent-uat-kit {__version__}. Observations only: this page says what happened, not why.</footer>
</main></body></html>
"""


def write_xlsx(path, graded_runs):
    """One sheet per graded run, failures first. Needs openpyxl."""
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Alignment, Font
    except ImportError as exc:
        raise SystemExit("The .xlsx export needs openpyxl: pip install openpyxl") from exc
    wb = Workbook()
    wb.remove(wb.active)
    cols = ["Case", "Verdict", "Issues", "Owner", "Expected", "Happened", "Customer email", "Reply 1",
            "Customer turn 2", "Reply 2", "Conversation"]
    widths = [9, 12, 34, 14, 50, 50, 50, 50, 30, 50, 30]
    for graded in graded_runs:
        ws = wb.create_sheet(graded["run"][:31] or "run")
        ws.append(cols)
        for c in ws[1]:
            c.font = Font(bold=True)
        for g in graded["cases"]:
            turns = (g["observation"] or {}).get("turns") or []
            t1 = turns[0] if turns else {}
            t2 = turns[1] if len(turns) > 1 else {}
            ws.append([g["case"], VERDICT_LABEL[g["verdict"]],
                       "\n".join(FINDINGS[f["code"]][0] for f in g["findings"]), ", ".join(g["owners"]),
                       g["expected"], g["happened"], g["case_fields"]["body"], t1.get("reply", ""),
                       t2.get("customer", ""), t2.get("reply", ""), (g["observation"] or {}).get("conversation", "")])
        for i, w in enumerate(widths, 1):
            ws.column_dimensions[ws.cell(row=1, column=i).column_letter].width = w
        for row in ws.iter_rows(min_row=2):
            for c in row:
                c.alignment = Alignment(wrap_text=True, vertical="top")
        ws.freeze_panes = "C2"
    wb.save(path)
