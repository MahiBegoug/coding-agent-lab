"""Present the existing repair service in a small Gradio page."""

import zipfile
from pathlib import Path

import gradio as gr

from bootstrap import build_service
from core.models import RepairResult

CASES = [
    "arithmetic",
    "balanced_brackets",
    "median",
    "multi_function",
    "unique_words",
]


def create_demo() -> gr.Blocks:
    """Build the Gradio page that starts one scripted repair."""

    service = build_service("scripted")

    def run_repair(case_name: str) -> tuple[str, str, str, str | None]:
        """Call the existing service and format its public result."""

        if case_name not in CASES:
            raise gr.Error("Select one of the supplied projects.")
        result = service.repair(f"evals/{case_name}")
        return (
            _format_trace(result),
            _format_changed_files(result),
            _format_test_output(result),
            _zip_workspace(result.workspace),
        )

    with gr.Blocks(title="Python Repair Agent") as demo:
        gr.Markdown("# Python Repair Agent")
        case = gr.Dropdown(choices=CASES, value="arithmetic", label="Project")
        start = gr.Button("Start repair")
        trace = gr.Textbox(label="Trace", lines=12)
        changed = gr.Textbox(label="Changed files", lines=12)
        tests = gr.Textbox(label="Final test output", lines=8)
        download = gr.File(label="Repaired workspace ZIP")
        start.click(run_repair, inputs=[case], outputs=[trace, changed, tests, download])
    return demo


def _format_trace(result: RepairResult) -> str:
    lines: list[str] = []
    for event in result.trace:
        parts = [str(event.get("event", "event"))]
        for key in ("case", "tool", "summary", "accepted", "ok", "detail", "reason", "passed"):
            if key in event:
                parts.append(f"{key}={event[key]}")
        lines.append(" ".join(parts))
    return "\n".join(lines)


def _format_changed_files(result: RepairResult) -> str:
    if not result.changed_files:
        return "(none)"
    workspace = Path(result.workspace)
    blocks: list[str] = []
    for name in result.changed_files:
        text = (workspace / name).read_text(encoding="utf-8")
        blocks.append(f"{name}\n{text}")
    return "\n\n".join(blocks)


def _format_test_output(result: RepairResult) -> str:
    if result.test_result is None:
        return "final test: none"
    header = (
        f"passed={result.test_result.passed} returncode={result.test_result.returncode}"
    )
    return f"{header}\n{result.test_result.output}"


def _zip_workspace(workspace: str) -> str | None:
    if not workspace:
        return None
    workspace_path = Path(workspace)
    if not workspace_path.is_dir():
        return None
    zip_path = workspace_path.parent / f"{workspace_path.name}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in workspace_path.rglob("*"):
            if path.is_file():
                archive.write(path, path.relative_to(workspace_path).as_posix())
    return str(zip_path)
