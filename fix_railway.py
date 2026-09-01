import re

with open('backend/api.py', 'r', encoding='utf-8') as f:
    content = f.read()

old_code = """        if (
            application.state.llm_backend_mode == "unified"
            and application.state.openai_router is None
        ):
            raise RoutingRuntimeError(
                "PINEAL_ROUTER_CONFIG is required when PINEAL_LLM_BACKEND=unified"
            )"""

new_code = """        if (
            application.state.llm_backend_mode == "unified"
            and application.state.openai_router is None
        ):
            logger.warning("PINEAL_ROUTER_CONFIG is missing or invalid. Falling back to legacy LLM backend.")
            application.state.llm_backend_mode = "legacy" """

if old_code in content:
    content = content.replace(old_code, new_code)
    print("Fixed api.py fallback!")
else:
    print("Could not find the target code in api.py.")

with open('backend/api.py', 'w', encoding='utf-8') as f:
    f.write(content)
