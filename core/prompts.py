"""Text that a repair model will receive.

These helpers only prepare messages. They do not parse a reply or run a tool.
"""


def system_instruction() -> str:
    """Return the standing instruction for one repair conversation."""

    return """You repair one small Python project.
Inspect the local code, reproduce a failing test before editing, make one focused edit, and verify the repair with tests.
Reply with one JSON object only. Do not use Markdown or prose.
The optional summary is a short public label for the trace, not private reasoning.
Allowed actions:
{"tool":"read_file","path":"test_calculator.py","summary":"Read the test"}
{"tool":"run_tests","summary":"Reproduce the failure"}
{"tool":"edit_file","path":"calculator.py","content":"..."}
"""


def case_request(case_name: str, relative_files: list[str]) -> str:
    """Ask the model to repair one named case and list its files."""

    file_list = "\n".join(relative_files)
    return f"Repair case {case_name}.\nRelative files:\n{file_list}"


def tool_result_message(observation: str) -> str:
    """Wrap one tool observation so the model can choose the next action."""

    return f"Tool result:\n{observation}"
