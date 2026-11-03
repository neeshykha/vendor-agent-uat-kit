"""Load kit.toml: the phrases and names that tell the grader what a vendor's output means."""
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path

DEFAULT = Path(__file__).resolve().parent.parent / "kit.toml"


@dataclass(frozen=True)
class Config:
    claims: tuple[re.Pattern, ...]
    asks: tuple[re.Pattern, ...]
    closing: tuple[re.Pattern, ...]
    checkin: tuple[re.Pattern, ...]
    handoff_actions: frozenset[str]
    resolved_statuses: frozenset[str]
    source: str


def _compile(patterns):
    return tuple(re.compile(p, re.IGNORECASE) for p in patterns)


def load(path=None) -> Config:
    path = Path(path or DEFAULT)
    raw = tomllib.loads(path.read_text())
    return Config(
        claims=_compile(raw["claims"]["patterns"]),
        asks=_compile(raw["asks"]["patterns"]),
        closing=_compile(raw["asks"].get("closing", [])),
        checkin=_compile(raw["asks"].get("checkin", [])),
        handoff_actions=frozenset(a.lower() for a in raw["actions"]["handoff"]),
        resolved_statuses=frozenset(s.lower() for s in raw["status"]["resolved"]),
        source=_display(path),
    )


def _display(path: Path):
    """The path relative to the kit when it's inside it, so graded files don't carry a home folder."""
    try:
        return str(path.resolve().relative_to(DEFAULT.parent))
    except ValueError:
        return str(path)
