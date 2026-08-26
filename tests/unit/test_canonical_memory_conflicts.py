from agent_core.services.canonical_memory import CanonicalMemory


def test_conflicting_claims_are_preserved_and_marked_not_silently_sorted():
    memory = CanonicalMemory()
    evidence = memory._resolve_conflicts(
        [],
        [
            {"agent": "verifier_a", "result": {"claim_text": "Ada is a doctor", "truth_status": "DOĞRULANDI"}},
            {"agent": "verifier_b", "result": {"claim_text": "Ada is a doctor", "truth_status": "YALAN"}},
        ],
    )

    assert len(evidence) == 2
    assert all(item["conflict_status"] == "CONTRADICTED" for item in evidence)
    assert evidence[0]["conflicts_with"] == [1]
    assert evidence[1]["conflicts_with"] == [0]
