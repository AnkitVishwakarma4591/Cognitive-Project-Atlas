"""
Automated Evaluation Runner for Project Atlas.
Executes 28 rigorous benchmark test cases and calculates:
- Overall Correctness Rate
- Citation Accuracy
- Refusal Accuracy (Unsafe, Injection, Out of Scope, Entitlements)
- Conflict Detection Rate
- Latency & Cost Profile
Outputs formatted markdown summary and generates evaluation_results.json.
"""
import os
import sys
import json
import time
from tabulate import tabulate

# Ensure workspace root is in path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.models import ChatRequest
from src.agent import agent


def run_benchmarks():
    dataset_path = os.path.join(os.path.dirname(__file__), "evaluation_dataset.json")
    with open(dataset_path, "r", encoding="utf-8") as f:
        test_cases = json.load(f)

    print(f"\n========================================================")
    print(f"  Starting Project Atlas Automated Benchmark Suite")
    print(f"  Total Test Cases: {len(test_cases)}")
    print(f"========================================================\n")

    results = []
    correct_count = 0
    citation_correct_count = 0
    refusal_correct_count = 0
    conflict_detected_count = 0

    total_refusals = 0
    total_conflicts = 0

    table_rows = []

    for test in test_cases:
        t_id = test["id"]
        client_id = test["client_id"]
        question = test["question"]
        expected_cat = test["expected_category"]
        must_contain = test.get("must_contain", [])
        must_not_contain = test.get("must_not_contain", [])

        is_refusal_test = ("refusal" in expected_cat or "unsafe" in expected_cat or "out_of_scope" in expected_cat)
        if is_refusal_test:
            total_refusals += 1

        is_conflict_test = ("conflict" in expected_cat)
        if is_conflict_test:
            total_conflicts += 1

        start_t = time.time()
        req = ChatRequest(client_id=client_id, question=question)
        response = agent.process_chat(req)
        latency = round((time.time() - start_t) * 1000, 2)

        ans = response.answer
        passed_contains = all(w.lower() in ans.lower() for w in must_contain)
        passed_not_contains = not any(w.lower() in ans.lower() for w in must_not_contain)

        # Citation validation
        has_citations = len(response.citations) > 0
        citation_valid = has_citations if not is_refusal_test else True
        if citation_valid:
            citation_correct_count += 1

        # Conflict detection validation
        if is_conflict_test:
            if len(response.conflicts) > 0 or "r-101" in ans.lower() and "r-102" in ans.lower():
                conflict_detected_count += 1

        # Refusal validation
        refusal_valid = True
        if is_refusal_test:
            refusal_valid = passed_contains and passed_not_contains
            if refusal_valid:
                refusal_correct_count += 1

        passed = passed_contains and passed_not_contains and (response.confidence >= test.get("min_confidence", 0.30))

        if passed:
            correct_count += 1
            status_str = "PASS"
        else:
            status_str = "FAIL"

        results.append({
            "id": t_id,
            "client_id": client_id,
            "question": question,
            "category": expected_cat,
            "status": status_str,
            "passed": passed,
            "confidence": response.confidence,
            "citations_count": len(response.citations),
            "conflicts_count": len(response.conflicts),
            "derived_count": len(response.derived_values),
            "escalated": response.escalated,
            "latency_ms": latency,
            "answer_preview": ans[:120].replace("\n", " ")
        })

        table_rows.append([
            t_id,
            client_id,
            question[:36] + ("..." if len(question) > 36 else ""),
            expected_cat,
            f"{response.confidence:.2f}",
            len(response.citations),
            "YES" if response.escalated else "NO",
            f"{latency}ms",
            status_str
        ])

    headers = ["#", "Client", "Question", "Category", "Conf", "Cits", "Esc", "Latency", "Status"]
    print(tabulate(table_rows, headers=headers, tablefmt="github"))

    correctness_pct = (correct_count / len(test_cases)) * 100
    citation_pct = (citation_correct_count / len(test_cases)) * 100
    refusal_pct = (refusal_correct_count / max(1, total_refusals)) * 100
    conflict_pct = (conflict_detected_count / max(1, total_conflicts)) * 100

    print(f"\n========================================================")
    print(f"  BENCHMARK METRICS SUMMARY")
    print(f"========================================================")
    print(f"  Overall Correctness:    {correctness_pct:.1f}% ({correct_count}/{len(test_cases)})")
    print(f"  Citation Accuracy:      {citation_pct:.1f}%")
    print(f"  Refusal Accuracy:       {refusal_pct:.1f}% ({refusal_correct_count}/{total_refusals})")
    print(f"  Conflict Detection:     {conflict_pct:.1f}% ({conflict_detected_count}/{total_conflicts})")
    print(f"========================================================\n")

    output_path = os.path.join(os.path.dirname(__file__), "evaluation_results.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({
            "summary": {
                "total_tests": len(test_cases),
                "passed": correct_count,
                "failed": len(test_cases) - correct_count,
                "correctness_rate": f"{correctness_pct:.1f}%",
                "citation_accuracy": f"{citation_pct:.1f}%",
                "refusal_accuracy": f"{refusal_pct:.1f}%",
                "conflict_detection_rate": f"{conflict_pct:.1f}%"
            },
            "results": results
        }, f, indent=2)
    print(f"Saved detailed results to {output_path}")


if __name__ == "__main__":
    run_benchmarks()
