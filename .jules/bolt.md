## 2024-05-24 - Async HTTP Connection Pooling
**Learning:** Instantiating `httpx.AsyncClient` inside a loop or within parallel `asyncio.gather` tasks prevents connection pooling and increases overhead for concurrent requests to the same host.
**Action:** When performing parallel async HTTP requests, instantiate a shared `httpx.AsyncClient` outside the `asyncio.gather` block and pass it to the worker functions.

## 2025-02-23 - Caching Configuration Parsing
**Learning:** Parsing YAML configuration files synchronously in a hot loop (like `DecisionConfig.load()`) adds unnecessary file I/O and CPU overhead.
**Action:** Use standard Python caching techniques like `@lru_cache(maxsize=1)` on static configuration loader classmethods to cache the parsed output and avoid repeated disk reads.

## 2025-02-24 - Async SQLite Concurrency
**Learning:** When offloading synchronous SQLite operations to threads using `asyncio.to_thread()`, running multiple writes concurrently via `asyncio.gather()` triggers SQLite locking issues because it spawns a separate thread for every item, violating SQLite concurrency limitations.
**Action:** When batch writing to SQLite in an async context, collect the writes into a single synchronous function and offload the entire sequential batch loop to a single background thread using `asyncio.to_thread()`.

## 2024-09-13 - Env Secret Values Optimization Failure
**Learning:** Attempting to optimize repetitive iterations over `os.environ` (for logging redactions) by wrapping it in `lru_cache` and passing `tuple(os.environ.items())` as a cache key on every invocation is computationally wasteful. The O(N) memory allocation and hashing overhead of building a complete snapshot of the environment nullifies any micro-performance gains over standard string-matching loops.
**Action:** Do not use `tuple(os.environ.items())` as a dynamic cache key in hot loops; keep environment reading lean or cache regex compilation patterns per call instead (as the codebase currently does efficiently).
