## 2024-05-24 - [Vision Analyzer Connection Pooling]
**Learning:** [Opening multiple independent HTTP sessions inside `asyncio.gather` for fetching resources like images bypasses connection pooling, degrading performance when fetching from the same host multiple times concurrently. Sharing a single `httpx.AsyncClient` across tasks allows connection reuse.]
**Action:** [When making concurrent HTTP requests, especially to the same domain, always instantiate a shared `httpx.AsyncClient` outside the gather block and pass it into the fetching routines.]
## 2024-05-24 - Async HTTP Connection Pooling
**Learning:** Instantiating `httpx.AsyncClient` inside a loop or within parallel `asyncio.gather` tasks prevents connection pooling and increases overhead for concurrent requests to the same host.
**Action:** When performing parallel async HTTP requests, instantiate a shared `httpx.AsyncClient` outside the `asyncio.gather` block and pass it to the worker functions.
