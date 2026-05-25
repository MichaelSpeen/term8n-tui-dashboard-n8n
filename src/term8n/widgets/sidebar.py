from __future__ import annotations

from textual.app import ComposeResult
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Label, ListItem, ListView

from ..api import Workflow


class WorkflowSidebar(Widget):
    DEFAULT_CSS = """
    WorkflowSidebar {
        width: 26;
        border-right: round $primary-darken-1;
    }
    WorkflowSidebar > .sidebar-title {
        width: 100%;
        height: 1;
        background: $primary-darken-3;
        color: $text;
        padding: 0 1;
        text-style: bold;
    }
    WorkflowSidebar ListView {
        height: 1fr;
        background: transparent;
        border: none;
    }
    """

    class FilterChanged(Message):
        def __init__(self, workflow_id: str | None) -> None:
            super().__init__()
            self.workflow_id = workflow_id

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._workflows: list[Workflow] = []
        self._counts: dict[str, int] = {}

    def compose(self) -> ComposeResult:
        yield Label("Workflows", classes="sidebar-title")
        yield ListView(ListItem(Label("All (0)"), id="item_all"))

    async def set_workflows(self, workflows: list[Workflow]) -> None:
        self._workflows = workflows
        await self._rebuild_list()

    def update_counts(self, counts: dict[str, int]) -> None:
        self._counts = counts
        total = sum(counts.values())
        try:
            self.query_one("#item_all Label", Label).update(f"All ({total})")
        except Exception:
            pass
        for wf in self._workflows:
            try:
                label = self.query_one(f"#item_{wf.id} Label", Label)
                marker = "● " if wf.active else "  "
                label.update(f"{marker}{wf.name[:18]} ({counts.get(wf.id, 0)})")
            except Exception:
                pass

    async def _rebuild_list(self) -> None:
        lv = self.query_one(ListView)
        await lv.clear()
        total = sum(self._counts.values())
        await lv.mount(ListItem(Label(f"All ({total})"), id="item_all"))
        for wf in self._workflows:
            marker = "● " if wf.active else "  "
            count = self._counts.get(wf.id, 0)
            await lv.mount(
                ListItem(
                    Label(f"{marker}{wf.name[:18]} ({count})"),
                    id=f"item_{wf.id}",
                )
            )

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        item_id = event.item.id or ""
        if item_id == "item_all":
            self.post_message(WorkflowSidebar.FilterChanged(None))
        elif item_id.startswith("item_"):
            self.post_message(WorkflowSidebar.FilterChanged(item_id[5:]))
