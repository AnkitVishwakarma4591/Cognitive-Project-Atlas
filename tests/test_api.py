"""
API Integration Tests for FastAPI Service.
Tests:
- GET /health
- POST /chat
- POST /ingest
- GET /escalations
- POST /feedback
- GET /reports
"""
import pytest
from fastapi.testclient import TestClient
from src.main import app

client = TestClient(app)


def test_health_endpoint():
    """Validates /health endpoint status and vector chunk counts."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "database" in data
    assert data["indexed_chunks"] > 0


def test_chat_endpoint_valid():
    """Validates POST /chat endpoint with valid request payload."""
    payload = {
        "client_id": "C-01",
        "question": "What will the APAC smart water meter market be worth in 2030?"
    }
    response = client.post("/chat", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "answer" in data
    assert "citations" in data
    assert "confidence" in data
    assert "derived_values" in data
    assert len(data["derived_values"]) > 0


def test_chat_endpoint_validation_error():
    """Validates POST /chat rejects empty client_id or question."""
    response = client.post("/chat", json={"client_id": "", "question": ""})
    assert response.status_code == 422


def test_escalations_endpoint():
    """Validates GET /escalations retrieves list of tickets."""
    response = client.get("/escalations")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


def test_reports_catalog_endpoint():
    """Validates GET /reports lists syndicated catalog."""
    response = client.get("/reports")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 6
    assert any(r["id"] == "R-101" for r in data)


def test_feedback_endpoint():
    """Validates POST /feedback records thumbs-up rating."""
    payload = {
        "conversation_id": 1,
        "rating": "up",
        "comments": "Very detailed citations."
    }
    response = client.post("/feedback", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
