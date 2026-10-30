"""Validation of a SAIA record against the EvOrA-AI traceability invariant.

The invariant (paper Sec. IV-B): every requirement is covered by a claim,
every claim by at least one control, and every implemented control produces
or binds to evidence under an accountable role. Further rules check
provenance, temporal validity, sufficiency, separation of duties and the
risk-proportional assurance rules of Sec. VI-B.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum

from .saia import ClaimStatus, ControlStatus, DecisionType, RiskProfile, SAIARecord, Sufficiency


class Severity(str, Enum):
    ERROR = "error"
    WARNING = "warning"


@dataclass(frozen=True)
class Finding:
    rule: str
    severity: Severity
    ref: str
    message: str


@dataclass
class Report:
    findings: list[Finding] = field(default_factory=list)

    @property
    def errors(self) -> list[Finding]:
        return [f for f in self.findings if f.severity is Severity.ERROR]

    @property
    def warnings(self) -> list[Finding]:
        return [f for f in self.findings if f.severity is Severity.WARNING]

    @property
    def ok(self) -> bool:
        return not self.errors

    def add(self, rule: str, severity: Severity, ref: str, message: str) -> None:
        self.findings.append(Finding(rule, severity, ref, message))


HIGH_ASSURANCE = {RiskProfile.HIGH, RiskProfile.EXCESSIVE}


def validate(record: SAIARecord, as_of: date | None = None) -> Report:
    """Check a SAIA record; ``as_of`` defaults to today."""
    as_of = as_of or date.today()
    idx = record.index()
    report = Report()
    E, W = Severity.ERROR, Severity.WARNING

    # R1 requirement coverage
    covered = {rid for c in record.claims for rid in c.requirement_ids}
    for rid in idx["requirements"]:
        if rid not in covered:
            report.add("R1-requirement-coverage", E, rid, "requirement is not bound to any claim")

    for claim in record.claims:
        # R2 dangling references
        for rid in claim.requirement_ids:
            if rid not in idx["requirements"]:
                report.add("R2-reference", E, claim.id, f"unknown requirement '{rid}'")
        for role in (claim.accountable_role, claim.reviewer_role):
            if role not in idx["roles"]:
                report.add("R2-reference", E, claim.id, f"unknown role '{role}'")
        for cid in claim.control_ids:
            if cid not in idx["controls"]:
                report.add("R2-reference", E, claim.id, f"unknown control '{cid}'")

        # R3 claim -> control
        if not claim.control_ids:
            report.add("R3-claim-control", E, claim.id, "claim has no control")
        if not claim.acceptance_criterion.strip():
            report.add("R3-claim-control", E, claim.id, "claim has no acceptance criterion")

        evidence = record.evidence_for_claim(claim)

        # R5 sufficiency is only meaningful with evidence
        if claim.status is ClaimStatus.ACCEPTED:
            if not evidence:
                report.add("R5-sufficiency", E, claim.id, "accepted claim has no evidence")
            if claim.sufficiency is Sufficiency.INSUFFICIENT:
                report.add("R5-sufficiency", E, claim.id, "accepted claim with insufficient evidence")
            elif claim.sufficiency is Sufficiency.CONDITIONAL:
                report.add("R5-sufficiency", W, claim.id, "claim accepted under conditional sufficiency")
        elif claim.status is ClaimStatus.REOPENED:
            report.add("R5-sufficiency", E, claim.id, "claim reopened by a change; revalidation pending")

        # R6 provenance: evidence must match deployed versions
        for ev in evidence:
            for b in ev.bindings:
                deployed = record.current_versions.get(b.component)
                if deployed is not None and deployed != b.version:
                    report.add(
                        "R6-stale-evidence", E, f"{claim.id}/{ev.id}",
                        f"evidence bound to {b.component}@{b.version}, deployed is {deployed}",
                    )
            # R7 temporal validity
            if ev.valid_until is not None and ev.valid_until < as_of:
                report.add("R7-expired-evidence", E, f"{claim.id}/{ev.id}", f"evidence expired on {ev.valid_until}")

        # R8 separation of duties and independent review
        producers = {ev.producer_role for ev in evidence}
        if claim.reviewer_role in producers:
            report.add("R8-separation-of-duties", E, claim.id, "reviewer also produced the evidence")
        reviewer = idx["roles"].get(claim.reviewer_role)
        if record.risk_profile in HIGH_ASSURANCE and reviewer is not None and not reviewer.independent:
            report.add("R8-independent-review", E, claim.id, "high-risk profile requires an independent reviewer")

    for control in record.controls:
        # R4 control -> evidence
        if control.status is not ControlStatus.PLANNED and not control.evidence_ids:
            report.add("R4-control-evidence", E, control.id, f"{control.status.value} control has no evidence")
        if control.status is ControlStatus.PLANNED:
            report.add("R4-control-evidence", W, control.id, "control is only planned")
        for eid in control.evidence_ids:
            if eid not in idx["evidence"]:
                report.add("R2-reference", E, control.id, f"unknown evidence '{eid}'")

    for ev in record.evidence:
        if ev.producer_role not in idx["roles"]:
            report.add("R2-reference", E, ev.id, f"unknown role '{ev.producer_role}'")

    # R9 decision consistency with assurance state
    if record.decisions:
        last = record.decisions[-1]
        if last.decided_by not in idx["roles"]:
            report.add("R2-reference", E, "decision", f"unknown role '{last.decided_by}'")
        if last.decision is DecisionType.PROCEED:
            if record.risk_profile is RiskProfile.EXCESSIVE:
                report.add("R9-decision", E, "decision", "excessive-risk systems cannot proceed")
            blocking = [c.id for c in record.claims if c.status is not ClaimStatus.ACCEPTED]
            if blocking:
                report.add("R9-decision", E, "decision", f"'proceed' with non-accepted claims: {', '.join(blocking)}")
    else:
        report.add("R9-decision", W, "decision", "no decision recorded")

    return report
