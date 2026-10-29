"""Analytical ex ante indicators computed on a SAIA instance.

These characterise the design of a record (coverage, automation potential,
human-judgement load, revalidation scope). They are not field measurements
of effort, latency or effectiveness.
"""

from __future__ import annotations

from .saia import SAIARecord


def indicators(record: SAIARecord) -> dict[str, float | int]:
    n_req = len(record.requirements)
    covered = {rid for c in record.claims for rid in c.requirement_ids}
    n_ev = len(record.evidence)
    hooked = sum(1 for e in record.evidence if e.automation_hook)
    n_claims = len(record.claims)
    out: dict[str, float | int] = {
        "requirements": n_req,
        "requirement_coverage": len(covered & {r.id for r in record.requirements}) / n_req if n_req else 0.0,
        "claims": n_claims,
        "controls": len(record.controls),
        "evidence_items": n_ev,
        "evidence_with_automation_hook": hooked,
        "automation_share": hooked / n_ev if n_ev else 0.0,
        # statement, acceptance criterion and sufficiency judgement per claim, plus each decision
        "human_judgement_fields": 3 * n_claims + len(record.decisions),
    }
    if record.revalidation_history:
        last = record.revalidation_history[-1]
        out["reopened_claims_last_change"] = len(last.reopened_claim_ids)
        out["revalidation_scope_last_change"] = len(last.reopened_claim_ids) / n_claims if n_claims else 0.0
    return out
