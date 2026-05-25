from __future__ import annotations

from rich.table import Table
from rich.text import Text
from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.widget import Widget
from textual.widgets import Label, Static

from ..api import Execution, NodeRun

_STATUS = {
    "success": ("✓", "bold green"),
    "running": ("●", "bold yellow"),
    "waiting": ("◐", "bold cyan"),
    "error":   ("✗", "bold red"),
}

_MAX_BAR = 36


class ExecutionDetail(Widget):
    BORDER_TITLE = "Node Timeline"

    DEFAULT_CSS = """
    ExecutionDetail {
        height: 13;
        border: round $primary-darken-1;
    }
    ExecutionDetail > #detail-label {
        height: 1;
        background: $primary-darken-3;
        padding: 0 1;
        width: 100%;
    }
    ExecutionDetail > VerticalScroll {
        height: 1fr;
        padding: 0 1;
    }
    """

    def compose(self) -> ComposeResult:
        yield Label("Select an execution above to inspect its nodes", id="detail-label")
        with VerticalScroll():
            yield Static(id="timeline")

    def show_execution(self, execution: Execution) -> None:
        icon, _ = _STATUS.get(execution.status, ("?", "dim"))
        duration = _fmt_dur(execution.duration_seconds)
        self.query_one("#detail-label", Label).update(
            f"#{execution.id}  ·  {execution.workflow_name}  ·  "
            f"{icon} {execution.status.capitalize()}  ·  {duration}"
        )
        self.query_one("#timeline", Static).update(_build_timeline(execution.node_runs))

    def clear_detail(self) -> None:
        self.query_one("#detail-label", Label).update(
            "Select an execution above to inspect its nodes"
        )
        self.query_one("#timeline", Static).update("")


def _build_timeline(nodes: list[NodeRun]) -> Table:
    table = Table.grid(padding=(0, 1))
    table.add_column("name",  width=28, no_wrap=True)
    table.add_column("bar",   width=_MAX_BAR + 2, no_wrap=True)
    table.add_column("time",  width=9, justify="right")

    if not nodes:
        table.add_row(Text("No node data available", style="dim"), "", "")
        return table

    max_ms = max(n.execution_time_ms for n in nodes) or 1

    for node in nodes:
        if node.error:
            bar_char, bar_style = "█", "bold red"
            name_text = Text(node.name[:26], style="bold red")
            time_text = Text(f"{node.execution_time_ms}ms", style="red")
        elif node.execution_time_ms == 0:
            bar_char, bar_style = "▒", "yellow"
            name_text = Text(node.name[:26], style="dim")
            time_text = Text("—", style="dim yellow")
        else:
            bar_char, bar_style = "█", "green"
            name_text = Text(node.name[:26], style="white")
            time_text = Text(f"{node.execution_time_ms}ms", style="dim")

        width = max(1, int((node.execution_time_ms / max_ms) * _MAX_BAR))
        bar_text = Text(bar_char * width, style=bar_style)

        table.add_row(name_text, bar_text, time_text)

    return table


def _fmt_dur(seconds: float | None) -> str:
    if seconds is None:
        return "—"
    if seconds < 1:
        return f"{int(seconds * 1000)}ms"
    if seconds < 60:
        return f"{seconds:.1f}s"
    return f"{int(seconds // 60)}m{int(seconds % 60)}s"
