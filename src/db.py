"""
Database access layer for Project Atlas.
Provides MySQL connection pooling, read-only query execution with strict AST security,
and seamless fallback to SQLite for local development and standalone testing.
"""
import os
import re
import json
import sqlite3
import logging
from typing import Dict, Any, List, Optional, Tuple
import pymysql
from pymysql.cursors import DictCursor
import sqlparse

from src.config import settings

logger = logging.getLogger(__name__)

# Fallback SQLite DB path for local offline development/testing
SQLITE_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "atlas_local.sqlite")


def is_mysql_available() -> bool:
    """Check if MySQL server is reachable."""
    try:
        conn = pymysql.connect(
            host=settings.MYSQL_HOST,
            port=settings.MYSQL_PORT,
            user=settings.MYSQL_USER,
            password=settings.MYSQL_PASSWORD,
            database=settings.MYSQL_DATABASE,
            connect_timeout=2,
            cursorclass=DictCursor
        )
        conn.close()
        return True
    except Exception as e:
        logger.debug(f"MySQL connection check failed: {e}. Utilizing embedded store fallback.")
        return False


def get_connection(readonly: bool = False):
    """
    Get a database connection. Returns PyMySQL connection if available,
    otherwise returns a SQLite connection initialized with seed data.
    """
    if is_mysql_available():
        user = settings.MYSQL_READONLY_USER if readonly else settings.MYSQL_USER
        password = settings.MYSQL_READONLY_PASSWORD if readonly else settings.MYSQL_PASSWORD
        return pymysql.connect(
            host=settings.MYSQL_HOST,
            port=settings.MYSQL_PORT,
            user=user,
            password=password,
            database=settings.MYSQL_DATABASE,
            charset="utf8mb4",
            cursorclass=DictCursor,
            connect_timeout=int(settings.SQL_QUERY_TIMEOUT_SECONDS)
        )
    else:
        # SQLite fallback
        os.makedirs(os.path.dirname(SQLITE_DB_PATH), exist_ok=True)
        conn = sqlite3.connect(SQLITE_DB_PATH)
        conn.row_factory = sqlite3.Row
        _init_sqlite_if_needed(conn)
        return conn


