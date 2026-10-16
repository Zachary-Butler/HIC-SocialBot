"""The approval record. Nothing reaches Buffer's queue, Buffer's approvals tab, or `shareNow`
without one of these, written when a named human took an explicit action (a Zulip reaction, a CLI
command). The Buffer client refuses to work without it; tests assert that."""

from dataclasses import asdict, dataclass

ACTIONS = ("queue", "next", "now", "schedule")   # add to queue · next slot · post now · at a time


@dataclass(frozen=True)
class Approval:
    id: int               # row id in the approvals table; 0 means "not recorded" and is refused
    kind: str             # "roundup" | "alert"
    target_id: str        # roundup id or story id
    approver: str         # who acted, e.g. "zach" or a Zulip email
    action: str           # one of ACTIONS
    at: str               # ISO 8601 UTC
    note: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    def valid(self) -> bool:
        return bool(self.id) and bool(self.approver) and self.action in ACTIONS
