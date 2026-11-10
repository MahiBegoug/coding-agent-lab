"""Run one repair from the terminal or open the Gradio page."""

import argparse
import sys
from pathlib import Path

from bootstrap import build_service


def main(argv: list[str] | None = None) -> int:
    """Dispatch the selected command and return a non-zero status on failure."""

    parser = argparse.ArgumentParser(description="Run one repair from the terminal.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    repair_parser = subparsers.add_parser("repair")
    repair_parser.add_argument("project", help="Path to one project under evals/")
    repair_parser.add_argument("--provider", required=True)
    subparsers.add_parser("ui")
    args = parser.parse_args(argv)

    if args.command == "ui":
        from adapters.gradio_ui import create_demo

        workspace_cache = Path.home() / ".cache" / "coding-agent-lab"
        create_demo().launch(allowed_paths=[str(workspace_cache)])
        return 0

    try:
        result = build_service(args.provider).repair(args.project)
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    for event in result.trace:
        print(_format_event(event))
    print("changed files:")
    if result.changed_files:
        for name in result.changed_files:
            print(name)
    else:
        print("(none)")
    if result.test_result is None:
        print("final test: none")
    else:
        print(
            "final test: "
            f"passed={result.test_result.passed} returncode={result.test_result.returncode}"
        )
        print(result.test_result.output, end="" if result.test_result.output.endswith("\n") else "\n")
    return 0 if result.passed else 1


def _format_event(event: dict[str, object]) -> str:
    parts = [str(event.get("event", "event"))]
    for key in ("case", "tool", "summary", "accepted", "ok", "detail", "reason", "passed"):
        if key in event:
            parts.append(f"{key}={event[key]}")
    return " ".join(parts)


if __name__ == "__main__":
    raise SystemExit(main())
