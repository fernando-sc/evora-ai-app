from datetime import date
from pathlib import Path

import pytest

from evora import ChangeEvent, SAIARecord, apply_change, indicators, validate
from evora.saia import ClaimStatus, DecisionType, RiskProfile

EXAMPLE = Path(__file__).resolve().parents[1] / "examples" / "rag-citizen-service"
AS_OF = date(2026, 10, 29)


@pytest.fixture
def record() -> SAIARecord:
    return SAIARecord.model_validate_json((EXAMPLE / "saia.json").read_text(encoding="utf-8"))


@pytest.fixture
def llm_update() -> ChangeEvent:
    return ChangeEvent.model_validate_json((EXAMPLE / "change_llm_update.json").read_text(encoding="utf-8"))


def rules(report):
    return {f.rule for f in report.errors}


def test_example_is_valid(record):
    report = validate(record, AS_OF)
    assert report.ok, report.errors
    assert [f.ref for f in report.warnings] == ["C-05"]


def test_uncovered_requirement(record):
    record.claims[0].requirement_ids = ["REQ-GUIA-GATE"]  # REQ-LLM01 loses its only claim
    assert "R1-requirement-coverage" in rules(validate(record, AS_OF))


def test_claim_without_control(record):
    record.claims[2].control_ids = []
    assert "R3-claim-control" in rules(validate(record, AS_OF))


def test_implemented_control_without_evidence(record):
    record.controls[2].evidence_ids = []
    assert "R4-control-evidence" in rules(validate(record, AS_OF))


def test_expired_evidence(record):
    assert "R7-expired-evidence" in rules(validate(record, date(2027, 2, 1)))  # EV-08 valid until 2027-01-08


def test_reviewer_cannot_review_own_evidence(record):
    record.claims[3].reviewer_role = "ml-eng"
    found = rules(validate(record, AS_OF))
    assert {"R8-separation-of-duties", "R8-independent-review"} <= found


def test_independent_review_only_required_for_high_risk(record):
    record.risk_profile = RiskProfile.MEDIUM
    record.claims[3].reviewer_role = "dpo"
    assert validate(record, AS_OF).ok


def test_excessive_risk_cannot_proceed(record):
    record.risk_profile = RiskProfile.EXCESSIVE
    assert record.decisions[-1].decision is DecisionType.PROCEED
    assert "R9-decision" in rules(validate(record, AS_OF))


def test_selective_revalidation(record, llm_update):
    updated = apply_change(record, llm_update)
    entry = updated.revalidation_history[-1]
    assert entry.previous_version == "vendor-llm-2026-06"
    assert entry.reopened_claim_ids == ["C-01", "C-04", "C-05"]
    assert entry.unaffected_claim_ids == ["C-02", "C-03"]
    status = {c.id: c.status for c in updated.claims}
    assert status["C-02"] is ClaimStatus.ACCEPTED and status["C-03"] is ClaimStatus.ACCEPTED
    # the original record is preserved
    assert all(c.status is ClaimStatus.ACCEPTED for c in record.claims)


def test_change_invalidates_until_revalidated(record, llm_update):
    report = validate(apply_change(record, llm_update), AS_OF)
    assert not report.ok
    stale = {f.ref for f in report.errors if f.rule == "R6-stale-evidence"}
    assert stale == {"C-01/EV-01", "C-04/EV-08"}


def test_unrelated_change_reopens_nothing(record):
    event = ChangeEvent(component="ui:theme", new_version="2", description="cosmetic", occurred_on=AS_OF)
    updated = apply_change(record, event)
    assert updated.revalidation_history[-1].reopened_claim_ids == []
    assert validate(updated, AS_OF).ok


def test_indicators(record, llm_update):
    ind = indicators(apply_change(record, llm_update))
    assert ind["requirement_coverage"] == 1.0
    assert ind["evidence_items"] == 11 and ind["evidence_with_automation_hook"] == 6
    assert ind["revalidation_scope_last_change"] == pytest.approx(0.6)


def test_schema_matches_committed_file():
    import json

    committed = json.loads((Path(__file__).resolve().parents[1] / "schema" / "saia.schema.json").read_text())
    assert committed == SAIARecord.model_json_schema()
