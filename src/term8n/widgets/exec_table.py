from __future__ import annotations

from datetime import datetime, timezone

from rich.text import Text
from textual.app import ComposeResult
from textual.message import Message
from textual.widget import Widget
from textual.widgets import DataTable

from ..api import Execution

_STATUS_STYLE: dict[str, tuple[str, str]] = {
    "running": ("●", "bold yellow"),
    "waiting": ("◐", "bold cyan"),
    "success": ("✓", "bold green"),
    "error":   ("✗", "bold red"),
    "new":     ("○", "dim white"),
}

_MODE_LABELS: dict[str, str] = {
    "webhook":  "hook",
    "trigger":  "trig",
    "manual":   "manu",
    "schedule": "cron",
    "internal": "int ",
    "retry":    "retry",
}

_COLS = ["id", "workflow", "status", "mode", "started", "duration"]


class ExecutionTable(Widget):
    BORDER_TITLE = "Executions"

    DEFAULT_CSS = """
    ExecutionTable {
        height: 1fr;
        border: round $primary-darken-1;
    }
    ExecutionTable DataTable {
        height: 1fr;
    }
    """

    class ExecutionSelected(Message):
        def __init__(self, execution_id: str) -> None:
            super().__init__()
            self.execution_id = execution_id

    def compose(self) -> ComposeResult:
        t = DataTable(id="dt", cursor_type="row", zebra_stripes=True)
        t.add_column("ID",       key="id",       width=8)
        t.add_column("Workflow", key="workflow",  width=24)
        t.add_column("Status",   key="status",   width=12)
        t.add_column("Mode",     key="mode",     width=6)
        t.add_column("Started",  key="started",  width=10)
        t.add_column("Duration", key="duration", width=9)
        yield t

    def update_executions(self, executions: list[Execution]) -> None:
        table = self.query_one(DataTable)
        cursor_row = table.cursor_row

        table.clear()
        for e in executions:
            table.add_row(*_make_row(e), key=e.id)

        if table.row_count > 0:
            table.move_cursor(row=min(cursor_row, table.row_count - 1))

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        self.post_message(ExecutionTable.ExecutionSelected(str(event.row_key.value)))


def _make_row(e: Execution) -> tuple:
    icon, style = _STATUS_STYLE.get(e.status, ("?", "dim"))
    status_cell = Text(f"{icon} {e.status.capitalize()}", style=style)
    mode_cell = _MODE_LABELS.get(e.mode, e.mode[:5])
    short_id = Text(f"#{e.id[-6:]}", style="dim")
    wf_name = e.workflow_name[:23] + "…" if len(e.workflow_name) > 24 else e.workflow_name

    return (
        short_id,
        wf_name,
        status_cell,
        mode_cell,
        _fmt_age(e.started_at),
        _fmt_duration(e.duration_seconds),
    )


def _fmt_age(dt: datetime | None) -> str:
    if not dt:
        return "-"
    secs = (datetime.now(timezone.utc) - dt).total_seconds()
    if secs < 0:
        return "just now"
    if secs < 60:
        return f"{int(secs)}s ago"
    if secs < 3600:
        return f"{int(secs / 60)}m ago"
    if secs < 86400:
        return f"{int(secs / 3600)}h ago"
    return f"{int(secs / 86400)}d ago"


def _fmt_duration(seconds: float | None) -> str:
    if seconds is None:
        return "-"
    if seconds < 1:
        return f"{int(seconds * 1000)}ms"
    if seconds < 60:
        return f"{seconds:.1f}s"
    return f"{int(seconds // 60)}m{int(seconds % 60)}s"
