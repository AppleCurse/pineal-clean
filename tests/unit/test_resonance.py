import pytest
from agent_core.agents.resonance_calculator import ResonanceCalculator, ResonanceCalculationError

def test_resonance_calculator_normal():
    calc = ResonanceCalculator()
    user_vec = {"depth": 0.8, "energy": 0.5}
    target_vec = {"depth": 0.7, "energy": 0.4}
    
    # Should not raise
    result = calc._cosine_similarity(user_vec, target_vec)
    assert 0.0 < result < 1.0

def test_resonance_calculator_disjoint():
    calc = ResonanceCalculator()
    # No intersecting keys
    user_vec = {"depth": 0.8}
    target_vec = {"energy": 0.4}
    
    result = calc._cosine_similarity(user_vec, target_vec)
    assert result == 0.0  # Valid return for disjoint vectors

def test_resonance_calculator_zero_magnitude():
    calc = ResonanceCalculator()
    user_vec = {"depth": 0.0, "energy": 0.0}
    target_vec = {"depth": 0.7, "energy": 0.4}
    
    with pytest.raises(ResonanceCalculationError) as exc_info:
        calc._cosine_similarity(user_vec, target_vec)
    assert "SIFIR" in str(exc_info.value)

def test_resonance_calculator_malformed():
    calc = ResonanceCalculator()
    user_vec = {}
    target_vec = {"depth": 0.7}
    
    result = calc._cosine_similarity(user_vec, target_vec)
    assert result == 0.0
