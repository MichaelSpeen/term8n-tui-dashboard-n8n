from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import ScrollableContainer
from textual.screen import ModalScreen
from textual.widgets import Label, Static

from ..api import WorkflowDef, WorkflowNode

_CANVAS_W = 180
_CANVAS_H = 60
_BOX_H = 3


# ── public screen ──────────────────────────────────────────────────────────────

class WorkflowDiagramScreen(ModalScreen):
    BINDINGS = [
        Binding("escape", "dismiss", "Close"),
        Binding("q",      "dismiss", "Close"),
    ]

    DEFAULT_CSS = """
    WorkflowDiagramScreen {
        align: center middle;
    }
    #diag-wrap {
        width: 95%;
        height: 90%;
        border: round $primary;
        background: $surface;
        layout: vertical;
    }
    #diag-title {
        height: 1;
        background: $primary-darken-3;
        padding: 0 2;
        width: 100%;
    }
    #diag-legend {
        height: 1;
        background: $primary-darken-2;
        padding: 0 2;
        width: 100%;
    }
    #diag-scroll {
        height: 1fr;
    }
    #diag-footer {
        height: 1;
        background: $primary-darken-3;
        padding: 0 2;
        color: $text-muted;
        width: 100%;
    }
    """

    def __init__(self, workflow: WorkflowDef) -> None:
        super().__init__()
        self._workflow = workflow

    def compose(self) -> ComposeResult:
        wf = self._workflow
        active_marker = "● active" if wf.active else "○ inactive"

        title_text = Text()
        title_text.append(f" {wf.name}", style="bold white")
        title_text.append(f"  ·  {len(wf.nodes)} nodes  ·  ", style="dim")
        title_text.append(active_marker, style="bold green" if wf.active else "dim")

        legend = Text()
        legend.append("  ")
        for label, style in (
            ("trigger", "bold blue"),
            ("  http", "bold cyan"),
            ("  code", "bold yellow"),
            ("  logic", "bold magenta"),
            ("  notify", "bold green"),
            ("  ai", "bold bright_magenta"),
        ):
            legend.append("■ ", style=style)
            legend.append(label, style="dim")

        content = _build_diagram(wf)

        with Static(id="diag-wrap"):
            yield Label(title_text, id="diag-title")
            yield Label(legend, id="diag-legend")
            with ScrollableContainer(id="diag-scroll"):
                yield Static(content, id="diag-content")
            yield Label(" [Esc / q] close   arrow keys: scroll", id="diag-footer")

    def on_click(self) -> None:
        self.dismiss()


# ── diagram renderer ───────────────────────────────────────────────────────────

def _build_diagram(wf: WorkflowDef) -> Text:
    nodes = wf.nodes
    if not nodes:
        return Text("No nodes in this workflow.", style="dim")

    xs = [n.position[0] for n in nodes]
    ys = [n.position[1] for n in nodes]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    span_x = max(max_x - min_x, 1)
    span_y = max(max_y - min_y, 1)

    pad_x, pad_y = 3, 1
    node_w = 20
    usable_w = _CANVAS_W - node_w - pad_x * 2
    usable_h = (_CANVAS_H - _BOX_H - pad_y * 2) // 2  # ÷2: terminal rows ≈ half n8n units

    def scale(x: int, y: int) -> tuple[int, int]:
        sx = int((x - min_x) / span_x * usable_w) + pad_x if span_x else pad_x
        sy = int((y - min_y) / span_y * usable_h) + pad_y if span_y else pad_y
        return sx, sy

    # ── allocate grid ──────────────────────────────────────────────────────────
    grid:   list[list[str]]              = [[" "] * _CANVAS_W for _ in range(_CANVAS_H)]
    styles: dict[tuple[int, int], str]   = {}

    boxes: dict[str, tuple[int, int, int, int]] = {}   # name → (x, y, w, h)

    # ── place node boxes ───────────────────────────────────────────────────────
    for node in nodes:
        cx, cy = scale(*node.position)
        label   = node.name[: node_w - 4]
        bw      = max(len(label) + 4, 14)
        color   = _node_color(node.node_type)

        inner   = bw - 2
        lpad    = (inner - len(label)) // 2
        rpad    = inner - len(label) - lpad

        _put(grid, styles, cx, cy,     "╭" + "─" * inner + "╮",                         color)
        _put(grid, styles, cx, cy + 1, "│" + " " * lpad + label + " " * rpad + "│",     color)
        _put(grid, styles, cx, cy + 2, "╰" + "─" * inner + "╯",                         color)

        boxes[node.name] = (cx, cy, bw, _BOX_H)

    # ── draw connections ───────────────────────────────────────────────────────
    # Pre-compute shared detour row per source: all backward arcs from the same
    # source share one horizontal run → clean left-spine, one horizontal bar.
    backward_detour: dict[str, int] = {}
    for src_name, branches in wf.connections.items():
        if src_name not in boxes:
            continue
        sx, sy, sw, _ = boxes[src_name]
        x1, y1 = sx + sw, sy + 1
        for branch in branches.get("main", []):
            for conn in branch:
                tgt = conn.get("node", "")
                if tgt not in boxes:
                    continue
                tx, ty, _, _ = boxes[tgt]
                if x1 >= tx:
                    backward_detour[src_name] = max(
                        backward_detour.get(src_name, 0),
                        ty + 1 + _BOX_H,
                    )

    for src_name, branches in wf.connections.items():
        if src_name not in boxes:
            continue
        sx, sy, sw, _ = boxes[src_name]
        x1, y1 = sx + sw, sy + 1

        for branch in branches.get("main", []):
            for conn in branch:
                tgt = conn.get("node", "")
                if tgt not in boxes:
                    continue
                tx, ty, _, _ = boxes[tgt]
                x2, y2 = tx, ty + 1
                if x1 >= x2:
                    detour = min(backward_detour[src_name], _CANVAS_H - 1)
                    _backward_arrow(grid, styles, x1, y1, x2, y2, detour)
                else:
                    _arrow(grid, styles, x1, y1, x2, y2)

    # ── convert to Rich Text ───────────────────────────────────────────────────
    result = Text()
    last_content_row = 0
    for r, row in enumerate(grid):
        if any(ch != " " for ch in row):
            last_content_row = r

    for r in range(last_content_row + 2):
        row = grid[r]
        c = 0
        while c < len(row):
            ch = row[c]
            st = styles.get((c, r), "")
            end = c + 1
            while end < len(row) and styles.get((end, r), "") == st:
                end += 1
            result.append("".join(row[c:end]), style=st)
            c = end
        result.append("\n")

    return result


