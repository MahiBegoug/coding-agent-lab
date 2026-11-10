"""Run one repair from the terminal or open the Gradio page."""

import argparse
import sys
from pathlib import Path

from bootstrap import build_service
from core.cli_trace import format_repair_trace_event, print_repair_summary


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

    def print_trace_event(event: dict[str, object]) -> None:
        print(format_repair_trace_event(event), flush=True)

    try:
        result = build_service(args.provider, trace_listener=print_trace_event).repair(
            args.project
        )
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print_repair_summary(result)
    return 0 if result.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
