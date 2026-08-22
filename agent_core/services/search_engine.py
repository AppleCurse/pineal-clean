import asyncio
import httpx
import json
from typing import Dict, List, Optional
from pydantic import BaseModel, ConfigDict

class SearchResult(BaseModel):
    query: str
    content: str
    source_url: str
    
    model_config = ConfigDict(extra="forbid")

class SearchEngine:
    """
    Otonom ajanların internete çıkış kapısı.
    Şimdilik Tavily API'sini varsayılan olarak kullanır.
    """
    def __init__(self):
        import os
        self.tavily_key = os.getenv("TAVILY_API_KEY")
        self.serpapi_key = os.getenv("SERPAPI_API_KEY")
        self.exa_key = os.getenv("EXA_API_KEY")

    def set_keys(self, tavily: str = None, serpapi: str = None, exa: str = None):
        if tavily: self.tavily_key = tavily
        if serpapi: self.serpapi_key = serpapi
        if exa: self.exa_key = exa

    async def search(self, query: str, num_results: int = 3) -> List[SearchResult]:
        if not self.tavily_key:
            # Yedek plan: Anahtar yoksa boş dön
            return []
            
        try:
            async with httpx.AsyncClient() as client:
                payload = {
                    "api_key": self.tavily_key,
                    "query": query,
                    "search_depth": "basic",
                    "include_answer": False,
                    "max_results": num_results
                }
                response = await client.post("https://api.tavily.com/search", json=payload, timeout=10.0)
                response.raise_for_status()
                data = response.json()
                
                results = []
                for item in data.get("results", []):
                    results.append(SearchResult(
                        query=query,
                        content=item.get("content", ""),
                        source_url=item.get("url", "")
                    ))
                return results
        except Exception as e:
            print(f"SearchEngine Error: {str(e)}")
            return []
