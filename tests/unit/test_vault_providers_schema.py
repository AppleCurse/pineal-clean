"""Kasa semasi sozlesmeleri: providers.{ad}.api_key (gercek yerel sema).

V1. Operator adlandirmasi normalize edilip gateway provider ID'sine cevrilir.
V2. Duz `provider_keys` ayni dosyada varsa EZER (acik override).
V3. Bilinmeyen/bozuk girdiler sessiz yutulmaz (skipped listeleri); sir
    DEGERLER hicbir isaret/log yapisina girmez.
V4. openrouter girdisi set_key yedegidir (top-level api_key yoksa).
V5. Alias hedefleri gateway'in bilinen ID kumesiyle senkron (drift kilidi).
"""

import json
import uuid

from backend.api import _VAULT_PROVIDER_ALIASES, _extract_vault_provider_keys


def test_providers_schema_maps_operator_names_to_gateway_ids():
    vault = {"providers": {
        "gemini": {"api_key": "G1"},
        "NVIDIA NIM": {"api_key": "N1"},
        "DeepSeek": {"api_key": "D1"},
        "i-flow": {"api_key": "I1"},
        "google_gemini_backup": {"api_key": "GB1"},
        "vertex": {"api_key": "GV1"},
        "mistral": {"api_key": "M1"},
        "Google Gemini": {"api_key": "G2"},
    }}
    applied, or_key, skipped = _extract_vault_provider_keys(vault)
    # "gemini" + "Google Gemini" ayni pid'e duser; dict sirasiyla son yazar.
    assert applied["google-gemini"] in ("G1", "G2")
    assert applied["nvidia-nim"] == "N1"
    assert applied["deepseek"] == "D1"
    assert applied["iflow"] == "I1"
    assert applied["google-gemini-backup"] == "GB1"
    assert applied["google-gemini-vertex"] == "GV1"
    assert applied["mistral"] == "M1"
    assert or_key is None
    assert skipped == {"unknown": [], "malformed": []}


def test_openrouter_entry_is_key_fallback_only():
    vault = {"providers": {"openrouter": {"api_key": "OR1"}}}
    applied, or_key, skipped = _extract_vault_provider_keys(vault)
    assert applied == {} and or_key == "OR1"
    assert skipped == {"unknown": [], "malformed": []}


def test_flat_provider_keys_override_providers_section():
    vault = {"providers": {"gemini": {"api_key": "OLD"}},
             "provider_keys": {"google-gemini": "NEW"}}
    applied, _, _ = _extract_vault_provider_keys(vault)
    assert applied == {"google-gemini": "NEW"}


def test_unknown_and_malformed_are_reported_never_swallowed():
    vault = {"providers": {
        "bilinmeyen-x": {"api_key": "X"},
        "gemini": {"token": "api_key-alani-yok"},
        "nvidia": {"api_key": "   "},
        "groq": {"api_key": None},
        "together": ["not-a-key"],
    }}
    applied, _, skipped = _extract_vault_provider_keys(vault)
    assert applied == {}
    assert skipped["unknown"] == ["bilinmeyen-x"]
    assert sorted(skipped["malformed"]) == ["gemini", "groq", "nvidia", "together"]


def test_plain_string_values_accepted_for_compat():
    vault = {"providers": {"deepseek": "sk-plain"}}
    applied, _, skipped = _extract_vault_provider_keys(vault)
    assert applied == {"deepseek": "sk-plain"}
    assert skipped == {"unknown": [], "malformed": []}


def test_no_vault_sections_yields_empty_parse():
    assert _extract_vault_provider_keys({}) == ({}, None, {"unknown": [], "malformed": []})
    assert _extract_vault_provider_keys({"api_key": "x"})[0] == {}
    assert _extract_vault_provider_keys(None) == ({}, None, {"unknown": [], "malformed": []})
    assert _extract_vault_provider_keys({"providers": ["nope"]})[0] == {}


def test_alias_targets_track_gateway_known_ids():
    from agent_core.services.llm_gateway import _KNOWN_PROVIDER_KEY_IDS

    targets = set(_VAULT_PROVIDER_ALIASES.values()) - {"openrouter"}
    assert targets <= set(_KNOWN_PROVIDER_KEY_IDS)
    # envanter kritik saglayicilar kapsanmali
    for pid in ("deepseek", "nvidia-nim", "google-gemini", "iflow",
                "google-gemini-backup", "google-gemini-vertex"):
        assert pid in targets


def test_secret_values_never_appear_in_marker_structures():
    vault = {"providers": {
        "gemini": {"api_key": "GIZLI-DEGER-123"},
        "bilinmeyen-x": {"api_key": "GIZLI-DEGER-456"},
    }}
    applied, or_key, skipped = _extract_vault_provider_keys(vault)
    # cagiranin isaretleyebilecegi yapilar: pid listeleri + ad listeleri.
    blob = json.dumps({"pids": sorted(applied), "skipped": skipped,
                       "or_present": or_key is not None})
    assert "GIZLI-DEGER-123" not in blob
    assert "GIZLI-DEGER-456" not in blob


def test_get_room_applies_vault_providers_end_to_end(tmp_path, monkeypatch):
    import backend.api as api_module

    cid = f"vault_{uuid.uuid4().hex[:8]}"
    (tmp_path / ".pineal_vault.json").write_text(json.dumps({
        "providers": {
            "gemini": {"api_key": "G1"},
            "nvidia": {"api_key": "N1"},
            "bilinmeyen-x": {"api_key": "X"},
        },
    }), encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    for env in ("OPENROUTER_API_KEY", "GEMINI_API_KEY", "NVIDIA_API_KEY"):
        monkeypatch.delenv(env, raising=False)
    room = api_module.get_room(cid)
    gateway = room["executor"].llm_gateway
    assert gateway._provider_keys.get("google-gemini") == "G1"
    assert gateway._provider_keys.get("nvidia-nim") == "N1"
    assert room["vault"].get("provider_keys_set") == ["google-gemini", "nvidia-nim"]
    assert room["vault"].get("provider_keys_skipped") == {
        "unknown": ["bilinmeyen-x"], "malformed": []}
    assert "providers" not in room["vault"] and "provider_keys" not in room["vault"]
    blob = json.dumps(room["vault"], default=str)
    assert "G1" not in blob and "N1" not in blob and '"X"' not in blob


def test_get_room_prefers_toplevel_api_key_over_providers_openrouter(tmp_path, monkeypatch):
    import backend.api as api_module

    cid = f"vaultor_{uuid.uuid4().hex[:8]}"
    (tmp_path / ".pineal_vault.json").write_text(json.dumps({
        "api_key": "sk-or-v1-TOP",
        "providers": {"openrouter": {"api_key": "sk-or-v1-PROV"}},
    }), encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    room = api_module.get_room(cid)
    assert room["executor"].llm_gateway.api_key == "sk-or-v1-TOP"
    assert room["vault"].get("or_key") is True


def test_get_room_uses_providers_openrouter_when_toplevel_missing(tmp_path, monkeypatch):
    import backend.api as api_module

    cid = f"vaultor2_{uuid.uuid4().hex[:8]}"
    (tmp_path / ".pineal_vault.json").write_text(json.dumps({
        "providers": {"openrouter": {"api_key": "sk-or-v1-PROV"}},
    }), encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    room = api_module.get_room(cid)
    assert room["executor"].llm_gateway.api_key == "sk-or-v1-PROV"
    assert room["vault"].get("or_key") is True
