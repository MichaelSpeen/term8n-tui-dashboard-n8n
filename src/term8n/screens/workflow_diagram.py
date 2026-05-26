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
_TOPO_NODE_W     = 16   # max box width in topo view
_TOPO_COL_STRIDE = 20   # horizontal space per column in top-down view
_TOPO_ROW_STRIDE = 5    # vertical space per depth level in top-down view


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

        with Static(id="diag-wrap"):
            yield Label(title_text, id="diag-title")
            yield Label(legend, id="diag-legend")
            with ScrollableContainer(id="diag-scroll"):
                yield Static(_build_diagram(self._workflow), id="diag-content")
            yield Label(" [Esc / q] close   arrow keys: scroll", id="diag-footer")

    def on_click(self) -> None:
        self.dismiss()


# ── topo flow screen ───────────────────────────────────────────────────────────

class WorkflowTopoScreen(ModalScreen):
    BINDINGS = [
        Binding("escape", "dismiss", "Close"),
        Binding("q",      "dismiss", "Close"),
    ]

    DEFAULT_CSS = """
    WorkflowTopoScreen {
        align: center middle;
    }
    #topo-wrap {
        width: 95%;
        height: 90%;
        border: round $accent;
        background: $surface;
        layout: vertical;
    }
    #topo-title {
        height: 1;
        background: $accent-darken-3;
        padding: 0 2;
        width: 100%;
    }
    #topo-legend {
        height: 1;
        background: $accent-darken-2;
        padding: 0 2;
        width: 100%;
    }
    #topo-scroll {
        height: 1fr;
    }
    #topo-footer {
        height: 1;
        background: $accent-darken-3;
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
        title_text.append("  ·  flow", style="bold yellow")

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

        with Static(id="topo-wrap"):
            yield Label(title_text, id="topo-title")
            yield Label(legend, id="topo-legend")
            with ScrollableContainer(id="topo-scroll"):
                yield Static(_build_diagram_topo(self._workflow), id="topo-content")
            yield Label(" [Esc / q] close   arrow keys: scroll", id="topo-footer")

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
    _h = len(grid)
    _w = len(grid[0]) if _h else 0
    for i, ch in enumerate(text):
        xi = x + i
        if 0 <= xi < _w and 0 <= y < _h:
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


def _arrow_tb(
    grid: list[list[str]],
    styles: dict[tuple[int, int], str],
    x1: int, y1: int,
    x2: int, y2: int,
) -> None:
    """Top-to-bottom arrow: exits source bottom-centre, enters target top-centre."""
    if y1 >= y2:
        return
    st = "dim"
    mid_y = y1 + (y2 - y1) // 2

    if x1 == x2:
        for y in range(y1, y2):
            _put(grid, styles, x1, y, "│", st)
    else:
        for y in range(y1, mid_y):
            _put(grid, styles, x1, y, "│", st)
        if x2 > x1:
            _put(grid, styles, x1, mid_y, "╰", st)
            for x in range(x1 + 1, x2):
                _put(grid, styles, x, mid_y, "─", st)
            _put(grid, styles, x2, mid_y, "╮", st)
        else:
            _put(grid, styles, x1, mid_y, "╯", st)
            for x in range(x2 + 1, x1):
                _put(grid, styles, x, mid_y, "─", st)
            _put(grid, styles, x2, mid_y, "╭", st)
        for y in range(mid_y + 1, y2):
            _put(grid, styles, x2, y, "│", st)
    _put(grid, styles, x2, y2, "▼", st)


def _build_diagram_topo(wf: WorkflowDef) -> Text:
    """Top-down layout: depth via longest-path BFS, columns by original canvas X."""
    nodes = wf.nodes
    if not nodes:
        return Text("No nodes in this workflow.", style="dim")

    node_names = {n.name for n in nodes}
    node_by_name = {n.name: n for n in nodes}

    # Build forward adjacency (deduplicated)
    forward: dict[str, list[str]] = {n.name: [] for n in nodes}
    for src, branches in wf.connections.items():
        if src not in node_names:
            continue
        for branch in branches.get("main", []):
            for conn in branch:
                tgt = conn.get("node", "")
                if tgt in node_names and tgt not in forward[src]:
                    forward[src].append(tgt)

    # Longest-path depth (Bellman-Ford, handles cycles safely)
    depth: dict[str, int] = {n.name: 0 for n in nodes}
    for _ in range(len(nodes)):
        updated = False
        for src, targets in forward.items():
            for tgt in targets:
                if depth[src] + 1 > depth[tgt]:
                    depth[tgt] = depth[src] + 1
                    updated = True
        if not updated:
            break

    # Group by depth; within each level sort by original canvas X position
    depth_groups: dict[int, list[str]] = {}
    for n in nodes:
        depth_groups.setdefault(depth[n.name], []).append(n.name)
    for d in depth_groups:
        depth_groups[d].sort(key=lambda name: node_by_name[name].position[0])

    # Assign canvas positions
    pad_x, pad_y = 2, 1
    pos: dict[str, tuple[int, int]] = {}
    for d, names in depth_groups.items():
        for col, name in enumerate(names):
            pos[name] = (pad_x + col * _TOPO_COL_STRIDE, pad_y + d * _TOPO_ROW_STRIDE)

    # Dynamic canvas
    canvas_h = max(cy + _BOX_H + 3 for _, cy in pos.values())
    canvas_w = max(cx + _TOPO_NODE_W + 2 for cx, _ in pos.values())
    grid: list[list[str]] = [[" "] * canvas_w for _ in range(canvas_h)]
    styles: dict[tuple[int, int], str] = {}
    boxes: dict[str, tuple[int, int, int, int]] = {}

    # Draw boxes
    for n in nodes:
        cx, cy = pos[n.name]
        label = n.name[:_TOPO_NODE_W - 4]
        bw = max(len(label) + 4, 10)
        color = _node_color(n.node_type)
        inner = bw - 2
        lpad = (inner - len(label)) // 2
        rpad = inner - len(label) - lpad
        _put(grid, styles, cx, cy,     "╭" + "─" * inner + "╮", color)
        _put(grid, styles, cx, cy + 1, "│" + " " * lpad + label + " " * rpad + "│", color)
        _put(grid, styles, cx, cy + 2, "╰" + "─" * inner + "╯", color)
        boxes[n.name] = (cx, cy, bw, _BOX_H)

    # Draw top-to-bottom connections (forward edges only)
    for src, branches in wf.connections.items():
        if src not in boxes:
            continue
        sx, sy, sw, _ = boxes[src]
        x1 = sx + sw // 2
        y1 = sy + _BOX_H          # just below source bottom border

        for branch in branches.get("main", []):
            for conn in branch:
                tgt = conn.get("node", "")
                if tgt not in boxes:
                    continue
                tx, ty, tw, _ = boxes[tgt]
                x2 = tx + tw // 2
                y2 = ty - 1        # just above target top border
                if y2 <= y1:
                    continue       # same depth or back-edge — skip
                _arrow_tb(grid, styles, x1, y1, x2, y2)

    # Convert grid to Rich Text
    result = Text()
    last_row = max((r for r, row in enumerate(grid) if any(ch != " " for ch in row)), default=0)
    for r in range(last_row + 2):
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
