"""
Intelligent Router and Guardrail Classifier for Project Atlas.
Classifies queries into distinct operational intents:
1. factual_lookup
2. comparison
3. calculation
4. sql_aggregate
5. out_of_scope
6. unsafe (prompt injections, confidential leaks, destructive commands)
7. entitlement_restricted
8. beyond_forecast_window
"""
import re
import logging
from typing import Dict, Any, Tuple, Optional
from src.db import log_audit_event

logger = logging.getLogger(__name__)

# Pattern sets for classification
UNSAFE_PATTERNS = [
    (r"(?:disregard|ignore)\s+(?:all\s+)?(?:previous|prior)\s+instructions", "prompt_injection_override"),
    (r"list\s+(?:all\s+)?(?:client\s+)?emails?", "confidential_data_exfiltration"),
    (r"contact\s+emails?", "confidential_data_exfiltration"),
    (r"print\s+(?:the\s+)?(?:full\s+)?contents\s+of\s+(?:the\s+)?clients?\s+table", "confidential_table_dump"),
    (r"delete\s+(?:all\s+)?(?:rows|from|tables?)", "destructive_sql_attempt"),
    (r"drop\s+table", "destructive_sql_attempt"),
    (r"truncate\s+table", "destructive_sql_attempt"),
    (r"update\s+.*\s+set", "destructive_sql_attempt"),
    (r"insert\s+into", "destructive_sql_attempt"),
    (r"alter\s+table", "destructive_sql_attempt"),
    (r"show\s+tables", "schema_reconnaissance"),
    (r"system\s+prompt", "prompt_leak_attempt")
]

OUT_OF_SCOPE_PATTERNS = [
    (r"\b(election|vote|president|prime minister|politics|democrat|republican|parliament)\b", "politics"),
    (r"\b(weather|temperature today|forecast tomorrow)\b", "weather"),
    (r"\b(who won the match|sports score|world cup|cricket)\b", "sports"),
    (r"\b(movie|celebrity|hollywood|bollywood)\b", "entertainment"),
    (r"\b(personal data|passwords?|credit card)\b", "personal_info"),
    (r"\bother clients?('s)? (purchases|orders|contracts)\b", "client_confidentiality")
]

AGGREGATE_SQL_PATTERNS = [
    r"which sector has the most reports",
    r"how many (?:total )?reports (?:do you have|in your library|are published|are in)",
    r"how many .* reports",
    r"list all sectors",
    r"count of reports",
    r"most published sector",
    r"breakdown of reports by sector"
]

CALCULATION_PATTERNS = [
    r"\b(what will .* be worth in 2030|apac .* in 2030|projected.*2030|projected.*2029)\b",
    r"\b(calculate|compound|project|cagr extrapolation|estimate 2030)\b",
    r"\b(what is the formula|derived value|assumptions used)\b"
]

COMPARISON_PATTERNS = [
    r"\b(compare|which report should i trust|difference between r-101 and r-102|conflict|disagree)\b",
    r"\b(both reports|two reports|variance|methodology differences?)\b"
]

BEYOND_FORECAST_PATTERNS = [
    r"\b(203[1-9]|204\d|205\d)\b"  # 2031-2059
]


class Router:
    """
    Classifies incoming user questions to direct the agent graph
    and immediately enforce safety guardrails.
    """

    @staticmethod
    def classify(question: str, client_id: str) -> Dict[str, Any]:
        """
        Analyzes query structure and returns classification metadata.
        """
        q_clean = question.strip()

        # 1. Check Unsafe / Hostile / Injections
        for pattern, reason in UNSAFE_PATTERNS:
            if re.search(pattern, q_clean, re.IGNORECASE):
                logger.warning(f"Unsafe request detected: {reason} for client {client_id}")
                log_audit_event(
                    event_type="injection_attempt" if "injection" in reason or "prompt" in reason else "sql_blocked",
                    client_id=client_id,
                    query_text=q_clean,
                    details={"matched_pattern": pattern, "threat_type": reason}
                )
                return {
                    "intent": "unsafe",
                    "reason": reason,
                    "action": "refuse_unsafe",
                    "confidence": 1.0
                }

        # 2. Check Out-of-Scope / Sensitive / Politics
        for pattern, topic in OUT_OF_SCOPE_PATTERNS:
            if re.search(pattern, q_clean, re.IGNORECASE):
                logger.info(f"Out of scope topic detected: {topic}")
                log_audit_event(
                    event_type="out_of_scope_blocked",
                    client_id=client_id,
                    query_text=q_clean,
                    details={"topic": topic}
                )
                return {
                    "intent": "out_of_scope",
                    "topic": topic,
                    "action": "redirect_out_of_scope",
                    "confidence": 1.0
                }

        # 3. Check Forecast Window Exceeded (e.g. 2035)
        for pattern in BEYOND_FORECAST_PATTERNS:
            match = re.search(pattern, q_clean)
            if match:
                target_year = match.group(0)
                return {
                    "intent": "beyond_forecast",
                    "target_year": target_year,
                    "action": "escalate_or_refuse_extrapolation",
                    "confidence": 0.50
                }

        # 4. Check SQL Aggregates (e.g., sector report counts)
        for pattern in AGGREGATE_SQL_PATTERNS:
            if re.search(pattern, q_clean, re.IGNORECASE):
                return {
                    "intent": "sql_aggregate",
                    "action": "run_sql_tool",
                    "confidence": 0.95
                }

        # 5. Check Comparison / Trust / Conflict queries
        for pattern in COMPARISON_PATTERNS:
            if re.search(pattern, q_clean, re.IGNORECASE):
                return {
                    "intent": "comparison",
                    "action": "analyze_conflicts_and_scopes",
                    "confidence": 0.85
                }

        # 6. Check Calculation / Missing Numbers / Projections
        for pattern in CALCULATION_PATTERNS:
            if re.search(pattern, q_clean, re.IGNORECASE):
                return {
                    "intent": "calculation",
                    "action": "run_calculator_tool",
                    "confidence": 0.85
                }

        # 7. Default to Factual Lookup (RAG)
        return {
            "intent": "factual_lookup",
            "action": "run_retriever",
            "confidence": 0.90
        }


router = Router()
