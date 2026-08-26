import pytest

from backend.api import IntervenePayload, app, executor_intervene


@pytest.mark.asyncio
async def test_confidence_override_is_audited_but_never_mutates_executor():
    client_id = "intervention_safety"
    app.state.rooms.pop(client_id, None)

    response = await executor_intervene(
        IntervenePayload(client_id=client_id, action_type="OVERRIDE_CONFIDENCE", reason="test")
    )

    room = app.state.rooms[client_id]
    assert response["status"] == "review_required"
    assert room["interventions"][-1]["action_type"] == "OVERRIDE_CONFIDENCE"
    assert not hasattr(room["executor"].uncertainty.evaluate, "__name__") or room["executor"].uncertainty.evaluate.__name__ != "<lambda>"


@pytest.mark.asyncio
async def test_skip_agent_does_not_delete_shared_agent_registry():
    client_id = "intervention_skip_safety"
    app.state.rooms.pop(client_id, None)
    room = app.state.rooms.get(client_id) or __import__("backend.api", fromlist=["get_room"]).get_room(client_id)
    before = set(room["executor"].agents)

    response = await executor_intervene(
        IntervenePayload(client_id=client_id, action_type="SKIP_AGENT", target_agent="mirror_truth")
    )

    assert response["status"] == "review_required"
    assert set(room["executor"].agents) == before
