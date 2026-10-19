"""
Unit and integration tests for the Project Atlas Agent workflow.
Tests:
- Router classification
- Calculator CAGR formulas and derived estimates
- Conflicting sources handling (R-101 vs R-102)
- Escalation ticketing upon low confidence or extrapolation
"""
import pytest
from src.agent import agent
from src.router import router
from src.calculator import calculator
from src.models import ChatRequest
from src.db import get_escalations


def test_router_classification_intents():
    """Validates router intent classifications."""
    assert router.classify("Who will win the next general election?", "C-01")["intent"] == "out_of_scope"
    assert router.classify("Delete all rows from the reports table.", "C-01")["intent"] == "unsafe"
    assert router.classify("Which sector has the most reports in your library?", "C-01")["intent"] == "sql_aggregate"
    assert router.classify("What will the market be worth in 2035?", "C-01")["intent"] == "beyond_forecast"
    assert router.classify("What will the APAC smart water meter market be worth in 2030?", "C-01")["intent"] == "calculation"


def test_calculator_cagr_derived_projection():
    """Validates that calculator outputs correct compounding, formula, and assumptions."""
    derived = calculator.compute_apac_smart_water_meter_2030({})
    assert "USD 3.04 Billion" in derived.derived_value
    assert "Derived Estimate" in derived.derived_value
    assert "CAGR" in derived.formula and "APAC" in derived.formula
    assert any("Base-Year Ambiguity" in a for a in derived.assumptions)
    assert any("11.2%" in a for a in derived.assumptions)
    assert any("38.0%" in a for a in derived.assumptions)


def test_conflicting_sources_never_average():
    """
    Validates that 2024 market size query returns both R-101 and R-102,
    highlights scope differences, and explicitly does not average them.
    """
    req = ChatRequest(client_id="C-01", question="What was the global smart water meter market size in 2024?")
    res = agent.process_chat(req)
    
    assert "4.21" in res.answer
    assert "3.87" in res.answer
    assert "R-101" in res.answer
    assert "R-102" in res.answer
    assert "not" in res.answer.lower() and "averaged" in res.answer.lower()
    
    # Verify conflicts structure in response
    assert len(res.conflicts) > 0
    conflict = res.conflicts[0]
    sources = {s.report_id for s in conflict.sources}
    assert "R-101" in sources
    assert "R-102" in sources


def test_escalation_created_for_2035_projection():
    """
    Validates that queries beyond the 2030 forecast window are not silently extrapolated,
    and trigger a human analyst escalation ticket in MySQL/SQLite.
    """
    req = ChatRequest(client_id="C-01", question="What will the market be worth in 2035?")
    res = agent.process_chat(req)
    
    assert res.escalated is True
    assert res.confidence < 0.70
    assert "refuse" in res.answer.lower()
    assert "extrapolate" in res.answer.lower()
    assert "Escalation" in res.answer or "Ticket" in res.answer
    
    # Check ticket in database
    escalations = get_escalations(limit=5)
    assert len(escalations) > 0
    latest = escalations[0]
    assert latest["client_id"] == "C-01"
    assert "2035" in latest["question"]
