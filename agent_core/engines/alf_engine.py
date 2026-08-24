
import aiohttp
import json
from typing import List, Dict, Any

class ALF_Engine:
    def __init__(self, profiles_path: str = "browser_profiles.json"):
        self.profiles_path = profiles_path
        self.profiles = self._load_profiles(profiles_path)
        self.session = None

    async def _get_session(self):
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session

    def _load_profiles(self, path: str) -> List[Dict[str, Any]]:
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            return [{
                "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "language": "en-US,en;q=0.9",
                "proxy": None
            }]

    def _get_next_proxy(self) -> str | None:
        return None

    def _build_headers(self, profile: dict) -> dict:
        return {
            "User-Agent": profile.get("user_agent", "Mozilla/5.0"),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": profile.get("language", "en-US,en;q=0.5"),
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }

    async def stealth_fetch(self, url: str, profile_id: int = 0) -> str:
        if not self.profiles:
            raise ValueError("Yüklü tarayıcı profili yok.")
        profile = self.profiles[profile_id % len(self.profiles)]
        proxy = self._get_next_proxy()
        headers = self._build_headers(profile)
        session = await self._get_session()
        try:
            async with session.get(url, headers=headers, proxy=proxy, timeout=aiohttp.ClientTimeout(total=15)) as response:
                if response.status == 200:
                    return await response.text()
                else:
                    return await self.stealth_fetch(url, profile_id + 1)
        except Exception:
            return await self.stealth_fetch(url, profile_id + 1)

