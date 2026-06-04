from __future__ import annotations

from typing import Optional

from rich.text import Text
from textual.app import ComposeResult
from textual.message import Message
from textual.widget import Widget
from textual.widgets import DataTable, Label

from ..api import Execution, NodeRun
from ..push import LiveExecution

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
        self._execution: Optional[Execution] = None
        self._node_runs: list[NodeRun] = []
        self._wf_node_names: list[str] = []
        self._live: Optional[LiveExecution] = None

    def compose(self) -> ComposeResult:
        yield Label("Select an execution above to inspect its nodes", id="detail-label")
        t = DataTable(id="node-dt", cursor_type="row", zebra_stripes=True)
        t.add_column("Node",  key="node",  width=26)
        t.add_column("",      key="bar",   width=_MAX_BAR + 2)
        t.add_column("Time",  key="time",  width=8)
        t.add_column("Items", key="items", width=6)
        yield t

    def show_execution(
        self,
        execution: Execution,
        wf_node_names: list[str] | None = None,
        live: LiveExecution | None = None,
    ) -> None:
        self._execution = execution
        self._node_runs = execution.node_runs
        if wf_node_names is not None:
            self._wf_node_names = wf_node_names
        if execution.status not in ("running", "waiting", "new"):
            self._live = None
        elif live is not None:
            self._live = live
        self._rebuild()

    def update_live(self, live: LiveExecution | None) -> None:
        self._live = live
        if self._execution and self._execution.status in ("running", "waiting", "new"):
            self._rebuild()

    def clear_detail(self) -> None:
        self._execution = None
        self._node_runs = []
        self._live = None
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

    # ── private ────────────────────────────────────────────────────────────────

    def _rebuild(self) -> None:
        if not self._execution:
            return
        execution = self._execution
        is_running = execution.status in ("running", "waiting", "new")
        active_node = self._live.active_node if self._live else None

        # Header label
        icon, _ = _STATUS.get(execution.status, ("?", "dim"))
        duration = _fmt_dur(execution.duration_seconds)
        label = Text()
        label.append(f"#{execution.id}", style="dim")
        label.append(f"  ·  {execution.workflow_name}  ·  ")
        label.append(
            f"{icon} {execution.status.capitalize()}",
            style="bold yellow" if is_running else "",
        )
        label.append(f"  ·  {duration}")
        if is_running:
            node_hint = f"▶ {active_node}" if active_node else "▶ running"
            label.append(f"  ·  {node_hint}", style="bold yellow")
        self.query_one("#detail-label", Label).update(label)

        # Table
        table = self.query_one(DataTable)
        table.clear()

        if self._live and self._live.completed:
            # Real-time data from WebSocket push
            max_ms = max((ms for _, ms, _, _ in self._live.completed), default=1) or 1
            for i, (name, ms, items, err) in enumerate(self._live.completed):
                table.add_row(*_make_node_row(name, ms, items, err, max_ms), key=f"live_{i}")

        elif self._node_runs:
            # REST API data (available after execution completes)
            max_ms = max((n.execution_time_ms for n in self._node_runs), default=1) or 1
            for i, node in enumerate(self._node_runs):
                table.add_row(
                    *_make_node_row(node.name, node.execution_time_ms, node.output_items, node.error, max_ms),
                    key=str(i),
                )

        elif is_running and self._wf_node_names:
            # Fallback: show workflow node structure as a plan
            for i, name in enumerate(self._wf_node_names):
                table.add_row(
                    Text("○ " + name[:24], style="dim"),
                    Text("·" * 4, style="dim"),
                    Text("—", style="dim"),
                    Text("—", style="dim"),
                    key=f"__plan_{i}__",
                )

        if is_running:
            label_str = f"▶ {active_node}" if active_node else "▶ running…"
            table.add_row(
                Text(label_str, style="bold yellow"),
                Text("░" * _MAX_BAR, style="yellow"),
                Text("running", style="bold yellow"),
                Text("—", style="dim"),
                key="__running__",
            )


def _make_node_row(
    name: str,
    exec_ms: int,
    items: int,
    error: Optional[str],
    max_ms: int,
) -> tuple:
    if error:
        name_text = Text(name[:24], style="bold red")
        bar_char, bar_style = "█", "bold red"
        time_text = Text(f"{exec_ms}ms", style="red")
    elif exec_ms == 0:
        name_text = Text(name[:24], style="dim")
        bar_char, bar_style = "▒", "yellow"
        time_text = Text("—", style="dim yellow")
    else:
        name_text = Text(name[:24], style="white")
        bar_char, bar_style = "█", "green"
        time_text = Text(f"{exec_ms}ms", style="dim")

    width = max(1, int((exec_ms / max_ms) * _MAX_BAR))
    bar_text = Text(bar_char * width, style=bar_style)
    items_text = Text(str(items), style="dim")
    return name_text, bar_text, time_text, items_text


def _fmt_dur(seconds: float | None) -> str:
    if seconds is None:
        return "—"
    if seconds < 1:
        return f"{int(seconds * 1000)}ms"
    if seconds < 60:
        return f"{seconds:.1f}s"
    return f"{int(seconds // 60)}m{int(seconds % 60)}s"
