import re

with open('backend/api.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Update the fallback logic to mark it as degraded
old_fallback = """        if (
            application.state.llm_backend_mode == "unified"
            and application.state.openai_router is None
        ):
            logger.warning("PINEAL_ROUTER_CONFIG is missing or invalid. Falling back to legacy LLM backend.")
            application.state.llm_backend_mode = "legacy" """

new_fallback = """        router_fallback_active = False
        if (
            application.state.llm_backend_mode == "unified"
            and application.state.openai_router is None
        ):
            logger.error("PINEAL_ROUTER_CONFIG is missing or invalid. Falling back to legacy LLM backend, marking health as DEGRADED.")
            application.state.llm_backend_mode = "legacy"
            router_fallback_active = True"""

if old_fallback in content:
    content = content.replace(old_fallback, new_fallback)
    print("Fallback logic updated.")
else:
    print("Could not find fallback logic.")

# 2. Update the startup_health payload to include the degraded status
old_health_status = """        startup_health["components"] = {
            "rust_core": rust_core_status(),"""

new_health_status = """        if router_fallback_active:
            startup_health["status"] = "degraded"
            startup_health["error_code"] = "UNIFIED_ROUTER_CONFIG_MISSING"

        startup_health["components"] = {
            "rust_core": rust_core_status(),"""

if old_health_status in content:
    content = content.replace(old_health_status, new_health_status)
    print("Health status logic updated.")
else:
    print("Could not find health status logic.")

with open('backend/api.py', 'w', encoding='utf-8') as f:
    f.write(content)
