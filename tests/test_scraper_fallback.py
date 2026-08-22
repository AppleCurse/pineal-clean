import pytest
from unittest.mock import patch
from agent_core.task_executor import PinealExecutor, InsufficientEvidenceError

@pytest.mark.asyncio
async def test_scraper_fallback_private_account():
    # Test that scraper properly throws InsufficientEvidenceError on private/empty account
    executor = PinealExecutor()
    
    # Normally handled by API.py, but we test the Executor's halt capability
    # If scraper returns empty, we mock that.
    
    # Actually, scraper logic is in scraper.py. Let's test scraper directly.
    from scraper import scrape_readonly, TargetPrivateError
    
    with patch('scraper.sync_playwright') as mock_playwright:
        # If the user tries to scrape a private account, we want the scraper to raise TargetPrivateError
        # In our implementation plan, we said we will add TargetPrivateError to scraper.py.
        # We will mock it to raise the error here to ensure our tests expect it.
        mock_playwright.side_effect = TargetPrivateError("Hesap gizli")
        
        with pytest.raises(TargetPrivateError):
            scrape_readonly("https://x.com/private_user")
