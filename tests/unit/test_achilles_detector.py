import pytest
from unittest.mock import MagicMock
from agent_core.aspasia.achilles_detector import AchillesDetector

def test_achilles_detector():
    detector = AchillesDetector()
    
    # Mock profile
    mock_profile = MagicMock()
    mock_profile.core_wound = "abandonment"
    mock_profile.fear = "being ignored"
    
    result = detector.detect(mock_profile, data={})
    
    assert result == {
        "vulnerability": "abandonment",
        "trigger": "being ignored"
    }
