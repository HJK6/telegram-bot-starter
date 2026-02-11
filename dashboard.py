"""
Admin Dashboard — Flask web UI for managing the bot.

Provides:
  - Agent overview with live status
  - Per-agent detail: chat history, logs, metrics
  - Controls: start/stop/delete agents, send messages
  - REST API for programmatic access

Runs in a background thread alongside the Telegram bot.
"""

import asyncio
import json
from functools import wraps

from flask import Flask, render_template, request, jsonify, redirect, url_for

from config import DASHBOARD_SECRET
from models import Agent
import store


_orchestrator = None  # set via create_app()


def create_app(orchestrator):
    global _orchestrator
    _orchestrator = orchestrator

    app = Flask(__name__)
    app.secret_key = DASHBOARD_SECRET

    # ── Pages ───────────────────────────────────────────────

    @app.route("/")
    def index():
        agents = _orchestrator.get_all_agents()
        stats = {
            "total": len(agents),
            "busy": sum(1 for a in agents if a.status == "busy"),
            "idle": sum(1 for a in agents if a.status == "idle"),
            "stopped": sum(1 for a in agents if a.status == "stopped"),
        }
        return render_template("dashboard.html", agents=agents, stats=stats)

    @app.route("/agent/<agent_id>")
    def agent_detail(agent_id):
        agent = _orchestrator.get_agent(agent_id)
        if not agent:
            return "Agent not found", 404
        chat = store.get_chat(agent_id, limit=50)
        chat.reverse()  # oldest first
        logs = store.get_logs(agent_id, limit=50)
        return render_template("agent_detail.html", agent=agent, chat=chat, logs=logs)

    # ── API endpoints ───────────────────────────────────────

    @app.route("/api/agents", methods=["GET"])
    def api_agents():
        agents = _orchestrator.get_all_agents()
        return jsonify([a.to_dict() for a in agents])

    @app.route("/api/agents", methods=["POST"])
    def api_create_agent():
        data = request.json or {}
        goal = data.get("goal", "")
        title = data.get("title", "")
        if not goal:
            return jsonify({"error": "goal is required"}), 400
        agent = _orchestrator.create_agent(goal, title)
        return jsonify({"agent_id": agent.agent_id, "title": agent.title})

    @app.route("/api/agents/<agent_id>", methods=["GET"])
    def api_get_agent(agent_id):
        agent = _orchestrator.get_agent(agent_id)
        if not agent:
            return jsonify({"error": "not found"}), 404
        return jsonify(agent.to_dict())

    @app.route("/api/agents/<agent_id>/stop", methods=["POST"])
    def api_stop_agent(agent_id):
        ok = _orchestrator.stop_agent(agent_id)
        return jsonify({"status": "ok" if ok else "not_found"})

    @app.route("/api/agents/<agent_id>/delete", methods=["POST"])
    def api_delete_agent(agent_id):
        ok = _orchestrator.delete_agent(agent_id)
        return jsonify({"status": "ok" if ok else "not_found"})

    @app.route("/api/agents/<agent_id>/send", methods=["POST"])
    def api_send_message(agent_id):
        data = request.json or {}
        text = data.get("message", "")
        if not text:
            return jsonify({"error": "message is required"}), 400

        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(
                _orchestrator.handle_dashboard_command("send_message", {
                    "agent_id": agent_id,
                    "message": text,
                })
            )
        finally:
            loop.close()
        return jsonify(result)

    @app.route("/api/agents/<agent_id>/chat", methods=["GET"])
    def api_get_chat(agent_id):
        chat = store.get_chat(agent_id, limit=50)
        return jsonify([c.to_dict() for c in chat])

    @app.route("/api/agents/<agent_id>/logs", methods=["GET"])
    def api_get_logs(agent_id):
        logs = store.get_logs(agent_id, limit=100)
        return jsonify([l.to_dict() for l in logs])

    # ── Form actions (from dashboard UI) ────────────────────

    @app.route("/action/new", methods=["POST"])
    def action_new():
        goal = request.form.get("goal", "").strip()
        if goal:
            _orchestrator.create_agent(goal)
        return redirect(url_for("index"))

    @app.route("/action/stop/<agent_id>", methods=["POST"])
    def action_stop(agent_id):
        _orchestrator.stop_agent(agent_id)
        return redirect(url_for("index"))

    @app.route("/action/delete/<agent_id>", methods=["POST"])
    def action_delete(agent_id):
        _orchestrator.delete_agent(agent_id)
        return redirect(url_for("index"))

    @app.route("/action/send/<agent_id>", methods=["POST"])
    def action_send(agent_id):
        text = request.form.get("message", "").strip()
        if text:
            loop = asyncio.new_event_loop()
            try:
                loop.run_until_complete(
                    _orchestrator.handle_dashboard_command("send_message", {
                        "agent_id": agent_id,
                        "message": text,
                    })
                )
            finally:
                loop.close()
        return redirect(url_for("agent_detail", agent_id=agent_id))

    return app
