"""Proposal ownership enforcement (resolved 2026-09-11, see
docs/design-system-redesign-and-ownership-concerns.md §1): claiming a
proposal is strict and has no override — once `salesperson_account_id` is
set, only that account may perform a state-changing action on the proposal.
There is no admin/override role (CLAUDE.md: exactly one role exists), so the
only way off a claim is the owner unclaiming or transferring it themselves
(services/proposal_service.py::unclaim_proposal / transfer_proposal).

An unclaimed proposal (`salesperson_account_id IS NULL`) has no owner to
enforce against and stays open to any authenticated salesperson — unchanged
from the prior default (decisions #21). This function only gates state
changes (edit, regenerate, approve, generate-document, deliver); read-only
endpoints (list/get/activity/claude-calls) are intentionally not gated here —
see docs/design-system-redesign-and-ownership-concerns.md §1's note that
"no UI distinguishes 'your proposals' from 'everyone's proposals'" is a
separate, still-open concern.

Pure domain logic: no I/O. Callers pass in the acting salesperson's stable
`SalespersonAccount.id` (never `salesperson_name`/`display_name`, which are
mutable strings — see docs/design-system-redesign-and-ownership-concerns.md
§1's "What is missing"). The dev token has no backing account row and so has
no account_id (None) — it can never satisfy ownership of a claimed proposal.
"""

from typing import Optional
import uuid

from app.domain.exceptions import NotProposalOwnerError
from app.models.proposal import Proposal


def assert_owns_proposal(
    proposal: Proposal, actor_account_id: Optional[uuid.UUID]
) -> None:
    if proposal.salesperson_account_id is None:
        return
    if actor_account_id is None or proposal.salesperson_account_id != actor_account_id:
        raise NotProposalOwnerError(proposal.id, proposal.salesperson_name)
