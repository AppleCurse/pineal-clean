## 2024-05-24 - Async HTTP Connection Pooling
**Learning:** Instantiating `httpx.AsyncClient` inside a loop or within parallel `asyncio.gather` tasks prevents connection pooling and increases overhead for concurrent requests to the same host.
**Action:** When performing parallel async HTTP requests, instantiate a shared `httpx.AsyncClient` outside the `asyncio.gather` block and pass it to the worker functions.

## 2024-06-25 - Async HTTP Connection Pooling applied to human_behavior
**Learning:** `asyncio.gather` successfully enabled parallel HTTP requests inside `HumanBehaviorAnalyzer.execute()` for image fetching, while maintaining the usage of a shared `httpx.AsyncClient` pool. This is consistent with previous learnings but proves the pattern is applicable to `human_behavior.py`. When refactoring logic to be concurrent, ensure that you leave no temporary script artifacts behind in the repository root.
**Action:** When performing parallel async HTTP requests, extract the core request and processing logic to a separate async method that receives the shared `httpx.AsyncClient` and the target item, and invoke them with `asyncio.gather`. Always clean up temporary python execution scripts used during development.
