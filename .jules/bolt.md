## 2025-02-23 - [Cache Env Parsing in Redaction]
**Learning:** Parsing `os.environ` per text redaction takes significant time (~67.8ms for 900 strings). This is an unnecessary cost during runtime when environments are largely static.
**Action:** Use `@functools.lru_cache(maxsize=1)` on functions that repeatedly parse `os.environ` when called frequently, such as secrets extraction for data redaction. Remember to clear cache in pytest fixtures if tests mock env vars.
