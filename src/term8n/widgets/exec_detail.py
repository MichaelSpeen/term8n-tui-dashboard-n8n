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

    def show_execution(self, execution: Execution, wf_node_names: list[str] | None = None) -> None:
        self._node_runs = execution.node_runs
        is_running = execution.status in ("running", "waiting", "new")

        icon, _ = _STATUS.get(execution.status, ("?", "dim"))
        duration = _fmt_dur(execution.duration_seconds)
        label_text = Text()
        label_text.append(f"#{execution.id}", style="dim")
        label_text.append(f"  ·  {execution.workflow_name}  ·  ")
        label_text.append(f"{icon} {execution.status.capitalize()}", style="bold yellow" if is_running else "")
        label_text.append(f"  ·  {duration}")
        if is_running:
            label_text.append("  ·  ▶ running", style="bold yellow")
        self.query_one("#detail-label", Label).update(label_text)

        table = self.query_one(DataTable)
        table.clear()

        if self._node_runs:
            max_ms = max((n.execution_time_ms for n in self._node_runs), default=1) or 1
            for i, node in enumerate(self._node_runs):
                table.add_row(*_make_row(node, max_ms), key=str(i))
        elif is_running and wf_node_names:
            # n8n doesn't expose partial runData via REST — show workflow nodes as a plan
            for i, name in enumerate(wf_node_names):
                table.add_row(
                    Text("○ " + name[:24], style="dim"),
                    Text("·" * 4, style="dim"),
                    Text("—", style="dim"),
                    Text("—", style="dim"),
                    key=f"__plan_{i}__",
                )

        if is_running:
            table.add_row(
                Text("▶ running…", style="bold yellow"),
                Text("░" * _MAX_BAR, style="yellow"),
                Text("running", style="bold yellow"),
                Text("—", style="dim"),
                key="__running__",
            )

    def clear_detail(self) -> None:
        self._node_runs = []
        self.query_one("#detail-label", Label).update(
            "Select an execution above to inspect its nodes"
        )
        self.query_one(DataTable).clear()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        key = str(event.row_key.value)
        if key.startswith("__"):
            return
        idx = int(key)
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
