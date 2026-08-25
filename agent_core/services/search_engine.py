import asyncio
import os
import re
import httpx
from typing import List, Optional
from pydantic import BaseModel, ConfigDict

class SearchResult(BaseModel):
    query: str
    content: str
    source_url: str
    provider: str = "unknown"
    model_config = ConfigDict(extra="forbid")

class SearchEngine:
    """
    3 Kaynaklı Eşzamanlı Arama ve Doğrulama Motoru (Tavily + SerpAPI + Exa + DuckDuckGo).
    """
    def __init__(self, tavily_key: Optional[str] = None, serpapi_key: Optional[str] = None, exa_key: Optional[str] = None):
        self.tavily_key = os.getenv("TAVILY_API_KEY") if tavily_key is None else (tavily_key if tavily_key != "" else None)
        self.serpapi_key = os.getenv("SERPAPI_API_KEY") if serpapi_key is None else (serpapi_key if serpapi_key != "" else None)
        self.exa_key = os.getenv("EXA_API_KEY") if exa_key is None else (exa_key if exa_key != "" else None)

    def set_keys(self, tavily: Optional[str] = None, serpapi: Optional[str] = None, exa: Optional[str] = None):
        if tavily is not None:
            self.tavily_key = tavily if tavily != "" else None
        if serpapi is not None:
            self.serpapi_key = serpapi if serpapi != "" else None
        if exa is not None:
            self.exa_key = exa if exa != "" else None

    async def search(self, query: str, num_results: int = 5) -> List[SearchResult]:
        async with httpx.AsyncClient(timeout=10.0) as client:
            tasks = []
            if self.tavily_key:
                tasks.append(self._search_tavily(query, num_results, client=client))
            if self.serpapi_key:
                tasks.append(self._search_serpapi(query, num_results, client=client))
            if self.exa_key:
                tasks.append(self._search_exa(query, num_results, client=client))

            # Eğer hiç anahtar yoksa ücretsiz DuckDuckGo yedeği devreye girer
            if not tasks:
                tasks.append(self._search_duckduckgo(query, num_results, client=client))

            results_lists = await asyncio.gather(*tasks, return_exceptions=True)
        
        merged: List[SearchResult] = []
        seen_urls = set()
        for res in results_lists:
            if isinstance(res, list):
                for item in res:
                    if item.source_url not in seen_urls:
                        seen_urls.add(item.source_url)
                        merged.append(item)
        return merged[:num_results * 2]

    async def _search_tavily(self, query: str, num_results: int, **kwargs) -> List[SearchResult]:
        url = "https://api.tavily.com/search"
        from agent_core.utils.security import is_safe_url
        if not is_safe_url(url):
            return []
        payload = {"api_key": self.tavily_key, "query": query, "max_results": num_results}
        try:
            if "client" in kwargs and kwargs["client"] is not None:
                res = await kwargs["client"].post(url, json=payload)
            else:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    res = await client.post(url, json=payload)
                if res.status_code == 200:
                    data = res.json()
                    return [
                        SearchResult(query=query, content=r.get("content", ""), source_url=r.get("url", ""), provider="tavily")
                        for r in data.get("results", [])
                    ]
        except Exception:
            pass
        return []

    async def _search_serpapi(self, query: str, num_results: int, **kwargs) -> List[SearchResult]:
        url = "https://serpapi.com/search"
        from agent_core.utils.security import is_safe_url
        if not is_safe_url(url):
            return []
        params = {"api_key": self.serpapi_key, "q": query, "num": num_results, "engine": "google"}
        try:
            if "client" in kwargs and kwargs["client"] is not None:
                res = await kwargs["client"].get(url, params=params)
            else:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    res = await client.get(url, params=params)
                if res.status_code == 200:
                    data = res.json()
                    return [
                        SearchResult(query=query, content=r.get("snippet", ""), source_url=r.get("link", ""), provider="serpapi")
                        for r in data.get("organic_results", [])
                    ]
        except Exception:
            pass
        return []

    async def _search_exa(self, query: str, num_results: int, **kwargs) -> List[SearchResult]:
        url = "https://api.exa.ai/search"
        from agent_core.utils.security import is_safe_url
        if not is_safe_url(url):
            return []
        headers = {"x-api-key": self.exa_key, "Content-Type": "application/json"}
        payload = {"query": query, "numResults": num_results}
        try:
            if "client" in kwargs and kwargs["client"] is not None:
                res = await kwargs["client"].post(url, headers=headers, json=payload)
            else:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    res = await client.post(url, headers=headers, json=payload)
                if res.status_code == 200:
                    data = res.json()
                    return [
                        SearchResult(query=query, content=r.get("text", r.get("title", "")), source_url=r.get("url", ""), provider="exa")
                        for r in data.get("results", [])
                    ]
        except Exception:
            pass
        return []

    async def _search_duckduckgo(self, query: str, num_results: int, **kwargs) -> List[SearchResult]:
        url = "https://html.duckduckgo.com/html/"
        from agent_core.utils.security import is_safe_url
        if not is_safe_url(url):
            return []
        data = {"q": query}
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        try:
            if "client" in kwargs and kwargs["client"] is not None:
                res = await kwargs["client"].post(url, data=data, headers=headers)
            else:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    res = await client.post(url, data=data, headers=headers)
                if res.status_code == 200:
                    html = res.text
                    results = []
                    links = re.findall(r'<a class="result__url" href="([^"]+)">([^<]+)</a>', html)
                    snippets = re.findall(r'<a class="result__snippet[^>]*>([^<]+)</a>', html)
                    for i, (href, raw_url) in enumerate(links[:num_results]):
                        snippet = snippets[i] if i < len(snippets) else query
                        results.append(SearchResult(query=query, content=snippet.strip(), source_url=raw_url.strip(), provider="duckduckgo"))
                    return results
        except Exception:
            pass
        return []
