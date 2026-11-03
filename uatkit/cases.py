"""Read and check cases.csv: one row per test case, written against the vendor's rules document."""
import csv
from dataclasses import dataclass
from pathlib import Path

SENDERS = {"resident", "site_team", "automated"}
SENT_AS = {"new", "reply_to_existing"}
CLARITY = {"clear", "conflict", "gap", "judgment"}
# What the first reply should do.
EXPECT_R1 = {
    "hand_off",   # a person gets it on the first reply
    "answer",     # answer it; no handoff
    "ask_once",   # ask one consolidated question first; no handoff, no troubleshooting yet
    "one_step",   # give one troubleshooting step first; no handoff yet
    "either",     # answering or handing off are both acceptable (the rules leave it open)
    "no_reply",   # send nothing and hand off nothing
    "discovery",  # no pass/fail; record what the agent does
}
# What the second reply should do, after the scripted customer turn.
EXPECT_R2 = {"", "hand_off", "answer", "close"}

COLUMNS = ["id", "batch", "sender", "sent_as", "subject", "body", "rules_ref", "clarity",
           "expect_r1", "max_questions", "silent", "must_not", "turn2", "expect_r2", "note"]


@dataclass(frozen=True)
class Case:
    id: str
    batch: str
    sender: str
    sent_as: str
    subject: str
    body: str
    rules_ref: str
    clarity: str
    expect_r1: str
    max_questions: int | None
    silent: bool
    must_not: tuple[str, ...]
    turn2: str
    expect_r2: str
    note: str


class CaseError(ValueError):
    pass


def _row_to_case(row, line):
    def pick(name, allowed, default=None):
        value = (row.get(name) or "").strip().lower() or default
        if value not in allowed:
            raise CaseError(f"line {line}: {name} {value!r} is not one of {sorted(a for a in allowed if a)}")
        return value

    cid = (row.get("id") or "").strip()
    if not cid:
        raise CaseError(f"line {line}: missing id")
    expect_r1 = pick("expect_r1", EXPECT_R1)
    max_q = (row.get("max_questions") or "").strip()
    turn2 = (row.get("turn2") or "").strip()
    expect_r2 = pick("expect_r2", EXPECT_R2, "")
    if turn2 and not expect_r2 and expect_r1 != "discovery":
        raise CaseError(f"line {line}: {cid} has a turn-2 script but no expect_r2")
    silent = (row.get("silent") or "").strip().lower() in {"yes", "y", "true", "1"} or expect_r1 == "no_reply"
    return Case(
        id=cid,
        batch=(row.get("batch") or "").strip(),
        sender=pick("sender", SENDERS),
        sent_as=pick("sent_as", SENT_AS, "new"),
        subject=(row.get("subject") or "").strip(),
        body=(row.get("body") or "").strip(),
        rules_ref=(row.get("rules_ref") or "").strip(),
        clarity=pick("clarity", CLARITY),
        expect_r1=expect_r1,
        max_questions=int(max_q) if max_q else None,
        silent=silent,
        must_not=tuple(p.strip() for p in (row.get("must_not") or "").split("|") if p.strip()),
        turn2=turn2,
        expect_r2=expect_r2,
        note=(row.get("note") or "").strip(),
    )


def load(path, batch=None) -> list[Case]:
    with open(Path(path), newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        missing = [c for c in ("id", "sender", "clarity", "expect_r1", "body") if c not in (reader.fieldnames or [])]
        if missing:
            raise CaseError(f"{path}: missing columns {missing}")
        cases = [_row_to_case(row, i) for i, row in enumerate(reader, 2)]
    ids = [c.id for c in cases]
    dupes = sorted({i for i in ids if ids.count(i) > 1})
    if dupes:
        raise CaseError(f"{path}: duplicate ids {dupes}")
    if batch:
        cases = [c for c in cases if c.batch == batch]
    return cases


def write(path, rows):
    """Write case rows (dicts keyed by COLUMNS) to a cases.csv."""
    with open(Path(path), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        for row in rows:
            w.writerow({k: row.get(k, "") for k in COLUMNS})
