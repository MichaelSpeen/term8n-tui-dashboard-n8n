from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.message import Message
from textual.widget import Widget
from textual.widgets import DataTable, Label

from ..api import Execution, NodeRun

_STATUS = {
    "success": ("✓", "bold green"),
    "running": ("●", "bold yellow"),
    "waiting": ("◐", "bold cyan"),
    "error":   ("✗", "bold red"),
}

_MAX_BAR = 32


class ExecutionDetail(Widget):
    BORDER_TITLE = "Node Timeline  (Enter / click to inspect)"

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
    ExecutionDetail > DataTable {
        height: 1fr;
    }
    """

    class NodeSelected(Message):
        def __init__(self, node: NodeRun) -> None:
            super().__init__()
            self.node = node

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._node_runs: list[NodeRun] = []

    def compose(self) -> ComposeResult:
        yield Label("Select an execution above to inspect its nodes", id="detail-label")
        t = DataTable(id="node-dt", cursor_type="row", zebra_stripes=True)
        t.add_column("Node",    key="node",  width=26)
        t.add_column("",        key="bar",   width=_MAX_BAR + 2)
        t.add_column("Time",    key="time",  width=8, )
        t.add_column("Items",   key="items", width=6)
        yield t

    def show_execution(self, execution: Execution) -> None:
        self._node_runs = execution.node_runs
        icon, _ = _STATUS.get(execution.status, ("?", "dim"))
        duration = _fmt_dur(execution.duration_seconds)
        self.query_one("#detail-label", Label).update(
            f"#{execution.id}  ·  {execution.workflow_name}  ·  "
            f"{icon} {execution.status.capitalize()}  ·  {duration}"
        )
        table = self.query_one(DataTable)
        table.clear()
        max_ms = max((n.execution_time_ms for n in self._node_runs), default=1) or 1
        for i, node in enumerate(self._node_runs):
            table.add_row(*_make_row(node, max_ms), key=str(i))

    def clear_detail(self) -> None:
        self._node_runs = []
        self.query_one("#detail-label", Label).update(
            "Select an execution above to inspect its nodes"
        )
        self.query_one(DataTable).clear()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        idx = int(str(event.row_key.value))
        if 0 <= idx < len(self._node_runs):
            self.post_message(ExecutionDetail.NodeSelected(self._node_runs[idx]))


def _make_row(node: NodeRun, max_ms: int) -> tuple:
    if node.error:
        name_text = Text(node.name[:24], style="bold red")
        bar_char, bar_style = "█", "bold red"
        time_text = Text(f"{node.execution_time_ms}ms", style="red")
    elif node.execution_time_ms == 0:
        name_text = Text(node.name[:24], style="dim")
        bar_char, bar_style = "▒", "yellow"
        time_text = Text("—", style="dim yellow")
    else:
        name_text = Text(node.name[:24], style="white")
        bar_char, bar_style = "█", "green"
        time_text = Text(f"{node.execution_time_ms}ms", style="dim")

    width = max(1, int((node.execution_time_ms / max_ms) * _MAX_BAR))
    bar_text = Text(bar_char * width, style=bar_style)

    items_text = Text(str(node.output_items), style="dim")
    return name_text, bar_text, time_text, items_text


def _fmt_dur(seconds: float | None) -> str:
    if seconds is None:
        return "—"
    if seconds < 1:
        return f"{int(seconds * 1000)}ms"
    if seconds < 60:
        return f"{seconds:.1f}s"
    return f"{int(seconds // 60)}m{int(seconds % 60)}s"