# ── helpers ────────────────────────────────────────────────────────────────────

def _put(
    grid: list[list[str]],
    styles: dict[tuple[int, int], str],
    x: int,
    y: int,
    text: str,
    style: str = "",
) -> None:
    for i, ch in enumerate(text):
        xi = x + i
        if 0 <= xi < _CANVAS_W and 0 <= y < _CANVAS_H:
            grid[y][xi] = ch
            if style:
                styles[(xi, y)] = style


def _arrow(
    grid: list[list[str]],
    styles: dict[tuple[int, int], str],
    x1: int, y1: int,
    x2: int, y2: int,
) -> None:
    if x1 >= x2:
        return  # backward connections are handled separately in _build_diagram

    st = "dim"
    mid = x1 + (x2 - x1) // 2

    # horizontal leg 1
    for x in range(x1, mid):
        _put(grid, styles, x, y1, "─", st)

    # vertical leg
    if y1 != y2:
        for y in range(min(y1, y2), max(y1, y2) + 1):
            if y == y1:
                ch = "╮" if y2 > y1 else "╯"
            elif y == y2:
                ch = "╰" if y2 > y1 else "╭"
            else:
                ch = "│"
            _put(grid, styles, mid, y, ch, st)
        h2_start = mid + 1
    else:
        h2_start = mid

    # horizontal leg 2
    for x in range(h2_start, x2 - 1):
        _put(grid, styles, x, y2, "─", st)

    # arrow head
    if x2 - 1 >= x1:
        _put(grid, styles, x2 - 1, y2, "►", st)


def _backward_arrow(
    grid: list[list[str]],
    styles: dict[tuple[int, int], str],
    x1: int, y1: int,
    x2: int, y2: int,
    detour_y: int,
) -> None:
    """Route a right-to-left connection: drop to shared detour row, run left, rise to target."""
    st = "dim"
    via_x = max(x2 - 1, 0)

    # Drop down from source right edge
    _put(grid, styles, x1, y1, "╮", st)
    for y in range(y1 + 1, detour_y):
        _put(grid, styles, x1, y, "│", st)
    _put(grid, styles, x1, detour_y, "╯", st)

    # Horizontal run leftward at detour_y
    for x in range(via_x + 1, x1):
        _put(grid, styles, x, detour_y, "─", st)

    # Corner turning upward
    _put(grid, styles, via_x, detour_y, "╰", st)

    # Upward run to target row
    for y in range(y2 + 1, detour_y):
        _put(grid, styles, via_x, y, "│", st)

    # Arrowhead pointing right into target's left edge
    _put(grid, styles, via_x, y2, "►", st)


def _node_color(node_type: str) -> str:
    t = node_type.lower()
    if any(k in t for k in ("webhook", "trigger", "schedule", "cron", "interval", "poll")):
        return "bold blue"
    if any(k in t for k in ("httprequest", "http", "graphql", "rest")):
        return "bold cyan"
    if any(k in t for k in ("code", "function", "python", "execute", "script")):
        return "bold yellow"
    if any(k in t for k in (".if", "switch", "filter", "merge", "split", "router")):
        return "bold magenta"
    if any(k in t for k in ("email", "slack", "telegram", "discord", "send", "gmail", "notify")):
        return "bold green"
    if any(k in t for k in ("langchain", "agent", "openai", "llm", "chat", "ai", "embeddings")):
        return "bold bright_magenta"
    return "white"
