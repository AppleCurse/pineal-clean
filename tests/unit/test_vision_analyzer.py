import pytest
from agent_core.services.vision_analyzer import VisionAnalyzer, VisualEvidence

@pytest.mark.asyncio
async def test_analyze_images_empty_invalid_urls():
    analyzer = VisionAnalyzer(llm_gateway=None)

    # Test with empty list
    result_empty = await analyzer.analyze_images([])
    assert isinstance(result_empty, VisualEvidence)
    assert result_empty.detected_objects == []
    assert result_empty.environment_and_places == []
    assert result_empty.aesthetic_style == "Görsel bulunamadı"
    assert result_empty.activity_signals == []
    assert result_empty.visual_evidence_summary == "İncelenecek fotoğraf verisi yok."
    assert result_empty.confidence == 0.2

    # Test with invalid items
    result_invalid = await analyzer.analyze_images(["not_a_url", 123, None, "ftp://example.com/image.jpg"])
    assert isinstance(result_invalid, VisualEvidence)
    assert result_invalid.detected_objects == []
    assert result_invalid.environment_and_places == []
    assert result_invalid.aesthetic_style == "Görsel bulunamadı"
    assert result_invalid.activity_signals == []
    assert result_invalid.visual_evidence_summary == "İncelenecek fotoğraf verisi yok."
    assert result_invalid.confidence == 0.2