def _init_sqlite_if_needed(conn: sqlite3.Connection):
    """Initializes SQLite schema and seed data identical to MySQL init.sql if empty."""
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='reports'")
    if cursor.fetchone() is None:
        cursor.executescript("""
        CREATE TABLE reports (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            publisher TEXT NOT NULL,
            published TEXT NOT NULL,
            sector TEXT NOT NULL,
            access TEXT NOT NULL
        );

        CREATE TABLE market_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            report TEXT NOT NULL,
            metric TEXT NOT NULL,
            region TEXT NOT NULL,
            year_period TEXT NOT NULL,
            value TEXT NOT NULL,
            scope_note TEXT NOT NULL,
            FOREIGN KEY (report) REFERENCES reports(id)
        );

        CREATE TABLE clients (
            id TEXT PRIMARY KEY,
            company TEXT NOT NULL,
            contact_email TEXT NOT NULL,
            purchased_reports TEXT NOT NULL
        );

        CREATE TABLE escalations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id TEXT NOT NULL,
            question TEXT NOT NULL,
            reason TEXT NOT NULL,
            confidence REAL NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            client_id TEXT NOT NULL,
            question TEXT NOT NULL,
            answer TEXT NOT NULL,
            citations TEXT NULL,
            conflicts TEXT NULL,
            derived_values TEXT NULL,
            confidence REAL NOT NULL,
            escalated INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id INTEGER NOT NULL,
            rating TEXT NOT NULL,
            comments TEXT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (conversation_id) REFERENCES conversations(id)
        );

        CREATE TABLE audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT NOT NULL,
            client_id TEXT NULL,
            query_text TEXT NULL,
            details TEXT NULL,
            latency_ms REAL NULL,
            cost_usd REAL NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- Seed Reports
        INSERT INTO reports (id, title, publisher, published, sector, access) VALUES
        ('R-101', 'Global Smart Water Meter Market 2025', 'CMR', '2025-03-10', 'Utilities', 'paid'),
        ('R-102', 'Smart Water Metering: Industry Outlook 2024', 'Aquila Insights (third party)', '2024-06-18', 'Utilities', 'public excerpt'),
        ('R-103', 'Residential Water Purifier Market 2025', 'CMR', '2025-01-22', 'Consumer Durables', 'paid'),
        ('R-104', 'Commercial Heat Pumps Market 2025', 'CMR', '2025-02-14', 'Clean Energy', 'paid'),
        ('R-105', 'EV Fast Charging Infrastructure 2025', 'CMR', '2025-02-28', 'Automotive', 'paid'),
        ('R-106', 'Industrial IoT Sensors Market 2025', 'CMR', '2025-04-05', 'Manufacturing', 'paid'),
        ('R-107', 'Smart Grid Distribution Automation 2024', 'GridVision Research (third party)', '2024-11-15', 'Utilities', 'public excerpt');

        -- Seed Metrics
        INSERT INTO market_metrics (report, metric, region, year_period, value, scope_note) VALUES
        ('R-101', 'Market size', 'Global', '2024', 'USD 4.21 B', 'Includes hardware, software and services'),
        ('R-101', 'CAGR', 'Global', '2025-2030', '11.2 %', 'Forecast period stated as 2025-2030'),
        ('R-101', 'Regional share', 'APAC', '2024', '38 %', 'Share of global market size'),
        ('R-102', 'Market size', 'Global', '2024', 'USD 3.87 B', 'AMR / AMI hardware only'),
        ('R-102', 'CAGR', 'Global', '2024-2029', '9.8 %', 'Different forecast window from R-101'),
        ('R-102', 'Regional share', 'APAC', '2024', '41 %', 'Share of hardware market'),
        ('R-103', 'Market size', 'Global', '2024', 'USD 9.60 B', 'Point-of-use residential purification systems'),
        ('R-103', 'CAGR', 'Global', '2025-2030', '8.5 %', 'Forecast period stated as 2025-2030'),
        ('R-103', 'Regional share', 'APAC', '2024', '46 %', 'Share of global consumer durables water filtration'),
        ('R-104', 'Market size', 'Global', '2024', 'USD 8.12 B', 'Air-to-water & ground-source commercial installations'),
        ('R-104', 'CAGR', 'Global', '2025-2030', '13.4 %', 'Forecast period stated as 2025-2030'),
        ('R-104', 'Regional share', 'Europe', '2024', '44 %', 'Driven by EU decarbonization policy'),
        ('R-105', 'Market size', 'Global', '2024', 'USD 5.75 B', 'DC fast charging equipment and cloud network software'),
        ('R-105', 'CAGR', 'Global', '2025-2030', '22.8 %', 'Forecast period stated as 2025-2030'),
        ('R-105', 'Regional share', 'APAC', '2024', '52 %', 'High growth segment led by China and Korea'),
        ('R-106', 'Market size', 'Global', '2024', 'USD 12.30 B', 'Vibration, temperature, acoustic and pressure industrial sensors'),
        ('R-106', 'CAGR', 'Global', '2025-2030', '10.1 %', 'Forecast period stated as 2025-2030'),
        ('R-106', 'Regional share', 'North America', '2024', '36 %', 'Industry 4.0 predictive maintenance installations'),
        ('R-107', 'Market size', 'Global', '2024', 'USD 7.40 B', 'Substation automation and feeder management hardware'),
        ('R-107', 'CAGR', 'Global', '2024-2029', '7.9 %', 'Forecast period stated as 2024-2029'),
        ('R-107', 'Regional share', 'North America', '2024', '40 %', 'Grid modernization utility programs');

        -- Seed Clients
        INSERT INTO clients (id, company, contact_email, purchased_reports) VALUES
        ('C-01', 'Northwind Utilities', 'ops@example.com', 'R-101, R-103'),
        ('C-02', 'Blue Delta Infra', 'procurement@example.com', 'R-103');
        """)
        conn.commit()


def validate_read_only_sql(sql: str) -> Tuple[bool, str]:
    """
    Validates that a SQL query is strictly read-only, non-destructive,
    single statement, and safe to execute.
    """
    cleaned = sql.strip().strip(";")
    parsed = sqlparse.parse(cleaned)
    if not parsed or len(parsed) != 1:
        return False, "Only single SQL statements are allowed."

    stmt = parsed[0]
    stmt_type = stmt.get_type()
    if stmt_type != "SELECT":
        return False, f"Illegal SQL statement type: {stmt_type}. Only SELECT queries are permitted."

    # Forbidden keyword check
    forbidden = [
        "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE", "CREATE",
        "REPLACE", "GRANT", "REVOKE", "EXEC", "EXECUTE", "UNION", "INTO OUTFILE",
        "LOAD_FILE", "BENCHMARK", "SLEEP", "INFORMATION_SCHEMA", "MYSQL"
    ]
    tokens = [token.value.upper() for token in stmt.flatten() if not token.is_whitespace]
    for token in tokens:
        for f in forbidden:
            if token == f or re.search(rf"\b{f}\b", token):
                return False, f"Forbidden SQL keyword or pattern detected: {token}"

    return True, cleaned


