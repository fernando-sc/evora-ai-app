"""Change-triggered selective revalidation (paper Sec. IV-E).

A material change reopens only the claims whose evidence is bound to the
changed component or that list it as a revalidation trigger; unrelated
claims keep their accepted state. The previous assurance state is preserved
in ``revalidation_history``.
"""

from __future__ import annotations

from .saia import ChangeEvent, ClaimStatus, RevalidationEntry, SAIARecord, Sufficiency


def affected_claims(record: SAIARecord, component: str) -> list[str]:
    out = []
    for claim in record.claims:
        bound = any(b.component == component for ev in record.evidence_for_claim(claim) for b in ev.bindings)
        if bound or component in claim.revalidation_triggers:
            out.append(claim.id)
    return out


def apply_change(record: SAIARecord, event: ChangeEvent) -> SAIARecord:
    """Return a new record with the change applied and affected claims reopened."""
    new = record.model_copy(deep=True)
    reopened = affected_claims(new, event.component)
    previous = new.current_versions.get(event.component)
    new.current_versions[event.component] = event.new_version
    for claim in new.claims:
        if claim.id in reopened:
            claim.status = ClaimStatus.REOPENED
            claim.sufficiency = Sufficiency.INSUFFICIENT
    new.revalidation_history.append(
        RevalidationEntry(
            event=event,
            previous_version=previous,
            reopened_claim_ids=reopened,
            unaffected_claim_ids=[c.id for c in new.claims if c.id not in reopened],
        )
    )
    return new
