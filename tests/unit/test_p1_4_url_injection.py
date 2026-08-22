"""
P1.4 — URL / argv injection güvenlik testi (köprü bağımsız sürüm).

Kapsam (rust_bridge silindikten sonra kalan canlı yüzeyler):
  A. scraper.py ve run_scraper.py kaynaklarında eval/exec/subprocess/invade yok.
  B. run_scraper.py argv[1]'den aldığı username'i split('/') ile işler,
     kod olarak çalıştırmaz.
"""
import ast
from pathlib import Path

REPO = Path(__file__).parent.parent.parent

SCRAPER_FILES = [
    REPO / "scraper.py",
    REPO / "agent_core" / "scraper" / "run_scraper.py",
    REPO / "agent_core" / "scraper" / "instagram_ghost.py",
]


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_no_dynamic_code_execution_in_scrapers():
    forbidden = {"eval", "exec", "__import__", "compile"}
    for f in SCRAPER_FILES:
        tree = ast.parse(_source(f))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                fn = node.func
                name = fn.id if isinstance(fn, ast.Name) else (fn.attr if isinstance(fn, ast.Attribute) else "")
                assert name not in forbidden, f"{f.name}: dinamik kod çalıştırma ({name}) yasak"


def test_no_subprocess_in_scrapers():
    for f in SCRAPER_FILES:
        tree = ast.parse(_source(f))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for a in node.names:
                    assert a.name != "subprocess", f"{f.name}: subprocess importu yok (injector silindi)"
            if isinstance(node, ast.ImportFrom):
                assert node.module != "subprocess", f"{f.name}: subprocess importu yok (injector silindi)"


def test_run_scraper_username_is_split_not_executed():
    """username sadece split('/') ile ayıklanır — hiçbir kod yolunda komuta dönüşmez."""
    src = _source(REPO / "agent_core" / "scraper" / "run_scraper.py")
    assert "split" in src
    assert "eval" not in src and "exec(" not in src and "system(" not in src
