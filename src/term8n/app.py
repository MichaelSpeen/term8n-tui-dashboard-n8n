from __future__ import annotations

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import Footer, Header

from .api import Execution, N8NClient, Workflow, WorkflowDef
from .push import PushClient
from .config import Config
from .screens.workflow_diagram import WorkflowDiagramScreen, WorkflowTopoScreen
from .widgets.exec_detail import ExecutionDetail
from .widgets.exec_table import ExecutionTable
from .widgets.node_modal import NodeDetailModal
from .widgets.sidebar import WorkflowSidebar
from .widgets.stats_bar import StatsBar
from .widgets.sys_bar import SysBar


class Term8nApp(App):
    TITLE = "term8n"
    SUB_TITLE = "n8n execution dashboard"

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("r", "refresh", "Refresh"),
        Binding("w", "workflow_diagram", "Diagram"),
        Binding("t", "topo_diagram", "Flow"),
        Binding("escape", "clear_detail", "Clear detail", show=False),
    ]

    CSS = """
    Screen { background: $background; }
    #main-container { layout: horizontal; height: 1fr; }
    #right-pane { layout: vertical; width: 1fr; }
    """

    def __init__(self) -> None:
        super().__init__()
        self.config = Config.from_env()
        self.client = N8NClient(self.config)
        self.push = PushClient(self.config.base_url, self.config.push_email, self.config.push_password)
        self._filter_workflow_id: str | None = None
        self._selected_execution_id: str | None = None
        self._executions: list[Execution] = []
        self._workflows: list[Workflow] = []
        self._wf_cache: dict[str, WorkflowDef] = {}
        self._connected = False

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="main-container"):
            yield WorkflowSidebar(id="sidebar")
            with Vertical(id="right-pane"):
                yield StatsBar(id="stats-bar")
                yield ExecutionTable(id="exec-table")
                yield ExecutionDetail(id="exec-detail")
        yield SysBar(id="sys-bar")
        yield Footer()

    def on_mount(self) -> None:
        if not self.config.api_key:
            self.notify(
                "N8N_API_KEY not set — copy .env.example to .env and add your key.\n"
                "Create one at: n8n Settings > n8n API > Create API key",
                severity="warning",
                timeout=15,
            )
        self.call_after_refresh(self._initial_load)
        self.set_interval(self.config.poll_interval, self._poll_executions)
        self.set_interval(1.0, self._fast_refresh_running)
        self.set_interval(2.0, self._refresh_sys_bar)
        self.push.on_update(self._on_push_update)
        self.push.start()

    async def _initial_load(self) -> None:
        try:
            self._workflows = await self.client.get_workflows()
            await self.query_one(WorkflowSidebar).set_workflows(self._workflows)
        except Exception:
            pass
        await self._poll_executions()

    async def _poll_executions(self) -> None:
        try:
            executions = await self.client.get_executions(
                workflow_id=self._filter_workflow_id,
                limit=self.config.max_executions,
            )
            self._executions = executions
            self._connected = True
        except Exception as exc:
            self._connected = False
            self._update_subtitle()
            return

        counts: dict[str, int] = {}
        for e in self._executions:
            counts[e.workflow_id] = counts.get(e.workflow_id, 0) + 1

        self.query_one(WorkflowSidebar).update_counts(counts)
        self.query_one(StatsBar).update_stats(self._executions)
        self.query_one(ExecutionTable).update_executions(self._executions)
        self._update_subtitle()

        if self._selected_execution_id:
            await self._refresh_detail(self._selected_execution_id)

    def _update_subtitle(self) -> None:
        if not self._connected:
            self.sub_title = "✗ disconnected  —  check N8N_BASE_URL and N8N_API_KEY"
            return
        running = sum(1 for e in self._executions if e.status == "running")
        errors  = sum(1 for e in self._executions if e.status == "error")
        parts = ["● connected"]
        if running:
            parts.append(f"{running} running")
        if errors:
            parts.append(f"{errors} errors")
        self.sub_title = "  ·  ".join(parts)

    async def on_execution_table_execution_selected(
        self, event: ExecutionTable.ExecutionSelected
    ) -> None:
        self._selected_execution_id = event.execution_id
        await self._refresh_detail(event.execution_id)

    async def _refresh_detail(self, execution_id: str) -> None:
        try:
            detail = await self.client.get_execution_detail(execution_id)
            wf_node_names: list[str] = []
            if detail.status in ("running", "waiting", "new") and not detail.node_runs:
                wf_id = detail.workflow_id
                if wf_id and wf_id not in self._wf_cache:
                    try:
                        self._wf_cache[wf_id] = await self.client.get_workflow_detail(wf_id)
                    except Exception:
                        pass
                cached = self._wf_cache.get(wf_id or "")
                if cached:
                    sorted_nodes = sorted(cached.nodes, key=lambda n: n.position[0])
                    wf_node_names = [n.name for n in sorted_nodes]
            live = self.push.get_live(execution_id)
            self.query_one(ExecutionDetail).show_execution(detail, wf_node_names, live)
        except Exception as exc:
            self.notify(f"Could not load execution detail: {exc}", severity="error")

    def _refresh_sys_bar(self) -> None:
        api_key_ok: bool | None = self._connected if self.config.api_key else None

        creds_ok: bool | None = None
        if self.config.push_email and self.config.push_password:
            if self.push.login_failed:
                creds_ok = False       # 401 — wrong credentials
            elif self.push.connected:
                creds_ok = True        # WebSocket live
            # else: still starting / reconnecting — show nothing yet

        self.query_one(SysBar).set_connection_status(api_key_ok, creds_ok)

    def _on_push_update(self, execution_id: str) -> None:
        if execution_id != self._selected_execution_id:
            return
        live = self.push.get_live(execution_id)
        self.query_one(ExecutionDetail).update_live(live)

    def on_workflow_sidebar_filter_changed(
        self, event: WorkflowSidebar.FilterChanged
    ) -> None:
        self._filter_workflow_id = event.workflow_id
        self.call_after_refresh(self._poll_executions)

    async def _fast_refresh_running(self) -> None:
        if not self._selected_execution_id:
            return
        selected = next(
            (e for e in self._executions if e.id == self._selected_execution_id), None
        )
        if selected and selected.status in ("running", "waiting", "new"):
            await self._refresh_detail(self._selected_execution_id)

    async def action_refresh(self) -> None:
        await self._poll_executions()

    async def action_workflow_diagram(self) -> None:
        wf_id = self._filter_workflow_id
        if not wf_id and self._selected_execution_id:
            for e in self._executions:
                if e.id == self._selected_execution_id:
                    wf_id = e.workflow_id
                    break
        if not wf_id:
            self.notify("Select a workflow in the sidebar first", severity="warning")
            return
        try:
            workflow = await self.client.get_workflow_detail(wf_id)
            await self.push_screen(WorkflowDiagramScreen(workflow))
        except Exception as exc:
            self.notify(f"Could not load workflow: {exc}", severity="error")

    async def action_topo_diagram(self) -> None:
        wf_id = self._filter_workflow_id
        if not wf_id and self._selected_execution_id:
            for e in self._executions:
                if e.id == self._selected_execution_id:
                    wf_id = e.workflow_id
                    break
        if not wf_id:
            self.notify("Select a workflow in the sidebar first", severity="warning")
            return
        try:
            workflow = await self.client.get_workflow_detail(wf_id)
            await self.push_screen(WorkflowTopoScreen(workflow))
        except Exception as exc:
            self.notify(f"Could not load workflow: {exc}", severity="error")

    async def on_execution_detail_node_selected(
        self, event: ExecutionDetail.NodeSelected
    ) -> None:
        await self.push_screen(NodeDetailModal(event.node))

    def action_clear_detail(self) -> None:
        self._selected_execution_id = None
        self.query_one(ExecutionDetail).clear_detail()

    async def on_unmount(self) -> None:
        self.push.stop()
        await self.client.aclose()