def execute_read_only_sql(sql: str, max_rows: int = settings.MAX_SQL_ROWS) -> Dict[str, Any]:
    """
    Executes a read-only query safely with row limits, timeout, and AST guardrails.
    Returns:
        {
            "success": bool,
            "data": list[dict],
            "query": str,
            "row_count": int,
            "error": Optional[str]
        }
    """
    is_safe, message_or_cleaned = validate_read_only_sql(sql)
    if not is_safe:
        return {
            "success": False,
            "data": [],
            "query": sql,
            "row_count": 0,
            "error": message_or_cleaned
        }

    clean_sql = message_or_cleaned
    # Enforce LIMIT if not explicitly present
    if not re.search(r"\bLIMIT\b", clean_sql, re.IGNORECASE):
        clean_sql = f"{clean_sql} LIMIT {max_rows}"

    conn = get_connection(readonly=True)
    try:
        cursor = conn.cursor()
        cursor.execute(clean_sql)
        rows = cursor.fetchall()

        # Format results
        if isinstance(conn, sqlite3.Connection):
            results = [dict(row) for row in rows]
        else:
            results = list(rows)

        return {
            "success": True,
            "data": results,
            "query": clean_sql,
            "row_count": len(results),
            "error": None
        }
    except Exception as e:
        logger.error(f"Read-only query execution failed: {e}")
        return {
            "success": False,
            "data": [],
            "query": clean_sql,
            "row_count": 0,
            "error": str(e)
        }
    finally:
        conn.close()


def get_client(client_id: str) -> Optional[Dict[str, Any]]:
    """Retrieves client record and parses purchased reports."""
    conn = get_connection(readonly=True)
    try:
        cursor = conn.cursor()
        if isinstance(conn, sqlite3.Connection):
            cursor.execute("SELECT id, company, contact_email, purchased_reports FROM clients WHERE id = ?", (client_id,))
            row = cursor.fetchone()
            if not row:
                return None
            data = dict(row)
        else:
            cursor.execute("SELECT id, company, contact_email, purchased_reports FROM clients WHERE id = %s", (client_id,))
            data = cursor.fetchone()
            if not data:
                return None

        # Parse purchased reports
        reports_raw = data.get("purchased_reports", "")
        purchased = [r.strip() for r in reports_raw.split(",") if r.strip()]
        data["purchased_list"] = purchased
        return data
    finally:
        conn.close()


def get_all_reports() -> List[Dict[str, Any]]:
    """Retrieves all reports."""
    conn = get_connection(readonly=True)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id, title, publisher, published, sector, access FROM reports ORDER BY id ASC")
        rows = cursor.fetchall()
        if isinstance(conn, sqlite3.Connection):
            return [dict(r) for r in rows]
        return list(rows)
    finally:
        conn.close()


