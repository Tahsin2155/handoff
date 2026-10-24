"""Structured results returned by every action the agent can run.

Instead of returning None / "Denied by user." / "Blocked: ..." and having the
main loop sniff strings, every action returns a `Result`. The loop switches on
`result.outcome` and asks `result.stops_turn` whether the rest of the model's
actions in this turn may still run.
"""
from dataclasses import dataclass
from enum import Enum


class Outcome(Enum):
    OK = "ok"                              # the action ran
    DENIED = "denied"                      # the user said No in the confirmation dialog
    BLOCKED = "blocked"                    # the model's own safety flag blocked it
    UNKNOWN_FUNCTION = "unknown_function"  # the model called a name we have no handler for
    RETURN_CONTROL = "return_control"      # the model handed control back; the user replied
    END_RUN = "end_run"                    # the user chose to end the run


# After any of these, the remaining actions of the same turn must NOT run.
_STOPS_TURN = frozenset({
    Outcome.DENIED,
    Outcome.BLOCKED,
    Outcome.UNKNOWN_FUNCTION,
    Outcome.RETURN_CONTROL,
    Outcome.END_RUN,
})


@dataclass(frozen=True)
class Result:
    outcome: Outcome
    message: str | None = None  # text for the model/log; None when there is nothing to say

    @property
    def stops_turn(self) -> bool:
        return self.outcome in _STOPS_TURN


OK = Result(Outcome.OK)
