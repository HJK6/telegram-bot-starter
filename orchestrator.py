"""
Orchestrator — manages agents, routes messages, handles lifecycle.

This is the brain of the bot. It decides which agent handles each
incoming message, manages agent state, and coordinates between
the Telegram bot and the dashboard.

Architecture:
  - Each "agent" is a task handler with its own conversation history
  - Messages are routed to agents via a multi-level strategy
  - Agents can be started/stopped from Telegram or the dashboard
  - All state persists in SQLite (survives restarts)
"""

from __future__ import annotations
import asyncio
import logging
import re
import subprocess
from datetime import datetime, timezone
from typing import Optional, Callable, Awaitable

from models import Agent, LogEntry, ChatMessage, _now
import store

log = logging.getLogger(__name__)


class Orchestrator:
    def __init__(self):
        self.agents: dict[str, Agent] = {}
        self._message_callback: Optional[Callable] = None
        self._last_sender_id: Optional[str] = None
        self._load_agents()

    def _load_agents(self):
        """Recover agents from the database on startup."""
        for agent in store.get_all_agents():
            if agent.status == "busy":
                agent.status = "idle"  # can't be busy on cold start
                store.save_agent(agent)
            self.agents[agent.agent_id] = agent
        log.info(f"Recovered {len(self.agents)} agents from database")

    def set_message_callback(self, callback: Callable[[str, str], Awaitable[None]]):
        """
        Register a callback for sending messages to Telegram.
        callback(agent_id, text) — called when an agent has output.
        """
        self._message_callback = callback

    # ── Agent lifecycle ─────────────────────────────────────────

    def create_agent(self, goal: str, title: str = "") -> Agent:
        """Create a new agent with a goal."""
        if not title:
            title = goal[:40].strip()
        agent = Agent(title=title, goal=goal, status="idle")
        self.agents[agent.agent_id] = agent
        store.save_agent(agent)
        self._log(agent.agent_id, "info", f"Agent created: {title}")
        log.info(f"Created agent {agent.short_id}: {title}")
        return agent

    def stop_agent(self, agent_id: str) -> bool:
        """Stop an agent. Returns True if found."""
        agent = self.agents.get(agent_id)
        if not agent:
            return False
        agent.status = "stopped"
        store.save_agent(agent)
        self._log(agent_id, "info", "Agent stopped")
        log.info(f"Stopped agent {agent.short_id}")
        return True

    def delete_agent(self, agent_id: str) -> bool:
        """Delete an agent and all its data."""
        if agent_id not in self.agents:
            return False
        self.agents.pop(agent_id)
        store.delete_agent(agent_id)
        log.info(f"Deleted agent {agent_id[:8]}")
        return True

    def get_agent(self, agent_id: str) -> Optional[Agent]:
        return self.agents.get(agent_id)

    def get_active_agents(self) -> list[Agent]:
        return [a for a in self.agents.values() if a.status in ("idle", "busy")]

    def get_all_agents(self) -> list[Agent]:
        return list(self.agents.values())

    # ── Message routing ─────────────────────────────────────────

    async def route_message(self, text: str, sender: str = "user") -> Optional[str]:
        """
        Route an incoming message to the right agent.
        Returns the agent_id it was routed to, or None if a new agent was created.

        Routing strategy (checked in order):
          1. Explicit "new agent/task" keywords → create new agent
          2. Agent ID prefix match (first 8 chars of message)
          3. [Title] bracket notation
          4. Title mentioned in text
          5. Follow-up heuristic (single active agent + short reply)
          6. Keyword scoring across agent contexts
          7. Fallback: last agent that sent a message
        """
        text_lower = text.lower().strip()

        # 1. Explicit new-agent keywords
        new_patterns = ["new agent", "new task", "start a new", "create agent"]
        if any(p in text_lower for p in new_patterns):
            # Strip the trigger phrase and use the rest as the goal
            goal = text
            for p in new_patterns:
                goal = re.sub(re.escape(p), "", goal, flags=re.IGNORECASE).strip()
            goal = goal.strip(":- ") or text
            agent = self.create_agent(goal)
            self._record_chat(agent.agent_id, text, "inbound", sender)
            await self._process_message(agent, text)
            return agent.agent_id

        active = self.get_active_agents()
        if not active:
            agent = self.create_agent(text)
            self._record_chat(agent.agent_id, text, "inbound", sender)
            await self._process_message(agent, text)
            return agent.agent_id

        # 2. Agent ID prefix (e.g., "a1b2c3d4 do this thing")
        words = text.split()
        if words and len(words[0]) >= 8:
            prefix = words[0].lower()
            for agent in active:
                if agent.agent_id.startswith(prefix):
                    msg = " ".join(words[1:]) or text
                    self._record_chat(agent.agent_id, msg, "inbound", sender)
                    await self._process_message(agent, msg)
                    return agent.agent_id

        # 3. [Title] bracket notation
        bracket_match = re.match(r"^\[([^\]]+)\]\s*(.*)", text, re.DOTALL)
        if bracket_match:
            target_title = bracket_match.group(1).lower()
            msg = bracket_match.group(2).strip() or text
            for agent in active:
                if agent.title.lower() == target_title:
                    self._record_chat(agent.agent_id, msg, "inbound", sender)
                    await self._process_message(agent, msg)
                    return agent.agent_id

        # 4. Title mentioned in text
        for agent in active:
            if len(agent.title) > 5 and agent.title.lower() in text_lower:
                self._record_chat(agent.agent_id, text, "inbound", sender)
                await self._process_message(agent, text)
                return agent.agent_id

        # 5. Follow-up heuristic (single agent + short/affirmative reply)
        if len(active) == 1:
            quick_replies = {"yes", "no", "ok", "sure", "do it", "go", "y", "n",
                             "yeah", "nah", "continue", "stop", "done", "thanks"}
            if text_lower in quick_replies or len(text) < 30:
                agent = active[0]
                self._record_chat(agent.agent_id, text, "inbound", sender)
                await self._process_message(agent, text)
                return agent.agent_id

        # 6. Keyword scoring
        best_agent, best_score = None, 0
        text_words = set(text_lower.split())
        for agent in active:
            score = 0
            goal_words = set(agent.goal.lower().split())
            score += len(text_words & goal_words) * 3

            task_words = set(agent.current_task.lower().split())
            score += len(text_words & task_words) * 2

            # Bonus for being the last sender
            if agent.agent_id == self._last_sender_id:
                score += 2

            if score > best_score:
                best_score = score
                best_agent = agent

        if best_agent and best_score >= 2:
            self._record_chat(best_agent.agent_id, text, "inbound", sender)
            await self._process_message(best_agent, text)
            return best_agent.agent_id

        # 7. Fallback: last sender or create new
        if self._last_sender_id and self._last_sender_id in self.agents:
            agent = self.agents[self._last_sender_id]
            if agent.status in ("idle", "busy"):
                self._record_chat(agent.agent_id, text, "inbound", sender)
                await self._process_message(agent, text)
                return agent.agent_id

        # Nothing matched — create new agent
        agent = self.create_agent(text)
        self._record_chat(agent.agent_id, text, "inbound", sender)
        await self._process_message(agent, text)
        return agent.agent_id

    async def _process_message(self, agent: Agent, text: str):
        """
        Process a message for an agent.

        Override this method to plug in your actual agent logic:
        - Call an LLM API (OpenAI, Anthropic, Ollama)
        - Run a shell command
        - Execute a workflow

        The default implementation echoes the message back.
        """
        agent.status = "busy"
        agent.current_task = f"Processing: {text[:60]}"
        agent.conversation_history.append({"role": "user", "text": text, "ts": _now()})
        store.save_agent(agent)

        # ┌──────────────────────────────────────────────────────┐
        # │  REPLACE THIS with your agent logic.                 │
        # │                                                      │
        # │  Examples:                                           │
        # │    response = await call_openai(agent.goal, text)    │
        # │    response = await call_anthropic(agent.goal, text) │
        # │    response = run_ollama(agent.goal, text)           │
        # │    response = subprocess.run(["claude", ...])        │
        # └──────────────────────────────────────────────────────┘
        response = f"Agent [{agent.title}] received: {text}"

        agent.status = "idle"
        agent.current_task = ""
        agent.last_heartbeat = _now()
        agent.conversation_history.append({"role": "agent", "text": response, "ts": _now()})
        store.save_agent(agent)

        self._record_chat(agent.agent_id, response, "outbound", agent.title)
        self._last_sender_id = agent.agent_id

        if self._message_callback:
            tagged = f"[{agent.title}] {response}"
            await self._message_callback(agent.agent_id, tagged)

    # ── Dashboard commands ──────────────────────────────────────

    async def handle_dashboard_command(self, command: str, payload: dict) -> dict:
        """
        Process a command from the admin dashboard.
        Returns a result dict.
        """
        if command == "start_agent":
            agent = self.create_agent(
                goal=payload.get("goal", ""),
                title=payload.get("title", ""),
            )
            return {"status": "ok", "agent_id": agent.agent_id}

        elif command == "stop_agent":
            ok = self.stop_agent(payload["agent_id"])
            return {"status": "ok" if ok else "not_found"}

        elif command == "delete_agent":
            ok = self.delete_agent(payload["agent_id"])
            return {"status": "ok" if ok else "not_found"}

        elif command == "send_message":
            agent_id = payload["agent_id"]
            text = payload["message"]
            agent = self.get_agent(agent_id)
            if not agent:
                return {"status": "not_found"}
            self._record_chat(agent_id, text, "inbound", "dashboard")
            await self._process_message(agent, text)
            return {"status": "ok"}

        return {"status": "unknown_command"}

    # ── Helpers ─────────────────────────────────────────────────

    def _log(self, agent_id: str, level: str, message: str):
        entry = LogEntry(agent_id=agent_id, level=level, message=message)
        store.add_log(entry)

    def _record_chat(self, agent_id: str, text: str, direction: str, sender: str):
        msg = ChatMessage(agent_id=agent_id, direction=direction, sender=sender, text=text)
        store.add_chat(msg)

    def get_status_text(self) -> str:
        """Formatted status for the /status command."""
        active = self.get_active_agents()
        if not active:
            return "No active agents."
        lines = [f"Active agents: {len(active)}\n"]
        for a in active:
            lines.append(
                f"  [{a.short_id}] {a.title}\n"
                f"    Status: {a.status} | Uptime: {a.uptime}\n"
                f"    Task: {a.current_task or '(idle)'}"
            )
        return "\n".join(lines)

    def get_agents_text(self) -> str:
        """Agent list for the /agents command."""
        agents = self.get_all_agents()
        if not agents:
            return "No agents."
        lines = []
        for a in agents:
            lines.append(f"  {a.short_id}  {a.status:<8}  {a.title}")
        return "ID        Status    Title\n" + "\n".join(lines)
