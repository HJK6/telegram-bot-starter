"""
SQLite persistence layer — agents, logs, chat messages.

Zero external dependencies. Swap this for Postgres/DynamoDB/etc.
by implementing the same interface.
"""

import sqlite3
from contextlib import contextmanager
from typing import Optional

from config import DB_PATH
from models import Agent, LogEntry, ChatMessage


def _init_db(conn: sqlite3.Connection):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS agents (
            agent_id TEXT PRIMARY KEY,
            title TEXT,
            goal TEXT,
            status TEXT DEFAULT 'idle',
            created_at TEXT,
            last_heartbeat TEXT,
            current_task TEXT DEFAULT '',
            metrics TEXT DEFAULT '{}',
            conversation_history TEXT DEFAULT '[]'
        );

        CREATE TABLE IF NOT EXISTS logs (
            log_id TEXT PRIMARY KEY,
            agent_id TEXT,
            level TEXT DEFAULT 'info',
            message TEXT,
            timestamp TEXT,
            metadata TEXT DEFAULT ''
        );
        CREATE INDEX IF NOT EXISTS idx_logs_agent ON logs(agent_id, timestamp DESC);

        CREATE TABLE IF NOT EXISTS chat (
            message_id TEXT PRIMARY KEY,
            agent_id TEXT,
            direction TEXT,
            sender TEXT,
            text TEXT,
            timestamp TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_chat_agent ON chat(agent_id, timestamp DESC);
    """)


# Module-level connection (single-threaded bot)
_conn: Optional[sqlite3.Connection] = None


def get_conn() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        _conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _init_db(_conn)
    return _conn


# ── Agents ──────────────────────────────────────────────────────

def save_agent(agent: Agent):
    conn = get_conn()
    d = agent.to_dict()
    conn.execute("""
        INSERT OR REPLACE INTO agents
        (agent_id, title, goal, status, created_at, last_heartbeat,
         current_task, metrics, conversation_history)
        VALUES (:agent_id, :title, :goal, :status, :created_at,
                :last_heartbeat, :current_task, :metrics, :conversation_history)
    """, d)
    conn.commit()


def get_agent(agent_id: str) -> Optional[Agent]:
    conn = get_conn()
    row = conn.execute("SELECT * FROM agents WHERE agent_id = ?", (agent_id,)).fetchone()
    return Agent.from_row(row) if row else None


def get_all_agents(include_stopped: bool = False) -> list[Agent]:
    conn = get_conn()
    if include_stopped:
        rows = conn.execute("SELECT * FROM agents ORDER BY created_at DESC").fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM agents WHERE status != 'stopped' ORDER BY created_at DESC"
        ).fetchall()
    return [Agent.from_row(r) for r in rows]


def delete_agent(agent_id: str):
    conn = get_conn()
    conn.execute("DELETE FROM agents WHERE agent_id = ?", (agent_id,))
    conn.execute("DELETE FROM logs WHERE agent_id = ?", (agent_id,))
    conn.execute("DELETE FROM chat WHERE agent_id = ?", (agent_id,))
    conn.commit()


# ── Logs ────────────────────────────────────────────────────────

def add_log(entry: LogEntry):
    conn = get_conn()
    conn.execute("""
        INSERT INTO logs (log_id, agent_id, level, message, timestamp, metadata)
        VALUES (:log_id, :agent_id, :level, :message, :timestamp, :metadata)
    """, entry.to_dict())
    conn.commit()


def get_logs(agent_id: str, limit: int = 100) -> list[LogEntry]:
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM logs WHERE agent_id = ? ORDER BY timestamp DESC LIMIT ?",
        (agent_id, limit),
    ).fetchall()
    return [LogEntry.from_row(r) for r in rows]


# ── Chat ────────────────────────────────────────────────────────

def add_chat(msg: ChatMessage):
    conn = get_conn()
    conn.execute("""
        INSERT INTO chat (message_id, agent_id, direction, sender, text, timestamp)
        VALUES (:message_id, :agent_id, :direction, :sender, :text, :timestamp)
    """, msg.to_dict())
    conn.commit()


def get_chat(agent_id: str, limit: int = 50) -> list[ChatMessage]:
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM chat WHERE agent_id = ? ORDER BY timestamp DESC LIMIT ?",
        (agent_id, limit),
    ).fetchall()
    return [ChatMessage.from_row(r) for r in rows]