def get_report_by_id(report_id: str) -> Optional[Dict[str, Any]]:
    """Retrieves report by ID."""
    conn = get_connection(readonly=True)
    try:
        cursor = conn.cursor()
        if isinstance(conn, sqlite3.Connection):
            cursor.execute("SELECT * FROM reports WHERE id = ?", (report_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
        else:
            cursor.execute("SELECT * FROM reports WHERE id = %s", (report_id,))
            return cursor.fetchone()
    finally:
        conn.close()


def get_metrics_for_report(report_id: str) -> List[Dict[str, Any]]:
    """Retrieves all metrics for a given report ID."""
    conn = get_connection(readonly=True)
    try:
        cursor = conn.cursor()
        if isinstance(conn, sqlite3.Connection):
            cursor.execute("SELECT * FROM market_metrics WHERE report = ?", (report_id,))
            return [dict(r) for r in cursor.fetchall()]
        else:
            cursor.execute("SELECT * FROM market_metrics WHERE report = %s", (report_id,))
            return list(cursor.fetchall())
    finally:
        conn.close()


def create_escalation(client_id: str, question: str, reason: str, confidence: float) -> int:
    """Inserts a new analyst escalation ticket."""
    conn = get_connection(readonly=False)
    try:
        cursor = conn.cursor()
        if isinstance(conn, sqlite3.Connection):
            cursor.execute(
                "INSERT INTO escalations (client_id, question, reason, confidence, status) VALUES (?, ?, ?, ?, 'pending')",
                (client_id, question, reason, float(confidence))
            )
            ticket_id = cursor.lastrowid
            conn.commit()
            return ticket_id
        else:
            cursor.execute(
                "INSERT INTO escalations (client_id, question, reason, confidence, status) VALUES (%s, %s, %s, %s, 'pending')",
                (client_id, question, reason, float(confidence))
            )
            ticket_id = cursor.lastrowid
            conn.commit()
            return ticket_id
    finally:
        conn.close()


def get_escalations(limit: int = 50) -> List[Dict[str, Any]]:
    """Retrieves recent escalation tickets."""
    conn = get_connection(readonly=True)
    try:
        cursor = conn.cursor()
        query = f"SELECT id, client_id, question, reason, confidence, status, created_at FROM escalations ORDER BY id DESC LIMIT {limit}"
        cursor.execute(query)
        rows = cursor.fetchall()
        if isinstance(conn, sqlite3.Connection):
            return [dict(r) for r in rows]
        return list(rows)
    finally:
        conn.close()


def save_conversation(
    session_id: str,
    client_id: str,
    question: str,
    answer: str,
    citations: List[Dict[str, Any]],
    conflicts: List[Dict[str, Any]],
    derived_values: List[Dict[str, Any]],
    confidence: float,
    escalated: bool
) -> int:
    """Stores full conversation turn for legacy CodeIgniter 3 portal."""
    conn = get_connection(readonly=False)
    try:
        cursor = conn.cursor()
        cit_json = json.dumps(citations)
        conf_json = json.dumps(conflicts)
        der_json = json.dumps(derived_values)
        esc_val = 1 if escalated else 0

        if isinstance(conn, sqlite3.Connection):
            cursor.execute(
                """INSERT INTO conversations 
                   (session_id, client_id, question, answer, citations, conflicts, derived_values, confidence, escalated)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (session_id, client_id, question, answer, cit_json, conf_json, der_json, float(confidence), esc_val)
            )
            conv_id = cursor.lastrowid
            conn.commit()
            return conv_id
        else:
            cursor.execute(
                """INSERT INTO conversations 
                   (session_id, client_id, question, answer, citations, conflicts, derived_values, confidence, escalated)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (session_id, client_id, question, answer, cit_json, conf_json, der_json, float(confidence), esc_val)
            )
            conv_id = cursor.lastrowid
            conn.commit()
            return conv_id
    finally:
        conn.close()


def record_feedback(conversation_id: int, rating: str, comments: Optional[str] = None) -> bool:
    """Records thumbs-up / thumbs-down rating."""
    if rating not in ("up", "down"):
        return False
    conn = get_connection(readonly=False)
    try:
        cursor = conn.cursor()
        if isinstance(conn, sqlite3.Connection):
            cursor.execute(
                "INSERT INTO feedback (conversation_id, rating, comments) VALUES (?, ?, ?)",
                (conversation_id, rating, comments)
            )
            conn.commit()
            return True
        else:
            cursor.execute(
                "INSERT INTO feedback (conversation_id, rating, comments) VALUES (%s, %s, %s)",
                (conversation_id, rating, comments)
            )
            conn.commit()
            return True
    finally:
        conn.close()


def log_audit_event(
    event_type: str,
    client_id: Optional[str] = None,
    query_text: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    latency_ms: Optional[float] = 0.0,
    cost_usd: Optional[float] = 0.0
) -> int:
    """Logs security audit, injection detection, and API usage."""
    conn = get_connection(readonly=False)
    try:
        cursor = conn.cursor()
        details_json = json.dumps(details or {})
        if isinstance(conn, sqlite3.Connection):
            cursor.execute(
                """INSERT INTO audit_logs (event_type, client_id, query_text, details, latency_ms, cost_usd)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (event_type, client_id, query_text, details_json, latency_ms, cost_usd)
            )
            audit_id = cursor.lastrowid
            conn.commit()
            return audit_id
        else:
            cursor.execute(
                """INSERT INTO audit_logs (event_type, client_id, query_text, details, latency_ms, cost_usd)
                   VALUES (%s, %s, %s, %s, %s, %s)""",
                (event_type, client_id, query_text, details_json, latency_ms, cost_usd)
            )
            audit_id = cursor.lastrowid
            conn.commit()
            return audit_id
    finally:
        conn.close()
