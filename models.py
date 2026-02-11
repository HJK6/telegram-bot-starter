"""
Data models for agents, messages, and logs.
"""

from __future__ import annotations
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Optional
import json
import uuid


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _uuid() -> str:
    return uuid.uuid4().hex[:12]


@dataclass
class Agent:
    agent_id: str = field(default_factory=_uuid)
    title: str = ""
    goal: str = ""
    status: str = "idle"  # idle, busy, stopped, failed
    created_at: str = field(default_factory=_now)
    last_heartbeat: str = field(default_factory=_now)
    current_task: str = ""
    metrics: dict = field(default_factory=dict)
    conversation_history: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["metrics"] = json.dumps(d["metrics"])
        d["conversation_history"] = json.dumps(d["conversation_history"])
        return d

    @classmethod
    def from_row(cls, row: dict) -> Agent:
        row = dict(row)
        row["metrics"] = json.loads(row.get("metrics") or "{}")
        row["conversation_history"] = json.loads(row.get("conversation_history") or "[]")
        return cls(**row)

    @property
    def short_id(self) -> str:
        return self.agent_id[:8]

    @property
    def uptime(self) -> str:
        created = datetime.fromisoformat(self.created_at)
        delta = datetime.now(timezone.utc) - created
        hours, rem = divmod(int(delta.total_seconds()), 3600)
        minutes, _ = divmod(rem, 60)
        if hours > 24:
            return f"{hours // 24}d {hours % 24}h"
        return f"{hours}h {minutes}m"


@dataclass
class LogEntry:
    log_id: str = field(default_factory=_uuid)
    agent_id: str = ""
    level: str = "info"
    message: str = ""
    timestamp: str = field(default_factory=_now)
    metadata: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_row(cls, row: dict) -> LogEntry:
        return cls(**dict(row))


@dataclass
class ChatMessage:
    message_id: str = field(default_factory=_uuid)
    agent_id: str = ""
    direction: str = "inbound"  # inbound (user→agent) or outbound (agent→user)
    sender: str = ""
    text: str = ""
    timestamp: str = field(default_factory=_now)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_row(cls, row: dict) -> ChatMessage:
        return cls(**dict(row))
