
import asyncio
import aiohttp
import json
from typing import List, Dict, Any

class FetchUnavailable(RuntimeError):
    """Raised after the bounded ALF fetch retry budget is exhausted."""


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

    async def stealth_fetch(self, url: str, profile_id: int = 0, max_attempts: int = 3) -> str:
        if not self.profiles:
            raise ValueError("Yüklü tarayıcı profili yok.")
        if max_attempts < 1:
            raise ValueError("max_attempts en az 1 olmalı.")

        errors = []
        session = await self._get_session()
        for attempt in range(max_attempts):
            profile = self.profiles[(profile_id + attempt) % len(self.profiles)]
            try:
                async with session.get(
                    url,
                    headers=self._build_headers(profile),
                    proxy=self._get_next_proxy(),
                    timeout=aiohttp.ClientTimeout(total=15),
                ) as response:
                    if response.status == 200:
                        return await response.text()
                    errors.append(f"HTTP_{response.status}")
            except aiohttp.ClientError as exc:
                errors.append(type(exc).__name__)
            except TimeoutError:
                errors.append("TIMEOUT")

            if attempt + 1 < max_attempts:
                await asyncio.sleep(0.1 * (attempt + 1))

        raise FetchUnavailable(f"ALF fetch unavailable after {max_attempts} attempts: {', '.join(errors)}")

    async def close(self) -> None:
        if self.session is not None and not self.session.closed:
            await self.session.close()

