"""
token_compressor.py'nin yasaklı bağımlılıklara dokunmadığını
statik kaynak taraması ile doğrular (Rust purity_scan.rs ile simetrik).
"""
import ast
from pathlib import Path

MODULE_PATH = Path("agent_core/services/token_compressor.py")

FORBIDDEN_IMPORTS = {
    "canonical_memory",
    "hindsight_memory",
    "task_executor",
    "llm_gateway",  # bu modül gateway'i İMPORT ETMEMELİ, tersi olur
    "requests",
    "httpx",
    "aiohttp",
}

FORBIDDEN_CALLS = {"open"}  # dosya sistemi erişimi yasak


def test_token_compressor_has_no_forbidden_imports():
    source = MODULE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)

    imported_names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_names.add(node.module.split(".")[0])

    forbidden_found = imported_names & FORBIDDEN_IMPORTS
    assert not forbidden_found, f"Yasaklı import bulundu: {forbidden_found}"


def test_token_compressor_does_not_call_open():
    source = MODULE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)

    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            assert node.func.id not in FORBIDDEN_CALLS, (
                f"Yasaklı çağrı bulundu: {node.func.id}() — bu modül dosya sistemine dokunmamalı"
            )