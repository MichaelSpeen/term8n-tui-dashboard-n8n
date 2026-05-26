from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

import httpx

from .config import Config


@dataclass
class NodeRun:
    name: str
    start_time_ms: int
    execution_time_ms: int
    output_items: int
    error: Optional[str] = None
    output_data: list[dict] = field(default_factory=list)  # json of each output item


@dataclass
class WorkflowNode:
    id: str
    name: str
    node_type: str
    position: tuple[int, int]


@dataclass
class WorkflowDef:
    id: str
    name: str
    active: bool
    nodes: list[WorkflowNode]
    connections: dict  # {node_name: {main: [[{node, type, index}]]}}


@dataclass
class Execution:
    id: str
    workflow_id: str
    workflow_name: str
    status: str   # success | error | running | waiting | new
    mode: str     # webhook | trigger | manual | schedule | internal | retry
    started_at: Optional[datetime]
    stopped_at: Optional[datetime]
    node_runs: list[NodeRun] = field(default_factory=list)

    @property
    def duration_seconds(self) -> Optional[float]:
        if not self.started_at:
            return None
        end = self.stopped_at or datetime.now(timezone.utc)
        return (end - self.started_at).total_seconds()

    @property
    def age_seconds(self) -> Optional[float]:
        if not self.started_at:
            return None
        return (datetime.now(timezone.utc) - self.started_at).total_seconds()


@dataclass
class Workflow:
    id: str
    name: str
    active: bool


class N8NClient:
    def __init__(self, config: Config) -> None:
        self._config = config
        self._client: Optional[httpx.AsyncClient] = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            headers: dict[str, str] = {}
            if self._config.api_key:
                headers["X-N8N-API-KEY"] = self._config.api_key
            self._client = httpx.AsyncClient(
                base_url=self._config.base_url,
                headers=headers,
                timeout=8.0,
            )
        return self._client

    async def check_connection(self) -> bool:
        try:
            resp = await self._get_client().get("/healthz")
            return resp.status_code < 400
        except Exception:
            return False

    async def get_workflows(self) -> list[Workflow]:
        resp = await self._get_client().get("/api/v1/workflows", params={"limit": 250})
        resp.raise_for_status()
        return [
            Workflow(id=str(w["id"]), name=w["name"], active=w.get("active", False))
            for w in resp.json().get("data", [])
        ]

    async def get_workflow_detail(self, workflow_id: str) -> WorkflowDef:
        resp = await self._get_client().get(f"/api/v1/workflows/{workflow_id}")
        resp.raise_for_status()
        data = resp.json()
        nodes = [
            WorkflowNode(
                id=n.get("id", ""),
                name=n.get("name", ""),
                node_type=n.get("type", ""),
                position=(int(n["position"][0]), int(n["position"][1])),
            )
            for n in data.get("nodes", [])
            if n.get("position")
        ]
        return WorkflowDef(
            id=str(data["id"]),
            name=data.get("name", "Unknown"),
            active=data.get("active", False),
            nodes=nodes,
            connections=data.get("connections", {}),
        )

    async def get_executions(
        self,
        workflow_id: Optional[str] = None,
        limit: int = 50,
    ) -> list[Execution]:
        params: dict = {"limit": limit, "includeData": "false"}
        if workflow_id:
            params["workflowId"] = workflow_id
        resp = await self._get_client().get("/api/v1/executions", params=params)
        resp.raise_for_status()
        return [self._parse_execution(e) for e in resp.json().get("data", [])]

    async def get_execution_detail(self, execution_id: str) -> Execution:
        resp = await self._get_client().get(
            f"/api/v1/executions/{execution_id}",
            params={"includeData": "true"},
        )
        resp.raise_for_status()
        return self._parse_execution(resp.json(), include_data=True)

    def _parse_execution(self, e: dict, include_data: bool = False) -> Execution:
        started_at = _parse_dt(e.get("startedAt"))
        stopped_at = _parse_dt(e.get("stoppedAt"))
        workflow_name = (
            e.get("workflowData", {}).get("name")
            or e.get("workflowName")
            or f"wf:{e.get('workflowId', '?')}"
        )

        node_runs: list[NodeRun] = []
        if include_data:
            exec_data = e.get("data") or {}
            run_data: dict = (
                exec_data.get("resultData", {}).get("runData", {})
                or exec_data.get("runData", {})
            )
            for node_name, runs in run_data.items():
                for run in runs:
                    branches = (run.get("data") or {}).get("main") or []
                    items = sum(len(b) for b in branches if b)
                    first_branch = next((b for b in branches if b), [])
                    output_data = [
                        item["json"] for item in first_branch
                        if isinstance(item, dict) and "json" in item
                    ]
                    err = run.get("error")
                    err_msg = err.get("message") if isinstance(err, dict) else None
                    node_runs.append(
                        NodeRun(
                            name=node_name,
                            start_time_ms=run.get("startTime", 0),
                            execution_time_ms=run.get("executionTime", 0),
                            output_items=items,
                            error=err_msg,
                            output_data=output_data,
                        )
                    )
            node_runs.sort(key=lambda n: n.start_time_ms)

        return Execution(
            id=str(e["id"]),
            workflow_id=str(e.get("workflowId", "")),
            workflow_name=workflow_name,
            status=e.get("status", "unknown"),
            mode=e.get("mode", "unknown"),
            started_at=started_at,
            stopped_at=stopped_at,
            node_runs=node_runs,
        )

    async def aclose(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()


def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None
