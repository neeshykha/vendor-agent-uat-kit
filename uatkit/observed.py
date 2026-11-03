"""Read observations: one JSON per case per run, recording what the agent actually did.

    {
      "case": "NG-07",
      "run": "batch-1",
      "agent": "sim-agent v1",
      "conversation": "https://vendor.example/conversations/abc123",
      "log_available": true,
      "new_conversation": false,
      "turns": [
        {"reply": "Try this first: ...", "actions": [], "status_after": "open"},
        {"customer": "Still crashing.", "reply": "I've passed this to our team.",
         "actions": ["handoff"], "status_after": "with_human"}
      ]
    }

Turn 1's customer message is the case body. "reply" is null or "" when nothing was sent.
"log_available": false means the vendor's log didn't show actions, so handoffs are unknown.
"new_conversation" only matters for cases sent as a reply on an existing thread.
"""
import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Turn:
    reply: str
    actions: tuple[str, ...]
    status_after: str
    customer: str = ""


@dataclass(frozen=True)
class Observation:
    case: str
    run: str
    agent: str
    conversation: str
    log_available: bool
    new_conversation: bool | None
    turns: tuple[Turn, ...] = field(default_factory=tuple)


def parse(data) -> Observation:
    turns = tuple(
        Turn(
            reply=(t.get("reply") or "").strip(),
            actions=tuple(a.strip().lower() for a in t.get("actions") or []),
            status_after=(t.get("status_after") or "").strip(),
            customer=(t.get("customer") or "").strip(),
        )
        for t in data.get("turns") or []
    )
    return Observation(
        case=data["case"],
        run=data.get("run", ""),
        agent=data.get("agent", ""),
        conversation=data.get("conversation", ""),
        log_available=bool(data.get("log_available", True)),
        new_conversation=data.get("new_conversation"),
        turns=turns,
    )


def load_dir(path) -> dict[str, Observation]:
    out = {}
    for p in sorted(Path(path).glob("*.json")):
        obs = parse(json.loads(p.read_text(encoding="utf-8")))
        out[obs.case] = obs
    return out


def to_dict(obs: Observation) -> dict:
    return {
        "case": obs.case, "run": obs.run, "agent": obs.agent, "conversation": obs.conversation,
        "log_available": obs.log_available, "new_conversation": obs.new_conversation,
        "turns": [{"customer": t.customer, "reply": t.reply, "actions": list(t.actions),
                   "status_after": t.status_after} for t in obs.turns],
    }


def write_dir(path, observations):
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    for obs in observations:
        (path / f"{obs.case}.json").write_text(json.dumps(to_dict(obs), indent=2, ensure_ascii=False) + "\n",
                                               encoding="utf-8")
