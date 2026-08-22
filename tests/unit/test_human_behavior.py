import pytest
from unittest.mock import MagicMock, AsyncMock, patch
import cv2
import numpy as np
from agent_core.agents.human_behavior import HumanBehaviorAnalyzer, MicroSignal

def test_linguistic_forensics():
    analyzer = HumanBehaviorAnalyzer()
    bio = "Blogger. Sadece pozitif düşünce."
    posts = ["Her şey mükemmel oldu.", "Bu yapıldı ve bitti.", "Herkes mutlu edildi. Her şey oldu.", "Ben 😊 😊 😊 😊 😊 😊 😊 😊"]
    
    result = analyzer._linguistic_forensics(bio, posts)
    signals = result['signals']
    
    assert any(s.signal_type == "authentic" and "emoji" in s.location for s in signals)
    assert any(s.signal_type == "contradiction" and "passive_voice" in s.location for s in signals)
    assert any(s.signal_type == "defense" and "linguistic" in s.location for s in signals)
    assert result['claimed_identity'] == "Blogger"

def test_temporal_forensics():
    analyzer = HumanBehaviorAnalyzer()
    
    # 4 posts late night, 1 post day -> > 30% late night
    post_times = ["01:00", "03:30", "23:45", "02:15", "14:00", "invalid"]
    signals = analyzer._temporal_forensics(post_times)
    
    assert len(signals) == 1
    assert signals[0].signal_type == "insomnia_isolation"
    
    post_times_safe = ["10:00", "14:00", "15:00"]
    signals_safe = analyzer._temporal_forensics(post_times_safe)
    assert len(signals_safe) == 0

def test_mine_contradictions():
    analyzer = HumanBehaviorAnalyzer()
    
    visual_signals = [
        MicroSignal(signal_type="tension", confidence=0.8, location="a", evidence="e", psychological_weight=0.5)
    ]
    
    text_signals = {
        'signals': [
            MicroSignal(signal_type="defense", confidence=0.8, location="b", evidence="e", psychological_weight=0.5),
            MicroSignal(signal_type="contradiction", confidence=0.8, location="c", evidence="evid", psychological_weight=0.8)
        ]
    }
    
    contradictions = analyzer._mine_contradictions(visual_signals, text_signals)
    
    # Should find mismatch and linguistic_contradiction
    assert len(contradictions) == 2
    assert any(c['type'] == "visual_linguistic_mismatch" for c in contradictions)
    assert any(c['type'] == "linguistic_contradiction" for c in contradictions)

def test_calculate_achilles():
    analyzer = HumanBehaviorAnalyzer()
    contradictions = [{}, {}]
    text_signals = {
        'signals': [
            MicroSignal(signal_type="x", confidence=0.8, location="b", evidence="e", psychological_weight=0.5)
        ]
    }
    
    score = analyzer._calculate_achilles(contradictions, text_signals)
    # 2 * 15 + 0.5 * 10 = 35
    assert score == 35.0

def test_identify_wound_as_bridge():
    analyzer = HumanBehaviorAnalyzer()
    
    res = analyzer._identify_wound_as_bridge([], {})
    assert res['type'] == 'unknown'
    
    contradictions = [{'type': 'social_vs_alone', 'weight': 10}]
    res2 = analyzer._identify_wound_as_bridge(contradictions, {})
    assert res2['type'] == 'yalnizlik_köprüsü'

def test_calculate_resonance_potential():
    analyzer = HumanBehaviorAnalyzer()
    wound = {'defense_strength': 0.6}
    input_data = {'user_authenticity_score': 0.8}
    
    score = analyzer._calculate_resonance_potential(wound, input_data)
    # target_openness = 0.4
    # 0.8 * 0.4 = 0.32, sqrt = ~0.565
    assert abs(score - 0.565) < 0.01

@patch('cv2.imread')
@patch('cv2.Canny')
@patch('cv2.Laplacian')
def test_analyze_visual_micro(mock_laplacian, mock_canny, mock_imread):
    analyzer = HumanBehaviorAnalyzer()
    
    fake_img = np.zeros((100, 100, 3), dtype=np.uint8)
    mock_imread.return_value = fake_img
    
    # Mock Canny to return array with high mean (tension)
    mock_canny.return_value = np.full((30, 60), 100, dtype=np.uint8)
    
    # Mock Laplacian to return object with var() < 100 (void)
    mock_var = MagicMock()
    mock_var.var.return_value = 50.0
    mock_laplacian.return_value = mock_var
    
    signals = analyzer._analyze_visual_micro(["dummy.jpg"])
    
    assert len(signals) == 2
    assert any(s.signal_type == "tension" for s in signals)
    assert any(s.signal_type == "void" for s in signals)

@pytest.mark.asyncio
async def test_execute():
    analyzer = HumanBehaviorAnalyzer()
    input_data = {
        'target_profile': {'bio': 'test', 'posts': []},
        'sacred_rules': 'rule'
    }
    
    mock_llm = MagicMock()
    mock_llm.query_json = AsyncMock(return_value="mock_result")
    
    res = await analyzer.execute(input_data, None, mock_llm)
    assert res == "mock_result"
    mock_llm.query_json.assert_called_once()
