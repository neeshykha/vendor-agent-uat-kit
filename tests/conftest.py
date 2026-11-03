import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from uatkit import config  # noqa: E402
from uatkit.cases import Case  # noqa: E402
from uatkit.observed import Observation, Turn  # noqa: E402


@pytest.fixture(scope="session")
def cfg():
    return config.load()


def make_case(**kw):
    base = dict(id="T-1", batch="", sender="resident", sent_as="new", subject="s", body="b", rules_ref="R1",
                clarity="clear", expect_r1="hand_off", max_questions=None, silent=False, must_not=(), turn2="",
                expect_r2="", note="")
    base.update(kw)
    return Case(**base)


def make_obs(*turns, case="T-1", log=True, new_conversation=None):
    return Observation(case=case, run="r", agent="a", conversation="", log_available=log,
                       new_conversation=new_conversation, turns=tuple(Turn(*t) if isinstance(t, tuple) else t for t in turns))
