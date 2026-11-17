import sqlite3
import json
import os
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from backend.app.config import settings

def get_db_path() -> str:
    url = settings.DATABASE_URL
    if url.startswith("sqlite:///"):
        return url.replace("sqlite:///", "")
    return "nex.db"

def get_connection() -> sqlite3.Connection:
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn

def init_db(drop_existing: bool = False):
    conn = get_connection()
    cursor = conn.cursor()

    if drop_existing:
        cursor.executescript("""
            DROP TABLE IF EXISTS mock_tickets;
            DROP TABLE IF EXISTS audit_events;
            DROP TABLE IF EXISTS incidents;
            DROP TABLE IF EXISTS order_events;
            DROP TABLE IF EXISTS orders;
            DROP TABLE IF EXISTS policies;
            DROP TABLE IF EXISTS demo_state;
        """)

    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS orders (
            id TEXT PRIMARY KEY,
            restaurant_name TEXT NOT NULL,
            created_at TEXT NOT NULL,
            promised_at TEXT NOT NULL,
            status TEXT NOT NULL,
            courier_assigned INTEGER NOT NULL,
            last_status_update_at TEXT NOT NULL,
            restaurant_backlog INTEGER NOT NULL,
            estimated_prep_minutes_remaining INTEGER NOT NULL,
            distance_km REAL NOT NULL,
            items_json TEXT NOT NULL DEFAULT '[]',
            customer_notes TEXT
        );

        CREATE TABLE IF NOT EXISTS order_events (
            id TEXT PRIMARY KEY,
            order_id TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            event_type TEXT NOT NULL,
            details_json TEXT NOT NULL DEFAULT '{}',
            FOREIGN KEY(order_id) REFERENCES orders(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS incidents (
            id TEXT PRIMARY KEY,
            order_id TEXT NOT NULL UNIQUE,
            risk_score INTEGER NOT NULL,
            risk_level TEXT NOT NULL,
            risk_signals_json TEXT NOT NULL DEFAULT '[]',
            status TEXT NOT NULL,
            analysis_job_id TEXT,
            agent_result_json TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            approved_at TEXT,
            executed_at TEXT,
            error_message TEXT,
            FOREIGN KEY(order_id) REFERENCES orders(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS audit_events (
            id TEXT PRIMARY KEY,
            incident_id TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            actor TEXT NOT NULL,
            event_type TEXT NOT NULL,
            payload_redacted_json TEXT NOT NULL DEFAULT '{}',
            correlation_id TEXT,
            FOREIGN KEY(incident_id) REFERENCES incidents(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS mock_tickets (
            id TEXT PRIMARY KEY,
            incident_id TEXT NOT NULL UNIQUE,
            priority TEXT NOT NULL,
            category TEXT NOT NULL,
            description TEXT NOT NULL,
            created_at TEXT NOT NULL,
            created_by_workflow_id TEXT NOT NULL,
            FOREIGN KEY(incident_id) REFERENCES incidents(id) ON DELETE CASCADE
        );

        CREATE UNIQUE INDEX IF NOT EXISTS idx_mock_tickets_incident_id ON mock_tickets(incident_id);

        CREATE TABLE IF NOT EXISTS policies (
            code TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            version TEXT NOT NULL,
            category TEXT NOT NULL,
            summary TEXT NOT NULL,
            recommended_action TEXT NOT NULL,
            content TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS demo_state (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
    """)

    conn.commit()
    conn.close()
