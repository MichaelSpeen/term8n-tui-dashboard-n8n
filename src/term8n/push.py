from __future__ import annotations

import asyncio
import json
import uuid
from dataclasses import dataclass, field
from typing import Callable, Optional

import httpx


@dataclass
class LiveExecution:
    active_node: Optional[str] = None
    # Completed nodes in chronological order: (name, exec_ms, output_items, error_msg)
    completed: list[tuple[str, int, int, Optional[str]]] = field(default_factory=list)


UpdateCallback = Callable[[str], None]  # called with execution_id on every state change


class PushClient:
    """Subscribes to n8n's SSE push endpoint for real-time node execution events.

    n8n's push endpoint uses cookie auth, not the API key. Requires N8N_EMAIL
    and N8N_PASSWORD to be set. Falls back gracefully if credentials are missing
    or login fails — polling continues as normal.
    """

    def __init__(self, base_url: str, email: str, password: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._email = email
        self._password = password
        self._push_ref = str(uuid.uuid4())
        self._live: dict[str, LiveExecution] = {}
        self._callbacks: list[UpdateCallback] = []
        self._task: Optional[asyncio.Task] = None
        self.connected = False
        self.available = bool(email and password)

    # ── public API ─────────────────────────────────────────────────────────────

    def on_update(self, callback: UpdateCallback) -> None:
        self._callbacks.append(callback)

    def get_live(self, execution_id: str) -> Optional[LiveExecution]:
        return self._live.get(execution_id)

    def start(self) -> None:
        if not self.available:
            return
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._run_forever())

    def stop(self) -> None:
        if self._task:
            self._task.cancel()
            self._task = None
        self.connected = False

    # ── internal ───────────────────────────────────────────────────────────────

    async def _run_forever(self) -> None:
        while True:
            try:
                await self._connect_and_stream()
            except asyncio.CancelledError:
                return
            except Exception:
                pass
            self.connected = False
            await asyncio.sleep(10)

    async def _connect_and_stream(self) -> None:
        async with httpx.AsyncClient(
            base_url=self._base_url,
            timeout=httpx.Timeout(connect=10.0, read=None, write=10.0, pool=10.0),
            follow_redirects=True,
        ) as client:
            login = await client.post(
                "/rest/login",
                json={"emailOrLdapLoginId": self._email, "password": self._password},
            )
            if login.status_code == 401:
                self.available = False  # wrong credentials — stop retrying
                return
            if not login.is_success:
                return

            async with client.stream(
                "GET", f"/rest/push?pushRef={self._push_ref}"
            ) as response:
                if response.status_code != 200:
                    return
                self.connected = True
                async for line in response.aiter_lines():
                    if line.startswith("data:"):
                        raw = line[5:].strip()
                        if raw:
                            try:
                                self._handle(json.loads(raw))
                            except Exception:
                                pass

    def _handle(self, event: dict) -> None:
        etype = event.get("type", "")
        data = event.get("data", {}) or {}

        if etype == "nodeExecuteBefore":
            eid = str(data.get("executionId", ""))
            node = data.get("nodeName", "")
            if eid and node:
                self._live.setdefault(eid, LiveExecution()).active_node = node
                self._fire(eid)

        elif etype == "nodeExecuteAfter":
            eid = str(data.get("executionId", ""))
            node = data.get("nodeName", "")
            if eid and node:
                live = self._live.setdefault(eid, LiveExecution())
                if live.active_node == node:
                    live.active_node = None
                task_data = data.get("data") or {}
                exec_ms = task_data.get("executionTime", 0)
                branches = ((task_data.get("data") or {}).get("main") or [])
                items = sum(len(b) for b in branches if b)
                err = task_data.get("error")
                err_msg = err.get("message") if isinstance(err, dict) else None
                live.completed.append((node, exec_ms, items, err_msg))
                self._fire(eid)

        elif etype in ("executionFinished", "workflowExecuteAfter"):
            eid = str(
                data.get("executionId", "")
                or (data.get("data") or {}).get("executionId", "")
            )
            if eid and eid in self._live:
                self._live[eid].active_node = None
                self._fire(eid)

    def _fire(self, execution_id: str) -> None:
        for cb in self._callbacks:
            cb(execution_id)
