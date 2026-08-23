import pytest
import httpx
from agent_core.services.vision_analyzer import VisionAnalyzer

class MockClient:
    def __init__(self, *args, **kwargs):
        pass
    async def __aenter__(self):
        return self
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass
    async def get(self, url, **kwargs):
        request = httpx.Request("GET", url)
        raise httpx.RequestError("Mock network error", request=request)

@pytest.mark.asyncio
async def test_download_and_encode_image_exception_handling(monkeypatch):
    """
    Test that _download_and_encode_image handles network exceptions gracefully
    and returns None instead of propagating the exception.
    """
    # Mock httpx.AsyncClient to return our MockClient that raises RequestError
    monkeypatch.setattr(httpx, "AsyncClient", MockClient)

    analyzer = VisionAnalyzer()

    # Should handle the exception gracefully and return None
    result = await analyzer._download_and_encode_image("https://example.com/image.jpg")

    assert result is None
