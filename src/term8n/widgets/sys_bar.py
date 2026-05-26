from __future__ import annotations

import psutil
from rich.text import Text
from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Static


class SysBar(Widget):
    DEFAULT_CSS = """
    SysBar {
        height: 1;
        background: $primary-darken-3;
        padding: 0 1;
    }
    """

    def compose(self) -> ComposeResult:
        yield Static("", id="sys-text")

    def on_mount(self) -> None:
        psutil.cpu_percent(interval=None)  # prime the counter; first call returns 0
        self.refresh_stats()

    def refresh_stats(self) -> None:
        cpu = psutil.cpu_percent(interval=None)
        mem = psutil.virtual_memory()

        cpu_style = "bold red" if cpu > 80 else ("bold yellow" if cpu > 50 else "bold green")
        ram_style = "bold red" if mem.percent > 85 else ("bold yellow" if mem.percent > 65 else "bold green")

        t = Text()
        t.append("  CPU ", style="dim")
        t.append(f"{cpu:5.1f}%", style=cpu_style)
        t.append("   RAM ", style="dim")
        t.append(f"{mem.percent:5.1f}%", style=ram_style)
        t.append(
            f"  ({mem.used / 1024**3:.1f} / {mem.total / 1024**3:.1f} GB)",
            style="dim",
        )

        self.query_one(Static).update(t)
