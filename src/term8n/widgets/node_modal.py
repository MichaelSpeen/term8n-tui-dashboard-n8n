from __future__ import annotations

import json

from rich.syntax import Syntax
from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Label, Static

from ..api import NodeRun

_STATUS_STYLE = {
    "ok":    ("✓", "bold green"),
    "error": ("✗", "bold red"),
    "none":  ("—", "dim"),
}


class NodeDetailModal(ModalScreen):
    BINDINGS = [
        Binding("escape", "dismiss", "Close"),
        Binding("q", "dismiss", "Close"),
    ]

    DEFAULT_CSS = """
    NodeDetailModal {
        align: center middle;
    }
    #modal-outer {
        width: 80;
        height: 36;
        max-width: 90%;
        max-height: 80%;
        border: round $primary;
        background: $surface;
        padding: 0;
    }
    #modal-header {
        height: 3;
        background: $primary-darken-3;
        padding: 1 2;
        width: 100%;
    }
    #modal-meta {
        height: 1;
        padding: 0 2;
        background: $primary-darken-2;
        width: 100%;
    }
    #modal-body {
        height: 1fr;
        padding: 1 2;
    }
    #modal-footer {
        height: 1;
        padding: 0 2;
        background: $primary-darken-3;
        width: 100%;
        color: $text-muted;
    }
    """

    def __init__(self, node: NodeRun) -> None:
        super().__init__()
        self._node = node

    def compose(self) -> ComposeResult:
        node = self._node

        status_icon = "✗" if node.error else "✓"
        status_style = "bold red" if node.error else "bold green"

        header = Text()
        header.append(f" {status_icon} ", style=status_style)
        header.append(node.name, style="bold white")

        meta = Text()
        meta.append(f"  {node.execution_time_ms}ms", style="dim")
        meta.append("  ·  ", style="dim")
        meta.append(f"{node.output_items} items out", style="dim")
        if node.error:
            meta.append("  ·  ", style="dim")
            meta.append(node.error, style="red")

        with Static(id="modal-outer"):
            yield Label(header, id="modal-header")
            yield Label(meta, id="modal-meta")
            with VerticalScroll(id="modal-body"):
                yield Static(_render_output(node), id="output-content")
            yield Label(" [Esc] close", id="modal-footer")

    def on_click(self) -> None:
        self.dismiss()


def _render_output(node: NodeRun) -> Syntax | Text:
    if node.error:
        t = Text()
        t.append("Error\n\n", style="bold red")
        t.append(node.error, style="red")
        return t

    if not node.output_data:
        return Text("No output data", style="dim")

    payload = node.output_data if len(node.output_data) > 1 else node.output_data[0]
    try:
        raw = json.dumps(payload, indent=2, ensure_ascii=False, default=str)
    except Exception:
        raw = str(payload)

    return Syntax(raw, "json", theme="monokai", word_wrap=True)
