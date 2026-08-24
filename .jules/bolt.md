## 2024-05-24 - [Vision Analyzer Connection Pooling]
**Learning:** [Opening multiple independent HTTP sessions inside `asyncio.gather` for fetching resources like images bypasses connection pooling, degrading performance when fetching from the same host multiple times concurrently. Sharing a single `httpx.AsyncClient` across tasks allows connection reuse.]
**Action:** [When making concurrent HTTP requests, especially to the same domain, always instantiate a shared `httpx.AsyncClient` outside the gather block and pass it into the fetching routines.]
