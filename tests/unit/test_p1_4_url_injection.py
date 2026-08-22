"""
P1.4 — URL / stdin injection güvenlik testi.

Üç vektörü kanıtlar:
  A. target_url hiçbir zaman eval/exec/subprocess'e gönderilmiyor.
  B. Kötü niyetli URL, run_full_pipeline'a ham string olarak geçiyor.
  C. run_scraper.py'nin argv[1]'den aldığı username,
     split('/') ile işlenip kod olarak çalıştırılmıyor.
"""
import ast
import inspect
import sys
import json
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

import agent_core.agents.rust_bridge_agent as bridge_module
from agent_core.agents.rust_bridge_agent import run_full_pipeline, _user_profile

SCRAPER_SRC = (
    Path(__file__).parent.parent.parent
    / "agent_core" / "scraper" / "run_scraper.py"
)

# ------------------------------------------------------------------
# Yardımcı: kaynak kodu statik analiz
# ------------------------------------------------------------------
def _get_function_source(module, func_name: str) -> str:
    func = getattr(module, func_name, None)
    if func is None:
        return ""
    return inspect.getsource(func)


# ------------------------------------------------------------------
# TEST A1: run_full_pipeline kaynağında eval/exec/subprocess.call YOK
# ------------------------------------------------------------------
def test_run_full_pipeline_has_no_eval_or_exec():
    """run_full_pipeline kodu eval(), exec() çağrısı içermemeli."""
    src = _get_function_source(bridge_module, "run_full_pipeline")
    for dangerous in ("eval(", "exec(", "compile(", "__import__"):
        assert dangerous not in src, (
            f"GÜVENLİK İHLALİ: run_full_pipeline içinde '{dangerous}' bulundu!"
        )


# ------------------------------------------------------------------
# TEST A2: run_full_pipeline kaynağında subprocess.call / os.system YOK
# ------------------------------------------------------------------
def test_run_full_pipeline_has_no_subprocess_injection():
    """run_full_pipeline kodu subprocess.call/os.system içermemeli."""
    src = _get_function_source(bridge_module, "run_full_pipeline")
    for dangerous in ("subprocess.call", "subprocess.run", "os.system", "os.popen"):
        assert dangerous not in src, (
            f"GÜVENLİK İHLALİ: run_full_pipeline içinde '{dangerous}' bulundu!"
        )


# ------------------------------------------------------------------
# TEST B: Kötü niyetli URL ham string olarak geçiyor, kod çalışmıyor
# ------------------------------------------------------------------
def test_malicious_url_passed_as_raw_string_not_executed():
    """
    '; import os; os.system('rm -rf /')' gibi URL,
    run_full_pipeline'a ham string olarak geçmeli — kod olarak çalışmamalı.
    """
    malicious_url = "'; import os; os.system('rm -rf /')"

    fake_task_status = MagicMock()
    fake_task_status.status = "completed"
    fake_task_status.evidence_chain = []

    captured_url = []

    def fake_asyncio_run(coro):
        # Coroutine'i close edip task_status döndürüyoruz — gerçek çalışma yok
        coro.close()
        return fake_task_status

    with patch("agent_core.agents.rust_bridge_agent.asyncio.run", side_effect=fake_asyncio_run), \
         patch("agent_core.agents.rust_bridge_agent.PinealExecutor") as MockExec:
        # PinealExecutor instance'ının execute_task'ini yakala
        mock_instance = MagicMock()
        MockExec.return_value = mock_instance

        # input_data'nın target_url'ini yakalamak için asyncio.run'u intercept ettik.
        # Şimdi url'in run_full_pipeline'a string olarak girildiğini doğruluyoruz.
        result = run_full_pipeline(malicious_url, {}, {})

    # target_url çıktıda ham string olarak dönmeli — kod çalışmamış olmalı
    assert result["target_url"] == malicious_url, (
        "URL çıktıya değişmeden geçmeli (ham string)"
    )
    # overall_authenticity_score asla 0.5 olmamalı (P0.3 regresyon)
    assert result.get("overall_authenticity_score") != 0.5


# ------------------------------------------------------------------
# TEST C1: run_scraper.py statik analiz — eval/exec/f-string URL kullanımı yok
# ------------------------------------------------------------------
def test_run_scraper_source_has_no_code_injection():
    """run_scraper.py'de eval/exec/os.system gibi tehlikeli çağrı yok."""
    assert SCRAPER_SRC.exists(), f"Dosya bulunamadı: {SCRAPER_SRC}"
    src = SCRAPER_SRC.read_text(encoding="utf-8")
    for dangerous in ("eval(", "exec(", "os.system(", "subprocess.call(", "compile("):
        assert dangerous not in src, (
            f"GÜVENLİK İHLALİ: run_scraper.py içinde '{dangerous}' bulundu!"
        )


# ------------------------------------------------------------------
# TEST C2: run_scraper.py — username, argv'den string olarak alınıyor
# ------------------------------------------------------------------
def test_run_scraper_argv_username_is_string_split_not_exec():
    """
    run_scraper.py'de sys.argv[1], yalnızca .strip('/').split('/')[-1]
    ile işleniyor; eval/exec kullanılmıyor.
    """
    src = SCRAPER_SRC.read_text(encoding="utf-8")
    # argv[1] alındıktan sonra sadece string manipülasyon yapılıyor
    assert "sys.argv[1]" in src, "argv kullanımı bekleniyor"
    assert "strip('/')" in src, "URL temizleme bekleniyor"
    # f"...{username}..." ile Python kodu oluşturuluyor olmamalı
    assert "eval(" not in src
    assert "exec(" not in src


# ------------------------------------------------------------------
# TEST C3: stdin (--stdin) yolu — JSON parse, kod çalıştırma değil
# ------------------------------------------------------------------
def test_stdin_path_parses_json_not_executes_code():
    """
    rust_bridge_agent main() --stdin yolunda json.load(stdin) kullanılıyor.
    target_url hiçbir zaman eval/exec'e verilmiyor.
    """
    src = inspect.getsource(bridge_module.main)
    assert "json.load(sys.stdin)" in src, "--stdin yolu json.load kullanmalı"
    assert "eval(" not in src
    assert "exec(" not in src
    assert "os.system(" not in src
