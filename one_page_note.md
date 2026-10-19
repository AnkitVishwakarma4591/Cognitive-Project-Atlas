# What I Would Do With One More Week

**Candidate Note: Project Atlas Future Roadmap**  
**Role:** AI Software Developer (Generative & Agentic AI)  
**Company:** Cognitive Market Research and Consulting (CMR)  

---

If granted one additional week to advance Project Atlas beyond the current working MVP, I would focus on five production-grade enterprise initiatives:

### 1. Hybrid Search with Cross-Encoder Neural Re-Ranking & Embeddings
* **Current Implementation:** Dual TF-IDF/BM25 sparse scoring with cosine vector ranking and report diversity filters.
* **Next Level:** Integrate a dense neural embedding model (`sentence-transformers/all-MiniLM-L6-v2` or `BGE-small-en-v1.5`) backed by an ONNX runtime for ultra-fast local inference without heavy GPU dependencies.
* **Two-Stage Re-ranking:** Introduce a lightweight cross-encoder (`cross-encoder/ms-marco-MiniLM-L-6-v2`) to re-score the top 20 retrieved candidates down to top 4, achieving superior semantic precision on complex phrasing (e.g., distinguishing "hardware supply contracts" from "SaaS platform licensing").

### 2. Native PDF & Multimodal Chart/Table Ingestion Pipeline
* **Current Implementation:** Structured Markdown documents with page breaks and tabular ASCII representations.
* **Next Level:** Productionize a document extraction worker utilizing `unstructured`, `pdfplumber`, or `marker-pdf` combined with vision-capable LLMs (e.g. Gemini 1.5 Flash / Claude 3.5 Sonnet) to ingest raw PDF pages.
* **Visual Table & Chart Extraction:** Convert charts, bar graphs, and infographic exhibits into structured JSON tables with automated bounding box citations. This allows clients to query exhibit charts directly (e.g. *"What was the battery lifespan stated in Exhibit 4.2?"*).

### 3. Real-Time Token Streaming via SSE to the CodeIgniter 3 Portal
* **Current Implementation:** Synchronous JSON responses over HTTP POST, responding in ~300ms.
* **Next Level:** Upgrade `POST /chat` to support Server-Sent Events (`text/event-stream`). In CodeIgniter 3, integrate an EventSource or chunked fetch handler in `chat_view.php` to render tokens with typewriter animations and immediate visual latency under 50ms, improving perceived responsiveness for long analytical syntheses.

### 4. Advanced Graph Checkpointing & Multi-Agent Collaboration (LangGraph)
* **Current Implementation:** Deterministic multi-stage pipeline (Router $\to$ Entitlement Filter $\to$ Calculator $\to$ Critic $\to$ Escalation).
* **Next Level:** Port the pipeline to a stateful LangGraph workflow with SQLite/Redis checkpointing. This enables:
  - Multi-turn conversation state persistence across complex analytic sessions.
  - Human-in-the-loop analyst interventions: When an inquiry is escalated, the senior analyst can edit the draft in an admin UI and release the verified response directly to the client's session.

### 5. Enterprise Observability, Cost Guardrails & SOC2 Compliance
* **Current Implementation:** Local SQLite/MySQL `audit_logs` tracking latency and token cost per request.
* **Next Level:** Integrate open-source LLM observability via **Langfuse** or **OpenTelemetry**. Export tracing spans for every stage (routing decision, SQL generation, vector retrieval, fact-checking).
* **Automated Guardrail Vault:** Implement automated daily PII scanning, tenant isolation testing, and immutable compliance auditing to satisfy SOC2 and GDPR requirements for confidential client data.
