"""Command-line interface: ``evora schema | validate | change | indicators``."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from .indicators import indicators
from .revalidation import apply_change
from .saia import ChangeEvent, SAIARecord
from .validate import validate


def _load(path: str) -> SAIARecord:
    return SAIARecord.model_validate_json(Path(path).read_text(encoding="utf-8"))


def _print_report(record: SAIARecord, as_of: date | None) -> int:
    report = validate(record, as_of)
    for f in report.findings:
        print(f"{f.severity.value.upper():7} {f.rule:26} {f.ref:16} {f.message}")
    print(f"\n{len(report.errors)} error(s), {len(report.warnings)} warning(s): {'VALID' if report.ok else 'NOT VALID'}")
    return 0 if report.ok else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="evora", description="EvOrA-AI SAIA tooling")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("schema", help="print the SAIA JSON Schema")
    p_val = sub.add_parser("validate", help="validate a SAIA record")
    p_val.add_argument("record")
    p_val.add_argument("--as-of", type=date.fromisoformat)
    p_chg = sub.add_parser("change", help="apply a change event and revalidate selectively")
    p_chg.add_argument("record")
    p_chg.add_argument("event", help="ChangeEvent JSON file")
    p_chg.add_argument("-o", "--output", help="write the updated record here")
    p_chg.add_argument("--as-of", type=date.fromisoformat)
    p_ind = sub.add_parser("indicators", help="print analytical ex ante indicators")
    p_ind.add_argument("record")
    args = parser.parse_args(argv)

    if args.cmd == "schema":
        print(json.dumps(SAIARecord.model_json_schema(), indent=2, ensure_ascii=False))
        return 0
    if args.cmd == "validate":
        return _print_report(_load(args.record), args.as_of)
    if args.cmd == "indicators":
        print(json.dumps(indicators(_load(args.record)), indent=2))
        return 0
    if args.cmd == "change":
        event = ChangeEvent.model_validate_json(Path(args.event).read_text(encoding="utf-8"))
        updated = apply_change(_load(args.record), event)
        entry = updated.revalidation_history[-1]
        print(f"change: {event.component} {entry.previous_version} -> {event.new_version}")
        print(f"reopened:   {', '.join(entry.reopened_claim_ids) or '-'}")
        print(f"unaffected: {', '.join(entry.unaffected_claim_ids) or '-'}\n")
        if args.output:
            Path(args.output).write_text(updated.model_dump_json(indent=2), encoding="utf-8")
        _print_report(updated, args.as_of)
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
