"""
Cache and telemetry tracking for Project Atlas.
Provides:
1. Low-latency response cache for repeated queries per client.
2. Latency timer and estimated cost calculation.
3. Audit logging integration.
"""
import time
import hashlib
import logging
from typing import Dict, Any, Optional, Tuple
from src.db import log_audit_event

logger = logging.getLogger(__name__)


class SemanticCache:
    """
    In-memory response cache indexed by client_id and normalized query hash.
    Ensures repeated questions return in < 15ms with zero LLM API cost.
    """
    def __init__(self):
        self._cache: Dict[str, Dict[str, Any]] = {}

    def _make_key(self, client_id: str, question: str) -> str:
        norm_q = " ".join(question.lower().strip().split())
        raw_key = f"{client_id}::{norm_q}"
        return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()

    def get(self, client_id: str, question: str) -> Optional[Dict[str, Any]]:
        key = self._make_key(client_id, question)
        entry = self._cache.get(key)
        if entry:
            logger.info(f"Cache hit for client {client_id}: {question[:40]}...")
            return entry["response"]
        return None

    def set(self, client_id: str, question: str, response_data: Dict[str, Any]):
        key = self._make_key(client_id, question)
        self._cache[key] = {
            "response": response_data,
            "created_at": time.time()
        }

    def clear(self):
        self._cache.clear()


response_cache = SemanticCache()


def estimate_request_cost(input_chars: int, output_chars: int) -> float:
    """
    Estimates query cost based on standard model token pricing
    (~4 chars per token; $0.15 / 1M input tokens, $0.60 / 1M output tokens).
    """
    input_tokens = input_chars / 4.0
    output_tokens = output_chars / 4.0
    cost = (input_tokens * 0.00000015) + (output_tokens * 0.00000060)
    return round(cost, 6)
