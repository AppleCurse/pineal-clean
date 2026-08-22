import pytest
from agent_core.aspasia.psychological_profiler import PsychologicalDecomposer, PsychologicalProfile, AttachmentStyle

@pytest.fixture
def decomposer():
    return PsychologicalDecomposer()

def test_decompose_anxious_abandonment(decomposer):
    data = {
        'bio': 'yalnız bir ruh',
        'posts': ['terk edildim', 'sensiz yapamam', 'neden bekle dedim?']
    }
    profile = decomposer.decompose(data)
    
    assert profile.attachment == AttachmentStyle.ANXIOUS
    assert profile.core_wound == 'abandonment'
    assert profile.fear == 'Terk edilme'
    assert profile.emotional_need == 'Güvenlik ve süreklilik'

def test_decompose_avoidant_betrayal(decomposer):
    data = {
        'bio': 'özgürlük benim işim',
        'posts': ['mesafe iyidir', 'kimseye güvenmem', 'yalan dolu', 'aldattı herkes']
    }
    profile = decomposer.decompose(data)
    
    assert profile.attachment == AttachmentStyle.AVOIDANT
    assert profile.core_wound == 'betrayal'
    assert profile.fear == 'İhanet'

def test_decompose_narcissistic_shame(decomposer):
    data = {
        'posts': ['ben mükemmel biriyim', 'eşsiz', 'utandım', 'yetersiz hissettim', 'kendim']
    }
    profile = decomposer.decompose(data)
    
    assert profile.dark_triad['narcissism'] > 0.1
    assert profile.core_wound == 'shame'
    assert profile.fear == 'Aşağılanma'
    assert profile.attention_seeking > 0.0

def test_exploitability_calculation(decomposer):
    # High exploitability: narcissism + anxious + abandonment
    data = {
        'posts': ['ben mükemmel eşsiz yalnız terk bekle']
    }
    profile = decomposer.decompose(data)
    assert profile.exploitability >= 0.5
