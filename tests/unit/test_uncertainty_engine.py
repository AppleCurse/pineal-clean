import pytest
from pydantic import BaseModel
from agent_core.services.uncertainty_engine import UncertaintyEngine, UncertaintyReport

class DummyResultBaseModel(BaseModel):
    name: str = ""
    evidence: list = []
    confidence: float = 0.8

class DummyResultWithAbsolutes(BaseModel):
    content: str = "kesinlikle eminim"
    confidence: float = 0.98

def test_uncertainty_evaluate_safe():
    engine = UncertaintyEngine()
    result = DummyResultBaseModel(name="test", evidence=[1], confidence=0.8)
    report = engine.evaluate(result, "test_agent")
    
    assert not report.is_suspicious
    assert report.confidence == 0.8

def test_uncertainty_evaluate_empty_list():
    engine = UncertaintyEngine()
    # evidence is empty list
    result = DummyResultBaseModel(name="test", evidence=[], confidence=0.8)
    report = engine.evaluate(result, "test_agent")
    
    # Due to removing the overly aggressive 'any list empty means fail' check,
    # the confidence drops to 0.66 (1 empty field out of 3) but does not trigger suspicious
    assert not report.is_suspicious
    assert abs(report.confidence - 0.666) < 0.01

def test_uncertainty_evaluate_missing_str():
    engine = UncertaintyEngine()
    # string with "bulunamadı" but no "evidence" key to avoid the global regex match
    class DummyNoEvidence(BaseModel):
        name: str = "bulunamadı"
        other_list: list = [1]
        confidence: float = 0.8
    result = DummyNoEvidence()
    report = engine.evaluate(result, "test_agent")
    
    # name is "bulunamadı", which drops data_score. 
    # data_score = 1.0 - (1 / 3) = 0.66. So confidence becomes min(0.8, 0.66) = 0.66.
    assert not report.is_suspicious
    assert abs(report.confidence - 0.666) < 0.01

def test_uncertainty_evaluate_all_empty():
    engine = UncertaintyEngine()
    # all fields empty or not found
    result = DummyResultBaseModel(name="bulunamadı", evidence=[])
    report = engine.evaluate(result, "test_agent")
    
    assert report.is_suspicious
    assert report.confidence == 0.1

def test_uncertainty_evaluate_has_absolutes():
    engine = UncertaintyEngine()
    result = DummyResultWithAbsolutes()
    report = engine.evaluate(result, "test_agent")
    
    assert report.is_suspicious
    assert report.confidence == 0.9
    assert "Halüsinasyon" in report.reason

def test_uncertainty_evaluate_non_pydantic_empty():
    engine = UncertaintyEngine()
    class DummyClass:
        def __str__(self):
            return "evidence bulunamadı"
    
    report = engine.evaluate(DummyClass(), "test_agent")
    assert report.is_suspicious
    assert report.confidence == 0.1
