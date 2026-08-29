"""Sahte-veri/mock YASAĞI koruma testi (production yolları).

Sözleşme:
- Production Python (agent_core/, backend/, live_llm_gate.py) içinde mock
  import'u ya da Mock/AsyncMock/MagicMock ÇAĞRISI YASAK (AST tabanlı —
  yorumlar algılayamaz, yanlış-pozitif vermez). "MOCK veri dönülmez" gibi
  yasağı belgeleyen yorumlar serbesttir ve bu test onları sevindirir.
- Dedektörün canlılığı kanıtlanır: aynı tarayıcı tests/ içinde en az bir
  mock kullanımı BULMALI (her zaman geçen koruma testi değildir).
- Frontend/Android ana kaynaklarında sahte-veri sabit kalıpları yasak.
- psutil adjudikasyonu çalışma-zamanı sözleşmesi: open-interpreter'ın
  gerçekte kullandığı API'ler (virtual_memory/disk_usage) ve crawl4ai'nin
  kullandıkları (Process/process_iter) kurulu psutil sürümünden bağımsız
  çalışmalı (iki-adımlı kurulum kararının kanıtı).
- Temizlenmiş ölü dosyalar (agent_core/p2p, db/reflection.sql) geri
  dönmemeli.
"""
import ast
import pytest
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

PROD_PY_PATHS = [
    REPO / "agent_core",
    REPO / "backend",
    REPO / "live_llm_gate.py",
]
FORBIDDEN_MODULES = {"mock", "unittest.mock"}
FORBIDDEN_CALL_NAMES = {"Mock", "AsyncMock", "MagicMock"}


def _py_files(root: Path):
    if root.is_file():
        yield root
        return
    for p in root.rglob("*.py"):
        if "__pycache__" in p.parts or ".venv" in p.parts:
            continue
        yield p


def _mock_violations(path: Path):
    """AST ile gerçek mock kullanımını bulur (yorum/strings hariç)."""
    found = []
    tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in FORBIDDEN_MODULES or alias.name.startswith("mock"):
                    found.append(f"{path.relative_to(REPO)}:{node.lineno} import {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            if node.module in FORBIDDEN_MODULES:
                found.append(f"{path.relative_to(REPO)}:{node.lineno} from {node.module}")
        elif isinstance(node, ast.Call):
            fn = node.func
            name = fn.id if isinstance(fn, ast.Name) else (
                fn.attr if isinstance(fn, ast.Attribute) else None)
            if name in FORBIDDEN_CALL_NAMES:
                found.append(f"{path.relative_to(REPO)}:{node.lineno} {name}()")
    return found


class TestMockBanProduction:
    def test_production_python_has_zero_mock_usage(self):
        violations = []
        for root in PROD_PY_PATHS:
            for py in _py_files(root):
                violations.extend(_mock_violations(py))
        assert violations == [], (
            "Production kodda mock kullanımı YASAK: " + "; ".join(violations))

    def test_detector_is_alive_finds_mocks_in_tests(self):
        """Koruma testinin kendisi sahte-geçer olamaz: tarayıcı tests/'te
        meşru mock kullanımını bulabilmeli (dedektör canlı kanıtı)."""
        hits = []
        for py in _py_files(REPO / "tests"):
            hits.extend(_mock_violations(py))
        assert len(hits) >= 1, "Dedektör kör: tests/'teki mock'ları bulamıyor"


class TestFrontendAndroidMockBan:
    def test_no_mock_data_patterns_in_frontend_and_android_main(self):
        patterns = re.compile(
            r"unittest\.mock|MagicMock|AsyncMock|"
            r"\bmockData\b|\bfakeData\b|\bdummyData\b|"
            r"const\s+(MOCK|FAKE|DUMMY|SAMPLE)[A-Za-z_]*\s*=",
        )
        targets = []
        fe = REPO / "frontend" / "src"
        an = REPO / "android" / "app" / "src" / "main"
        if fe.exists():
            targets += [p for p in fe.rglob("*") if p.suffix in (".svelte", ".ts", ".js")]
        if an.exists():
            targets += [p for p in an.rglob("*.kt")]
        violations = []
        for f in targets:
            try:
                text = f.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            for i, line in enumerate(text.splitlines(), 1):
                if patterns.search(line):
                    violations.append(f"{f.relative_to(REPO)}:{i}")
        assert violations == [], "Sahte-veri kalıbı: " + "; ".join(violations)


class TestPsutilAdjudicationRuntime:
    """İki-adımlı kurulum kararının çalışma-zamanı kanıtı: hangi psutil
    sürümü kurulursa kurulsun, iki paketin GERÇEK kullandığı API'ler çalışır."""

    def test_both_packages_real_apis_work(self):
        psutil = __import__("psutil")
        assert psutil.virtual_memory().total > 0          # open-interpreter
        assert psutil.disk_usage("/").free > 0             # open-interpreter
        assert psutil.Process().pid > 0                    # crawl4ai
        assert len(list(psutil.process_iter(["pid"]))) > 0  # crawl4ai

    def test_open_interpreter_imports_with_installed_psutil(self):
        importlib = __import__("importlib")
        importlib.import_module("interpreter")  # psutil'i dolaylı çeker

    def test_crawl4ai_psutil_consuming_modules_import(self):
        importlib = __import__("importlib")
        pytest.importorskip(
            "crawl4ai",
            reason="crawl4ai ikinci-adım dosyasındadır (requirements-osint.txt); CI yalnız birinci adımı kurar",
        )
        importlib.import_module("crawl4ai")
        importlib.import_module("crawl4ai.async_dispatcher")  # psutil kullanan modül


class TestDeadFilesStayDead:
    def test_cleaned_dead_files_not_back(self):
        assert not (REPO / "agent_core" / "p2p").exists()
        assert not (REPO / "agent_core" / "db" / "reflection.sql").exists()
