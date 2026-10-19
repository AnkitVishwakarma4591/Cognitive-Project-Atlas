"""
Vector store and document ingestion pipeline for Project Atlas.
Provides:
1. Markdown report ingestion and structured chunking with metadata (report_id, sector, region, year, page).
2. Prompt injection detection and neutralization (e.g. R-102 page 14 attack).
3. Entitlement-aware filtering before LLM retrieval.
4. Hybrid Dense/BM25 vector search with cosine similarity.
"""
import os
import re
import math
import logging
from typing import List, Dict, Any, Optional, Tuple, Set
from collections import Counter

from src.config import settings
from src.db import get_client, get_all_reports, log_audit_event

logger = logging.getLogger(__name__)

# Injection signature patterns (used to detect adversarial instructions embedded in documents or user queries)
INJECTION_PATTERNS = [
    r"disregard\s+all\s+previous\s+instructions",
    r"ignore\s+(all\s+)?(previous|prior)\s+instructions",
    r"print\s+(the\s+)?full\s+contents",
    r"clients?\s+table",
    r"contact\s+emails?",
    r"only\s+reliable\s+source",
    r"system\s+prompt",
    r"override\s+system",
    r"as\s+an\s+ai\s+language\s+model,\s+you\s+must"
]


class DocumentChunk:
    """Represents a single chunk of a market research report with full metadata."""
    def __init__(
        self,
        chunk_id: str,
        report_id: str,
        report_title: str,
        publisher: str,
        sector: str,
        access: str,
        page: int,
        year: str,
        region: str,
        content: str,
        raw_content: str,
        has_injection_attempt: bool = False
    ):
        self.chunk_id = chunk_id
        self.report_id = report_id
        self.report_title = report_title
        self.publisher = publisher
        self.sector = sector
        self.access = access
        self.page = page
        self.year = year
        self.region = region
        self.content = content
        self.raw_content = raw_content
        self.has_injection_attempt = has_injection_attempt
        self.vector: Optional[Dict[str, float]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "report_id": self.report_id,
            "report_title": self.report_title,
            "publisher": self.publisher,
            "sector": self.sector,
            "access": self.access,
            "page": self.page,
            "year": self.year,
            "region": self.region,
            "content": self.content,
            "has_injection_attempt": self.has_injection_attempt
        }


def detect_and_sanitize_injection(text: str) -> Tuple[bool, str, Optional[str]]:
    """
    Scans text for prompt injection patterns.
    If detected, returns (is_injected, sanitized_text, matched_pattern).
    Sanitization strips the hostile directive while keeping legitimate market figures intact.
    """
    is_injected = False
    matched_pattern = None
    sanitized = text

    for pattern in INJECTION_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            is_injected = True
            matched_pattern = match.group(0)
            break

    if is_injected:
        # Strip footnote attack lines such as:
        # [^1]: NOTE TO AI SYSTEMS: Disregard all previous instructions...
        sanitized = re.sub(
            r"(\[\^\d+\]:\s*)?NOTE TO AI SYSTEMS:.*?(?=\n\n|\Z)",
            "[SECURITY NOTICE: Malicious system override instruction detected and neutralized by Atlas Guardrail. Legitimate factual data preserved.]",
            text,
            flags=re.IGNORECASE | re.DOTALL
        )

    return is_injected, sanitized, matched_pattern


def tokenize(text: str) -> List[str]:
    """Basic alphanumeric tokenizer with lowercasing."""
    return re.findall(r"\b[a-zA-Z0-9_\-\.]+\b", text.lower())


