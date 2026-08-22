import pytest
import asyncio
from agent_core.scraper.instagram_ghost import InstagramGhostScraper, InsufficientEvidenceError

class MockPageFail:
    def __init__(self, fails=3):
        self.fails = fails
        self.attempts = 0
        
    async def goto(self, url, wait_until, timeout):
        self.attempts += 1
        if self.attempts <= self.fails:
            raise Exception("Mocked Network timeout")
            
    async def content(self):
        return "<html>mock</html>"

class MockPagePermanentFail:
    def __init__(self):
        self.attempts = 0
        
    async def goto(self, url, wait_until, timeout):
        self.attempts += 1
        raise Exception("TargetPrivateError: Account is private")


@pytest.mark.asyncio
async def test_scraper_retry_success():
    scraper = InstagramGhostScraper()
    # Fails 2 times, succeeds on 3rd
    page = MockPageFail(fails=2)
    
    # Needs to raise InsufficientEvidenceError because the mock html doesn't have JSON,
    # but the retry mechanism itself should pass and it should reach _extract_from_html.
    # So we expect the error message to be about JSON not found, NOT Playwright.
    with pytest.raises(InsufficientEvidenceError) as exc:
        await scraper.scrape_async("test_user", playwright_page=page)
        
    assert "JSON bulunamadı" in str(exc.value)
    assert page.attempts == 3

@pytest.mark.asyncio
async def test_scraper_retry_failure():
    scraper = InstagramGhostScraper()
    # Fails 4 times (always fails)
    page = MockPageFail(fails=4)
    
    with pytest.raises(InsufficientEvidenceError) as exc:
        await scraper.scrape_async("test_user", playwright_page=page)
        
    assert "transient hatas" in str(exc.value)
    assert page.attempts == 3  # Max retries

@pytest.mark.asyncio
async def test_scraper_permanent_failure():
    scraper = InstagramGhostScraper()
    page = MockPagePermanentFail()
    
    with pytest.raises(InsufficientEvidenceError) as exc:
        await scraper.scrape_async("test_user", playwright_page=page)
        
    assert "kalıcı hatası" in str(exc.value)
    assert page.attempts == 1  # Should not retry
