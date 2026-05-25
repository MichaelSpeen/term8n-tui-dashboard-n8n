from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass
class Config:
    base_url: str
    api_key: str
    poll_interval: float
    max_executions: int

    @classmethod
    def from_env(cls) -> Config:
        return cls(
            base_url=os.getenv("N8N_BASE_URL", "http://localhost:5678").rstrip("/"),
            api_key=os.getenv("N8N_API_KEY", ""),
            poll_interval=float(os.getenv("N8N_POLL_INTERVAL", "3.0")),
            max_executions=int(os.getenv("N8N_MAX_EXECUTIONS", "50")),
        )
