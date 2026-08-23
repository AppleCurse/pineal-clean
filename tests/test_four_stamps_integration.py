import pytest
import json
from datetime import datetime, timezone
from agent_core.domain.memory_models import TaskSnapshot
from agent_core.services.search_engine import SearchEngine
from backend.api import _send_snapshot, broadcast_result, app

@pytest.mark.asyncio
async def test_snapshot_and_result_four_stamps_serialization():
    snapshot = TaskSnapshot(
        task_id='test_task_stamps',
        status='completed',
        created_at=datetime.now(timezone.utc),
        follower_audit={
            'follower_count': 1000,
            'following_count': 50,
            'verdict': 'healthy',
            'bot_probability': 0.05,
            'evidence': ['Normal oran']
        },
        timing_forensics={
            'night_owl_score': 0.8,
            'peak_utc_hour': 3,
            'tz_offset_hours_likely': 3,
            'pattern_label': 'Gece kusu'
        },
        depth_report={
            'reality_index': 0.85,
            'reality_rationale': 'Kanitlar saglam',
            'reality_findings': [{'topic': 'Muzik', 'observation': 'Produktor', 'evidence_quotes': ['Gece 04:00']}],
            'contradictions': [],
            'essence_one_liner': 'Gercek bir sanatci.',
            'quote_guard': {'checked': 1, 'kept': 1, 'dropped_fake_quote': 0}
        },
        visual_evidence={
            'aesthetic_style': 'Dark',
            'visual_evidence_summary': 'Studio ekipmanlari'
        }
    )

    received_payloads = []
    class FakeWS:
        async def send_text(self, text):
            received_payloads.append(json.loads(text))

    fake_room = {
        'websockets': {FakeWS()},
        'active_tasks': {}
    }

    await _send_snapshot(fake_room, snapshot)
    assert len(received_payloads) == 1
    snap_data = received_payloads[0]
    assert snap_data['type'] == 'snapshot_update'
    assert 'follower_audit' in snap_data
    assert snap_data['follower_audit']['verdict'] == 'healthy'
    assert 'timing_forensics' in snap_data
    assert snap_data['timing_forensics']['night_owl_score'] == 0.8
    assert 'depth_report' in snap_data
    assert snap_data['depth_report']['reality_index'] == 0.85
    assert snap_data['depth_report']['quote_guard']['kept'] == 1
    assert 'visual_evidence' in snap_data
    assert snap_data['visual_evidence']['aesthetic_style'] == 'Dark'

    app.state.rooms = {'client_test': {'queue': None, 'websockets': set(), 'executor': None, 'vault': {}}}
    import asyncio
    queue = asyncio.Queue()
    app.state.rooms['client_test']['queue'] = queue

    broadcast_result('client_test', snapshot)
    kind, res_data = queue.get_nowait()
    assert kind == 'result'
    assert res_data['follower_audit']['verdict'] == 'healthy'
    assert res_data['timing_forensics']['night_owl_score'] == 0.8
    assert res_data['depth_report']['reality_index'] == 0.85
    assert res_data['visual_evidence']['aesthetic_style'] == 'Dark'

def test_searchengine_none_vs_empty_string(monkeypatch):
    monkeypatch.setenv('TAVILY_API_KEY', 'env_tavily')
    monkeypatch.setenv('SERPAPI_API_KEY', 'env_serpapi')
    monkeypatch.setenv('EXA_API_KEY', 'env_exa')

    eng_none = SearchEngine(tavily_key=None, serpapi_key=None, exa_key=None)
    assert eng_none.tavily_key == 'env_tavily'
    assert eng_none.serpapi_key == 'env_serpapi'
    assert eng_none.exa_key == 'env_exa'

    eng_empty = SearchEngine(tavily_key='', serpapi_key='', exa_key='')
    assert eng_empty.tavily_key is None
    assert eng_empty.serpapi_key is None
    assert eng_empty.exa_key is None

    eng_custom = SearchEngine(tavily_key='my_tavily')
    assert eng_custom.tavily_key == 'my_tavily'
    assert eng_custom.serpapi_key == 'env_serpapi'
