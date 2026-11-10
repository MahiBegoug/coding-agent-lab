"""Human-readable terminal output for repair trace events."""

from core.models import RepairResult


def format_repair_trace_event(event: dict[str, object]) -> str:
    """Turn one stored trace event into a labeled terminal line or block."""

    kind = str(event.get("event", "event"))
    if kind == "repair_started":
        case = event.get("case", "unknown")
        return f"START  Repairing case: {case}"

    if kind == "model_response":
        if event.get("accepted") is False:
            reason = event.get("reason", "rejected")
            return f"ACTION Rejected model step — {reason}"
        tool = event.get("tool", "unknown")
        parts = [f"ACTION Requested {tool}"]
        if path := event.get("path"):
            parts.append(f"({path})")
        if summary := event.get("summary"):
            parts.append(f"— {summary}")
        return " ".join(parts)

    if kind == "tool_result":
        tool = event.get("tool", "tool")
        status = "ok" if event.get("ok") else "failed"
        header = f"RESULT {tool} ({status})"
        if summary := event.get("summary"):
            header = f"{header} — {summary}"
        if detail := event.get("detail"):
            if detail != summary and detail not in str(event.get("observation", "")):
                header = f"{header}\n       {detail}"
        observation = event.get("observation")
        if isinstance(observation, str) and observation.strip():
            body = _indent_multiline(observation, "       ")
            return f"{header}\n{body}"
        return header

    if kind == "repair_finished":
        passed = event.get("passed")
        reason = event.get("reason", "")
        outcome = "success" if passed else "failure"
        return f"FINISHED Repair {outcome} — {reason}"

    return f"TRACE  {kind}"


def print_repair_summary(result: RepairResult) -> None:
    """Print changed files and the final sandboxed test status."""

    print("\nChanged files:")
    if result.changed_files:
        for name in result.changed_files:
            print(f"  {name}")
    else:
        print("  (none)")

    if result.test_result is None:
        print("\nFinal sandboxed test: none")
        return

    status = "PASSED" if result.test_result.passed else "FAILED"
    print(
        f"\nFinal sandboxed test: {status} "
        f"(returncode {result.test_result.returncode})"
    )
    if result.test_result.output.strip():
        print(_indent_multiline(result.test_result.output.rstrip(), "  "))


def _indent_multiline(text: str, prefix: str) -> str:
    lines = text.splitlines()
    if not lines:
        return prefix
    return "\n".join(f"{prefix}{line}" if line else prefix for line in lines)
