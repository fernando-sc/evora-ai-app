"""SAIA (Simplified Algorithmic Impact Assessment) record model.

Implements the minimal EvOrA-AI assurance semantics (paper Table IV):
requirement binding, assurance claim, control binding, evidence identity,
provenance/versioning, evidence sufficiency, accountability, temporal
validity, revalidation trigger, decision and automation hook.
"""

from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", use_enum_values=False)


class RiskProfile(str, Enum):
    """Initial assurance profile, taken from the applicable framework.

    In the Brazilian instantiation it mirrors the AIE scale. "critical" or
    equivalent categories in other frameworks map to HIGH or EXCESSIVE.
    """

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    EXCESSIVE = "excessive"


class Phase(str, Enum):
    """EvOrA-AI lifecycle phases L1-L6."""

    L1 = "L1"  # problem understanding
    L2 = "L2"  # data
    L3 = "L3"  # design and development
    L4 = "L4"  # evaluation and verification
    L5 = "L5"  # deployment and monitoring
    L6 = "L6"  # closure


class Sufficiency(str, Enum):
    SUFFICIENT = "sufficient"
    CONDITIONAL = "conditional"
    INSUFFICIENT = "insufficient"


class ClaimStatus(str, Enum):
    OPEN = "open"
    ACCEPTED = "accepted"
    REOPENED = "reopened"


class ControlStatus(str, Enum):
    PLANNED = "planned"
    IMPLEMENTED = "implemented"
    VERIFIED = "verified"


class DecisionType(str, Enum):
    PROCEED = "proceed"
    MITIGATE = "mitigate"
    RESTRICT = "restrict"
    SUSPEND = "suspend"
    DECOMMISSION = "decommission"


class Role(_Model):
    id: str
    name: str
    independent: bool = Field(
        default=False,
        description="True if the role is organisationally independent of the delivery team.",
    )


class RequirementBinding(_Model):
    """Stable reference to an external requirement, gate, policy or risk criterion."""

    id: str
    source: str = Field(description="Governance source, e.g. 'GuIA/MGI', 'LGPD', 'OWASP LLM Top 10 (2025)'.")
    reference: str = Field(description="Item, article or gate within the source.")


class VersionBinding(_Model):
    """Component version to which a piece of evidence applies."""

    component: str = Field(description="e.g. 'model:llm', 'index:vector-store', 'pipeline:ingestion'.")
    version: str


class Evidence(_Model):
    id: str
    type: str = Field(description="e.g. 'red-team report', 'evaluation report', 'lineage record'.")
    producer_role: str = Field(description="Role id that produced the evidence.")
    uri: str = Field(description="Storage reference (repository path, registry URI, ticket).")
    sha256: Optional[str] = None
    produced_on: date
    valid_until: Optional[date] = Field(default=None, description="Expiry of the evidence, if any.")
    bindings: list[VersionBinding] = Field(
        default_factory=list, description="Versions the evidence applies to (provenance)."
    )
    automation_hook: Optional[str] = Field(
        default=None,
        description="Machine-readable source from which the evidence can be harvested (CI job, registry API).",
    )


class Control(_Model):
    id: str
    description: str
    status: ControlStatus
    evidence_ids: list[str] = Field(default_factory=list)


class Claim(_Model):
    id: str
    statement: str = Field(description="What must be demonstrated.")
    requirement_ids: list[str] = Field(min_length=1)
    phases: list[Phase] = Field(min_length=1)
    control_ids: list[str] = Field(default_factory=list)
    acceptance_criterion: str = Field(description="Criterion against which evidence sufficiency is judged.")
    sufficiency: Sufficiency
    status: ClaimStatus
    accountable_role: str = Field(description="Role accountable for the claim and its decision.")
    reviewer_role: str = Field(description="Role that reviews evidence sufficiency.")
    revalidation_triggers: list[str] = Field(
        default_factory=list,
        description="Components whose material change reopens the claim, besides its evidence bindings.",
    )


class Decision(_Model):
    decision: DecisionType
    rationale: str
    decided_by: str = Field(description="Role id.")
    decided_on: date
    claim_ids: list[str] = Field(default_factory=list)


class ChangeEvent(_Model):
    """Material change that may invalidate previously accepted evidence."""

    component: str
    new_version: str
    description: str
    occurred_on: date


class RevalidationEntry(_Model):
    event: ChangeEvent
    previous_version: Optional[str]
    reopened_claim_ids: list[str]
    unaffected_claim_ids: list[str]


class SAIARecord(_Model):
    """A SAIA assurance record for one AI system."""

    saia_version: str = "0.1"
    system_id: str
    name: str
    purpose: str
    context_of_use: str
    affected_groups: list[str] = Field(default_factory=list)
    risk_profile: RiskProfile
    current_phase: Phase
    current_versions: dict[str, str] = Field(
        default_factory=dict, description="Deployed version of each tracked component."
    )
    roles: list[Role]
    requirements: list[RequirementBinding]
    claims: list[Claim]
    controls: list[Control]
    evidence: list[Evidence]
    residual_risk: str = ""
    decisions: list[Decision] = Field(default_factory=list)
    revalidation_history: list[RevalidationEntry] = Field(default_factory=list)

    def index(self) -> dict[str, dict]:
        """Lookup tables by id."""
        return {
            "roles": {r.id: r for r in self.roles},
            "requirements": {r.id: r for r in self.requirements},
            "claims": {c.id: c for c in self.claims},
            "controls": {c.id: c for c in self.controls},
            "evidence": {e.id: e for e in self.evidence},
        }

    def evidence_for_claim(self, claim: Claim) -> list[Evidence]:
        idx = self.index()
        out: list[Evidence] = []
        for cid in claim.control_ids:
            control = idx["controls"].get(cid)
            if control is None:
                continue
            out.extend(idx["evidence"][e] for e in control.evidence_ids if e in idx["evidence"])
        return out
