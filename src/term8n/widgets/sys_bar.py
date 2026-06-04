from __future__ import annotations

from typing import Optional

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

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        # Set by app after each credential check
        self._api_key_ok: Optional[bool] = None      # None = not configured
        self._credentials_ok: Optional[bool] = None  # None = not configured

    def compose(self) -> ComposeResult:
        yield Static("", id="sys-text")

    def on_mount(self) -> None:
        psutil.cpu_percent(interval=None)  # prime the counter; first call returns 0
        self.refresh_stats()

    def set_connection_status(
        self,
        api_key_ok: Optional[bool],
        credentials_ok: Optional[bool],
    ) -> None:
        self._api_key_ok = api_key_ok
        self._credentials_ok = credentials_ok
        self.refresh_stats()

    def refresh_stats(self) -> None:
        cpu = psutil.cpu_percent(interval=None)
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage("/")

        cpu_style = "bold red" if cpu > 80 else ("bold yellow" if cpu > 50 else "bold green")
        ram_style = "bold red" if mem.percent > 85 else ("bold yellow" if mem.percent > 65 else "bold green")
        disk_free_gb = disk.free / 1024 ** 3
        disk_style = "bold red" if disk_free_gb < 2 else ("bold yellow" if disk_free_gb < 10 else "dim")

        t = Text()
        t.append("  CPU ", style="dim")
        t.append(f"{cpu:5.1f}%", style=cpu_style)
        t.append("   RAM ", style="dim")
        t.append(f"{mem.percent:5.1f}%", style=ram_style)
        t.append(f"  ({mem.used / 1024**3:.1f} / {mem.total / 1024**3:.1f} GB)", style="dim")
        t.append("   Disk free ", style="dim")
        t.append(f"{disk_free_gb:.0f} GB", style=disk_style)

        # API key status
        if self._api_key_ok is True:
            t.append("   API key ", style="dim")
            t.append("OK", style="bold green")
        elif self._api_key_ok is False:
            t.append("   API key ", style="dim")
            t.append("ERROR", style="bold red")

        # Push credentials status
        if self._credentials_ok is True:
            t.append("   credentials ", style="dim")
            t.append("OK", style="bold green")
        elif self._credentials_ok is False:
            t.append("   credentials ", style="dim")
            t.append("ERROR", style="bold red")

        self.query_one(Static).update(t)
