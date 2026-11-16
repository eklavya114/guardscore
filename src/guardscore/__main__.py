import argparse
import sys
from collections import Counter
from pathlib import Path

from guardscore.cases import load_cases, validate_cases

CASES_DIR = Path(__file__).parent.parent.parent / "cases"


def cmd_validate(cases_dir: Path) -> int:
    cases = load_cases(cases_dir)
    if not cases:
        print("No cases found.")
        return 0

    errors = validate_cases(cases)
    if errors:
        for error in errors:
            print(error)
        print(f"\n{len(errors)} error(s) found in {len(cases)} case(s).")
        return 1

    print(f"All {len(cases)} case(s) are valid.")
    return 0


def cmd_stats(cases_dir: Path) -> int:
    cases = load_cases(cases_dir)
    if not cases:
        print("No cases found.")
        return 0

    kind_counts = Counter(c.kind for c in cases)
    verdict_counts = Counter(c.expected for c in cases)
    outcome_counts = Counter(c.outcome for c in cases if c.outcome is not None)
    tag_counts: Counter = Counter()
    for c in cases:
        tag_counts.update(c.tags)

    print(f"Total cases: {len(cases)}")
    print()
    print("By kind:")
    for kind, count in sorted(kind_counts.items()):
        print(f"  {kind}: {count}")
    print()
    print("By expected verdict:")
    for verdict, count in sorted(verdict_counts.items()):
        print(f"  {verdict}: {count}")
    print()
    print("By outcome:")
    for outcome, count in sorted(outcome_counts.items()):
        print(f"  {outcome}: {count}")
    print()
    print("By tag:")
    for tag, count in tag_counts.most_common():
        print(f"  {tag}: {count}")
    return 0


def cmd_run(argv: list[str]) -> int:
    from guardscore.adapters import GuardSpecError, load_guard
    from guardscore.report import render_detail, render_table
    from guardscore.runner import run_guard_over_cases

    parser = argparse.ArgumentParser(prog="guardscore run")
    parser.add_argument("--guard", action="append", default=[], metavar="SPEC",
                        help="a guard spec, may be given more than once")
    parser.add_argument("--cases", type=Path, default=CASES_DIR, help="directory of case files")
    parser.add_argument("--timeout", type=float, default=10.0, help="guard timeout in seconds")
    parser.add_argument("--detail", action="store_true", help="print every case decision")
    parser.add_argument("--json", type=Path, default=None, help="write a JSON results file")
    parser.add_argument("--md", type=Path, default=None, help="write a markdown report")
    opts = parser.parse_args(argv)

    if not opts.guard:
        print("Give at least one --guard SPEC")
        return 1

    cases = load_cases(opts.cases)
    if not cases:
        print("No cases found.")
        return 1

    summaries = []
    for spec in opts.guard:
        try:
            guard = load_guard(spec, timeout=opts.timeout)
        except GuardSpecError as exc:
            print(f"Cannot load guard '{spec}': {exc}")
            return 1
        summaries.append(run_guard_over_cases(guard, spec, cases, timeout=opts.timeout))

    print(render_table(summaries))

    if opts.detail:
        print()
        print(render_detail(summaries))

    if opts.json is not None:
        from guardscore.results import write_results_file
        write_results_file(opts.json, summaries, cases)
        print(f"\nWrote JSON results to {opts.json}")

    if opts.md is not None:
        from guardscore.results import compute_case_set_id
        from guardscore.report_md import write_markdown_report
        write_markdown_report(opts.md, summaries, cases, compute_case_set_id(cases))
        print(f"Wrote markdown report to {opts.md}")

    return 0


def main() -> None:
    args = sys.argv[1:]
    if not args:
        print("Usage: guardscore <validate|stats|run>")
        sys.exit(1)

    command = args[0]
    cases_dir = CASES_DIR

    if command == "validate":
        sys.exit(cmd_validate(cases_dir))
    elif command == "stats":
        sys.exit(cmd_stats(cases_dir))
    elif command == "run":
        sys.exit(cmd_run(args[1:]))
    else:
        print(f"Unknown command: {command!r}")
        print("Usage: guardscore <validate|stats|run>")
        sys.exit(1)


if __name__ == "__main__":
    main()
