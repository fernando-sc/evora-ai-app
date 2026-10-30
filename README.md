# EvOrA-AI SAIA artifact

Executable artifact accompanying the paper *EvOrA-AI: An Evidence-Oriented Assurance Layer for Public-Sector AI Governance* (INCISCOS 2026).

EvOrA-AI is a framework-agnostic assurance layer. It binds each external governance requirement to explicit claims, controls, version-bound evidence, sufficiency criteria, accountable roles, decisions and revalidation triggers. These relationships are recorded in **SAIA (Simplified Algorithmic Impact Assessment)**, which is filled progressively across the lifecycle phases L1–L6.

```text
requirement → claim → control → evidence (version-bound) → sufficiency criterion → accountable role → decision / revalidation
```

## Contents

| Path | Content |
|---|---|
| `schema/saia.schema.json` | JSON Schema of the SAIA record (generated from `src/evora/saia.py`) |
| `src/evora/` | SAIA model, validator (rules R1–R9), change-triggered selective revalidation, analytical indicators, CLI |
| `examples/rag-citizen-service/` | Illustrative SAIA record for a **hypothetical** RAG citizen-service system, plus an LLM-update change event |
| `notebooks/ex_ante_evaluation.ipynb` | Executed notebook that reproduces the ex ante indicators reported in the paper (Table VI) |
| `tests/` | pytest suite |

## Usage

```bash
pip install -e ".[dev]"
evora validate examples/rag-citizen-service/saia.json --as-of 2026-10-29
evora change examples/rag-citizen-service/saia.json examples/rag-citizen-service/change_llm_update.json --as-of 2026-10-29
evora indicators examples/rag-citizen-service/saia.json
evora schema > schema/saia.schema.json
pytest
```

## Validator rules

| Rule | Checks |
|---|---|
| R1 | Every requirement is bound to at least one claim |
| R2 | References (requirements, roles, controls, evidence) resolve |
| R3 | Every claim has a control and an acceptance criterion |
| R4 | Every implemented or verified control has evidence |
| R5 | Accepted claims have sufficient evidence (a conditional sufficiency raises a warning) |
| R6 | Evidence version bindings match the deployed versions (no stale evidence) |
| R7 | Evidence is within its validity window |
| R8 | Separation of duties; an independent reviewer for high-risk profiles |
| R9 | The latest decision is consistent with the assurance state (Excessive risk cannot proceed) |

A change event reopens only the claims whose evidence is bound to the changed component, or that list it as a revalidation trigger. The previous state is kept in the revalidation history.

## Scope and limitations

The RAG instance is **hypothetical** and contains no field data. The indicators characterize the design of one illustrative record. They are **not** measurements of effort, decision latency or effectiveness, which are left to the next research cycle. Automatic harvesting of evidence from CI, registries or evaluation platforms is not implemented: the record stores automation hooks, and the validator checks version bindings.

## License

Apache-2.0. See `LICENSE` and `CITATION.cff`.