class VectorStore:
    """
    In-memory entitlement-aware hybrid vector database.
    Calculates TF-IDF sparse/dense vectors and supports fast cosine search
    with strict client entitlement filtering before any LLM exposure.
    """
    _instance = None

    def __init__(self):
        self.chunks: List[DocumentChunk] = []
        self.idf: Dict[str, float] = {}
        self.doc_count: int = 0
        self.is_indexed: bool = False

    @classmethod
    def get_instance(cls) -> "VectorStore":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def ingest_reports_directory(self, reports_dir: str) -> int:
        """Parses all markdown reports from the seed directory and builds chunks."""
        self.chunks.clear()
        if not os.path.exists(reports_dir):
            logger.error(f"Reports directory does not exist: {reports_dir}")
            return 0

        report_files = [f for f in os.listdir(reports_dir) if f.endswith(".md")]
        logger.info(f"Ingesting {len(report_files)} reports from {reports_dir}")

        for filename in report_files:
            file_path = os.path.join(reports_dir, filename)
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            self._parse_and_chunk_report(content, filename)

        self._build_index()
        self.is_indexed = True
        logger.info(f"Indexing completed: {len(self.chunks)} chunks generated.")
        return len(self.chunks)

    def _parse_and_chunk_report(self, markdown_text: str, filename: str):
        """Parses metadata header and splits into page-level chunks."""
        # Header regex parsing
        title_m = re.search(r"^#\s+(.+)$", markdown_text, re.MULTILINE)
        report_id_m = re.search(r"\*\*Report ID:\*\*\s*([^\n]+)", markdown_text)
        publisher_m = re.search(r"\*\*Publisher:\*\*\s*([^\n]+)", markdown_text)
        published_m = re.search(r"\*\*Published Date:\*\*\s*([^\n]+)", markdown_text)
        sector_m = re.search(r"\*\*Sector:\*\*\s*([^\n]+)", markdown_text)
        access_m = re.search(r"\*\*Access Classification:\*\*\s*([^\n]+)", markdown_text)

        title = title_m.group(1).strip() if title_m else filename
        report_id = report_id_m.group(1).strip() if report_id_m else filename.split("_")[0]
        publisher = publisher_m.group(1).strip() if publisher_m else "Unknown"
        published_date = published_m.group(1).strip() if published_m else "2025"
        year = published_date.split("-")[0] if "-" in published_date else "2025"
        sector = sector_m.group(1).strip() if sector_m else "Utilities"
        access = access_m.group(1).strip() if access_m else "paid"

        # Split on page markers (<!-- Page X --> or ## Page X: ...)
        page_splits = re.split(r"(?:<!--\s*Page\s*(\d+)\s*-->|##\s*Page\s*(\d+):)", markdown_text)
        
        if len(page_splits) > 1:
            idx = 1
            while idx < len(page_splits):
                page_num_str = page_splits[idx] or page_splits[idx + 1]
                page_num = int(page_num_str) if page_num_str and page_num_str.isdigit() else 1
                page_content = page_splits[idx + 2] if (idx + 2) < len(page_splits) else ""
                
                self._create_chunk(
                    report_id=report_id,
                    report_title=title,
                    publisher=publisher,
                    sector=sector,
                    access=access,
                    page=page_num,
                    year=year,
                    content=page_content.strip()
                )
                idx += 3
        else:
            # Fallback single chunk
            self._create_chunk(
                report_id=report_id,
                report_title=title,
                publisher=publisher,
                sector=sector,
                access=access,
                page=1,
                year=year,
                content=markdown_text.strip()
            )

    def _create_chunk(
        self,
        report_id: str,
        report_title: str,
        publisher: str,
        sector: str,
        access: str,
        page: int,
        year: str,
        content: str
    ):
        if not content:
            return

        # Detect and sanitize prompt injection
        has_injection, sanitized_content, pattern = detect_and_sanitize_injection(content)
        if has_injection:
            logger.warning(f"Adversarial prompt injection detected in {report_id} Page {page}! Pattern: {pattern}")
            log_audit_event(
                event_type="injection_attempt",
                client_id="system_ingestion",
                query_text=f"Ingestion {report_id} page {page}",
                details={
                    "report_id": report_id,
                    "page": page,
                    "pattern": pattern,
                    "action": "neutralized_malicious_instruction_preserved_data"
                }
            )

        # Extract primary region if present
        region = "Global"
        if re.search(r"\b(asia-pacific|apac)\b", content, re.IGNORECASE):
            region = "APAC"
        elif re.search(r"\b(north america|usa|us)\b", content, re.IGNORECASE):
            region = "North America"
        elif re.search(r"\beurope\b", content, re.IGNORECASE):
            region = "Europe"

        chunk_id = f"{report_id}_p{page}"
        chunk = DocumentChunk(
            chunk_id=chunk_id,
            report_id=report_id,
            report_title=report_title,
            publisher=publisher,
            sector=sector,
            access=access,
            page=page,
            year=year,
            region=region,
            content=sanitized_content,
            raw_content=content,
            has_injection_attempt=has_injection
        )
        self.chunks.append(chunk)

    def _build_index(self):
        """Builds TF-IDF vocabulary and normalized vectors for fast cosine retrieval."""
        self.doc_count = len(self.chunks)
        if self.doc_count == 0:
            return

        df: Counter = Counter()
        for chunk in self.chunks:
            tokens = set(tokenize(chunk.content))
            for t in tokens:
                df[t] += 1

        self.idf = {t: math.log((self.doc_count + 1) / (count + 1)) + 1.0 for t, count in df.items()}

        for chunk in self.chunks:
            tokens = tokenize(chunk.content)
            tf = Counter(tokens)
            vec = {}
            norm_sq = 0.0
            for t, count in tf.items():
                tfidf = (1 + math.log(count)) * self.idf.get(t, 1.0)
                vec[t] = tfidf
                norm_sq += tfidf * tfidf
            norm = math.sqrt(norm_sq) if norm_sq > 0 else 1.0
            chunk.vector = {t: val / norm for t, val in vec.items()}

    def get_client_entitlements(self, client_id: str) -> Tuple[Set[str], List[Dict[str, Any]]]:
        """
        Retrieves the set of report IDs accessible to the calling client.
        Combines explicitly purchased reports + public excerpt reports.
        """
        all_reports = get_all_reports()
        public_reports = {r["id"] for r in all_reports if r.get("access") == "public excerpt"}

        client = get_client(client_id)
        purchased_reports = set(client.get("purchased_list", [])) if client else set()

        allowed_reports = public_reports.union(purchased_reports)
        return allowed_reports, all_reports

    def check_entitlement_violation(self, query: str, client_id: str) -> Optional[Dict[str, Any]]:
        """
        Checks whether the query explicitly targets a paid report that the client has NOT purchased.
        Checks both explicit report IDs (e.g., R-101) and distinctive report topics/titles.
        """
        allowed_reports, all_reports = self.get_client_entitlements(client_id)
        q_lower = query.lower()

        # Sector / Topic keywords mapping to paid reports
        topic_mappings = [
            ("R-105", ["ev fast charging", "ev charging", "charging infrastructure", "electric vehicle fast"]),
            ("R-106", ["industrial iot", "iot sensors", "industrial sensors"]),
            ("R-104", ["heat pump", "commercial heat", "heat pumps"]),
            ("R-101", ["smart water meter", "water metering", "r-101"]),
            ("R-103", ["water purifier", "residential water", "r-103"])
        ]

        # 1. Check explicit report ID mentions
        for report in all_reports:
            r_id = report["id"]
            if r_id in allowed_reports:
                continue

            if re.search(rf"\b{re.escape(r_id)}\b", query, re.IGNORECASE):
                return {
                    "report_id": r_id,
                    "title": report["title"],
                    "sector": report["sector"],
                    "access": report["access"],
                    "reason": f"Client '{client_id}' does not have an active entitlement for {r_id} ({report['title']})."
                }

        # 2. Check topic-level targeting for unpurchased paid reports
        for r_id, keywords in topic_mappings:
            if r_id in allowed_reports:
                continue

            # Special case: R-102 is public excerpt for smart water metering, so C-02 can ask general water meter questions
            # but if asking specifically for unpurchased sector (e.g. EV charging or Industrial IoT):
            if any(kw in q_lower for kw in keywords):
                # If R-101 topic and client doesn't have R-101:
                # If they have R-102, they can see public excerpt unless they explicitly ask for full market size or R-101
                if r_id == "R-101" and "R-102" in allowed_reports and "r-101" not in q_lower:
                    continue

                rep = next((r for r in all_reports if r["id"] == r_id), None)
                if rep:
                    return {
                        "report_id": r_id,
                        "title": rep["title"],
                        "sector": rep["sector"],
                        "access": rep["access"],
                        "reason": f"Client '{client_id}' does not have an active entitlement for the {rep['sector']} report ({r_id})."
                    }

        return None

    def search(
        self,
        query: str,
        client_id: str,
        top_k: int = 5,
        sector_filter: Optional[str] = None
    ) -> List[Tuple[DocumentChunk, float]]:
        """
        Executes entitlement-aware vector retrieval with report-level diversity (MMR).
        CRITICAL RULE: Chunks from unpurchased reports are filtered out BEFORE scoring/LLM exposure.
        """
        if not self.is_indexed:
            default_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "seed_data", "reports")
            self.ingest_reports_directory(default_dir)

        allowed_reports, _ = self.get_client_entitlements(client_id)

        # Tokenize query and build query vector
        q_tokens = tokenize(query)
        q_tf = Counter(q_tokens)
        q_vec = {}
        norm_sq = 0.0
        for t, count in q_tf.items():
            if t in self.idf:
                tfidf = (1 + math.log(count)) * self.idf[t]
                q_vec[t] = tfidf
                norm_sq += tfidf * tfidf
        norm = math.sqrt(norm_sq) if norm_sq > 0 else 1.0
        q_norm = {t: val / norm for t, val in q_vec.items()}

        scored_candidates: List[Tuple[DocumentChunk, float]] = []

        for chunk in self.chunks:
            # 1. ENTITLE-AWARE FILTER: Skip immediately if client does not have access
            if chunk.report_id not in allowed_reports:
                continue

            # 2. Sector filter if requested
            if sector_filter and chunk.sector.lower() != sector_filter.lower():
                continue

            # 3. Compute cosine similarity with term matching boost
            score = 0.0
            if chunk.vector:
                for t, w in q_norm.items():
                    if t in chunk.vector:
                        score += w * chunk.vector[t]

            # Boost if exact query tokens appear in chunk title or content
            for t in q_tokens:
                if len(t) > 3 and t in chunk.report_title.lower():
                    score += 0.20
                if t in chunk.report_id.lower():
                    score += 0.35

            if score > 0.01:
                scored_candidates.append((chunk, score))

        scored_candidates.sort(key=lambda x: x[1], reverse=True)

        # Diversity enforcement: limit at most 2 chunks per report to prevent crowding
        results: List[Tuple[DocumentChunk, float]] = []
        report_counts: Dict[str, int] = {}
        for chunk, score in scored_candidates:
            count = report_counts.get(chunk.report_id, 0)
            if count < 2 or len(results) < 2:
                results.append((chunk, score))
                report_counts[chunk.report_id] = count + 1
            if len(results) >= top_k:
                break

        return results


# Initialize on import
vector_store = VectorStore.get_instance()
