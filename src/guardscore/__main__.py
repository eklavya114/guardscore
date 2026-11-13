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
    print("By tag:")
    for tag, count in tag_counts.most_common():
        print(f"  {tag}: {count}")
    return 0


def main() -> None:
    args = sys.argv[1:]
    if not args:
        print("Usage: guardscore <validate|stats>")
        sys.exit(1)

    command = args[0]
    cases_dir = CASES_DIR

    if command == "validate":
        sys.exit(cmd_validate(cases_dir))
    elif command == "stats":
        sys.exit(cmd_stats(cases_dir))
    else:
        print(f"Unknown command: {command!r}")
        print("Usage: guardscore <validate|stats>")
        sys.exit(1)


if __name__ == "__main__":
    main()
