from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import DataTable, Label

from ..api import Execution

_STATUS: dict[str, tuple[str, str]] = {
    "success": ("✓", "bold green"),
    "running": ("●", "bold yellow"),
    "waiting": ("◐", "bold cyan"),
    "error":   ("✗", "bold red"),
}


class ExecutionDetail(Widget):
    BORDER_TITLE = "Node Detail"

    DEFAULT_CSS = """
    ExecutionDetail {
        height: 13;
        border: thick $primary-darken-2;
    }
    ExecutionDetail > #detail-label {
        width: 100%;
        height: 1;
        background: $primary-darken-3;
        padding: 0 1;
    }
    ExecutionDetail DataTable {
        height: 1fr;
    }
    """

    def compose(self) -> ComposeResult:
        yield Label("Select an execution above to inspect its nodes", id="detail-label")
        t = DataTable(id="node-dt", show_cursor=False, zebra_stripes=True)
        t.add_column("Node",      key="node",  width=32)
        t.add_column("Status",    key="status", width=9)
        t.add_column("Time",      key="time",   width=8)
        t.add_column("Items out", key="items",  width=9)
        yield t

    def show_execution(self, execution: Execution) -> None:
        icon, _ = _STATUS.get(execution.status, ("?", "dim"))
        duration = _fmt_duration(execution.duration_seconds)
        self.query_one("#detail-label", Label).update(
            f"#{execution.id}  ·  {execution.workflow_name}  ·  "
            f"{icon} {execution.status.capitalize()}  ·  {duration}"
        )

        table = self.query_one("#node-dt", DataTable)
        table.clear()

        if not execution.node_runs:
            table.add_row(
                Text("No node data available (execution may still be running)", style="dim"),
                "-", "-", "-",
            )
            return

        for node in execution.node_runs:
            if node.error:
                s_cell = Text("✗ Err", style="bold red")
            else:
                s_cell = Text("✓ OK", style="bold green")
            time_str = f"{node.execution_time_ms}ms" if node.execution_time_ms else "-"
            table.add_row(node.name, s_cell, time_str, str(node.output_items))

    def clear_detail(self) -> None:
        self.query_one("#detail-label", Label).update(
            "Select an execution above to inspect its nodes"
        )
        self.query_one("#node-dt", DataTable).clear()


def _fmt_duration(seconds: float | None) -> str:
    if seconds is None:
        return "-"
    if seconds < 1:
        return f"{int(seconds * 1000)}ms"
    if seconds < 60:
        return f"{seconds:.1f}s"
    return f"{int(seconds // 60)}m{int(seconds % 60)}s"
