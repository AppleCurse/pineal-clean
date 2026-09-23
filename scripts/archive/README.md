# scripts/archive — tek seferlik prob/deneme scriptleri

Bu dizindeki scriptler **üretim akışında, CI'da ve test paketinde kullanılmaz**
(`pytest.ini: testpaths = tests`). Tarihsel kanıt/deneme amaçlı saklanır:

| Script | Ne idi |
|---|---|
| `analyze_target_instagram.py` | tek-profil canlı demo (Chrome ister) |
| `benchmark_download.py` | indirme kıyaslaması |
| `e2e_test.py` | elle çalıştırılan canlı LLM provası |
| `flow_roentgen.py` | akış röntgeni ölçüm aracı (`docs/reports/AKIS_RONTGENI_2026-09-21.md`) |
| `live_provider_probe.py` | canlı sağlayıcı probu |
| `test_e2e_fixture.py` | uçtan uca prova (canlı) |
| `test_live_holistic.py` | bütüncül canlı çözümleme (canlı) |
| `ws_leak_probe.py` | WS sızıntı probu (`docs/ZERO_TRUST_VERIFICATION_2026-09-18.md`) |

Aktif operasyonel scriptler bir üst dizinde kalır: `run_task.py`,
`generate_routing_shadows.py`, `verify_openrouter_catalog.py`,
`preflight_9router.py`, `smoke_test_browser.py`, `backup_restore.sh`,
`test_disaster_recovery.sh/.ps1`.
