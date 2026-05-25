from __future__ import annotations

from datetime import datetime, timezone

from rich.text import Text
from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Sparkline, Static

from ..api import Execution


class StatsBar(Widget):
    BORDER_TITLE = "Activity"

    DEFAULT_CSS = """
    StatsBar {
        height: 6;
        border: round $primary-darken-1;
        padding: 0 1;
    }
    StatsBar Static {
        height: 1;
        width: 100%;
        margin-top: 1;
    }
    StatsBar Sparkline {
        height: 3;
        width: 100%;
    }
    """

    def compose(self) -> ComposeResult:
        yield Static(id="stat-row")
        yield Sparkline(
            [0.0],
            id="sparkline",
            summary_function=max,
            min_color="#1a5c30",
            max_color="#00e676",
        )

    def update_stats(self, executions: list[Execution]) -> None:
        today = datetime.now(timezone.utc).date()
        running = sum(1 for e in executions if e.status == "running")
        errors  = sum(1 for e in executions if e.status == "error")
        today_count = sum(
            1 for e in executions
            if e.started_at and e.started_at.astimezone(timezone.utc).date() == today
        )
        finished_durations = [
            e.duration_seconds
            for e in executions
            if e.duration_seconds is not None and e.status in ("success", "error")
        ]
        avg_dur = sum(finished_durations) / len(finished_durations) if finished_durations else None

        t = Text()
        t.append("  ● ", style="bold yellow" if running else "dim")
        t.append(f"{running} running   ", style="bold white" if running else "dim")
        t.append("✗ ", style="bold red" if errors else "dim")
        t.append(f"{errors} errors   ", style="bold white" if errors else "dim")
        t.append("▪ ", style="bold cyan")
        t.append(f"{today_count} today   ", style="bold white")
        t.append("⌀ avg ", style="bold green")
        t.append(_fmt_dur(avg_dur) if avg_dur is not None else "—", style="bold white")

        self.query_one("#stat-row", Static).update(t)

        # sparkline: oldest → newest finished execution durations
        ordered = sorted(
            [
                (e.started_at, e.duration_seconds)
                for e in executions
                if e.duration_seconds is not None
                and e.status in ("success", "error")
                and e.started_at
            ],
            key=lambda x: x[0],
        )
        self.query_one(Sparkline).data = [d for _, d in ordered[-60:]] or [0.0]


def _fmt_dur(seconds: float | None) -> str:
    if seconds is None:
        return "—"
    if seconds < 1:
        return f"{int(seconds * 1000)}ms"
    if seconds < 60:
        return f"{seconds:.1f}s"
    return f"{int(seconds // 60)}m{int(seconds % 60)}s"
