"""Adli kapatıcılar (kalan 4 madde): kasa interlock, raf kablolama, gravity determinizmi, taşıyıcı dürüstlüğü.

Kilitler:
  V1. `_check_vault_interlock` dosya VARLIĞIYLA açılmaz; gerçek anahtar
      malzemesi ister, placeholder fail-closed reddedilir.
  V2. `/api/vault` placeholder anahtarı 400 ile reddeder, bayrak kurmaz.
  R1. `_AGENT_RACK_MAP` birebirdir: hiçbir raf slotuna iki ajan yazmaz;
      yardımcılar (shadow/7pillar/vision) kendi slotunu boyar.
  R2. `_rack_update` senkron-yedek yolu gerçekten yazar (ölü kod değil).
  G1. GRAVITY eşit (pull, mass) durumunda alfabetik tie-breaker uygular;
      çıktı PYTHONHASHSEED'den bağımsızdır (alt-süreç kanıtı).
  T1. `/api/agents/status` `source` alanı canlı ping'e bağlıdır:
      Redis yanıt veriyorsa `redis_bus`, vermiyorsa `in_memory`.
"""

import json
import subprocess
import sys
import uuid
from itertools import groupby
from pathlib import Path

import pytest

import backend.api as api
from agent_core.engines.gravity_engine import GravityEngine
from agent_core.task_executor import PinealExecutor


# ---------------------------------------------------------------- V1: interlock

def test_placeholder_prefix_rejected():
    assert api._is_placeholder_key("sk-or-v1-YOUR-KEY-HERE")
    assert not api._is_real_key("sk-or-v1-YOUR-KEY-HERE")


@pytest.mark.parametrize("val", ["", "   ", None, 123, ["x"], "YOUR_API_KEY",
                           "my_changeme_key", "REPLACE_ME", "sample_key_1"])
def test_empty_and_placeholder_values_are_not_real(val):
    assert not api._is_real_key(val)


@pytest.mark.parametrize("val", ["sk-or-v1-abc123", "sk-pineal-local-1", "tvly-real",
                           "G1", "sessionid_abc", "c1=v1; c2=v2"])
def test_real_keys_accepted(val):
    assert api._is_real_key(val)


def test_cookie_pool_needs_one_real_line():
    assert api._cookie_pool_has_key("a=1\nb=2")
    assert api._cookie_pool_has_key("YOUR_COOKIE\na=1")
    assert not api._cookie_pool_has_key("   ")
    assert not api._cookie_pool_has_key("YOUR_COOKIE_HERE")
    assert not api._cookie_pool_has_key(None)


def test_file_without_key_material_stays_locked():
    assert not api._vault_file_has_key_material({})
    assert not api._vault_file_has_key_material({"use_local": True})
    assert not api._vault_file_has_key_material({"api_key": "   "})
    assert not api._vault_file_has_key_material(
        {"api_key": "sk-or-v1-YOUR-KEY",
         "providers": {"gemini": {"api_key": "PLACEHOLDER"}}})
    assert not api._vault_file_has_key_material(
        {"providers": {"search and osint": {"tavily": "EXAMPLE"}}})
    assert not api._vault_file_has_key_material([])


def test_file_with_real_material_unlocks():
    assert api._vault_file_has_key_material({"api_key": "sk-or-v1-abc"})
    assert api._vault_file_has_key_material({"providers": {"deepseek": {"api_key": "D1"}}})
    assert api._vault_file_has_key_material({"providers": {"deepseek": "sk-plain"}})
    assert api._vault_file_has_key_material(
        {"providers": {"gemini": {"primary_api_key": "G1"}}})
    assert api._vault_file_has_key_material({"provider_keys": {"groq": "gsk-x"}})
    assert api._vault_file_has_key_material({"tavily_key": "tvly-x"})
    assert api._vault_file_has_key_material({"x_cookie": "a=1; b=2"})
    assert api._vault_file_has_key_material({"ig_sessionid": "sess-1"})
    assert api._vault_file_has_key_material(
        {"providers": {"search and osint": {"tavily": "tvly-x"}}})


def test_room_flags_unlock_only_when_real():
    assert not api._room_vault_unlocked({})
    assert not api._room_vault_unlocked({"or_key": False})
    assert not api._room_vault_unlocked({"provider_keys_set": []})
    assert api._room_vault_unlocked({"or_key": True})
    assert api._room_vault_unlocked({"provider_keys_set": ["deepseek"]})
    assert api._room_vault_unlocked({"search_keys": True})
    assert api._room_vault_unlocked({"ig_sessionid": "sess-1"})
    assert not api._room_vault_unlocked({"ig_sessionid": "YOUR_SESSION"})
    assert api._room_vault_unlocked({"x_cookie": "c1=v1"})
    assert not api._room_vault_unlocked({"x_cookie": "   "})


_KEY_ENVS = ("OPENROUTER_API_KEY", "NINEROUTER_API_KEY", "PINEAL_LLM_API_KEY",
             "TAVILY_API_KEY", "SERPAPI_API_KEY", "SERPAPI_KEY", "EXA_API_KEY")


def _scrub_key_env(monkeypatch):
    for env in _KEY_ENVS:
        monkeypatch.delenv(env, raising=False)


def test_interlock_locked_with_placeholder_only_file(tmp_path, monkeypatch):
    cid = f"lock_{uuid.uuid4().hex[:8]}"
    (tmp_path / ".pineal_vault.json").write_text(json.dumps({
        "api_key": "sk-or-v1-YOUR-KEY",
        "providers": {"gemini": {"api_key": "PLACEHOLDER"}},
    }), encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    _scrub_key_env(monkeypatch)
    room = api.get_room(cid)
    assert room["vault"].get("or_key") is not True
    assert not room["vault"].get("provider_keys_set")
    assert api._check_vault_interlock(cid) is False


def test_interlock_file_path_opens_only_with_real_key(tmp_path, monkeypatch):
    cid = f"file_{uuid.uuid4().hex[:8]}"
    monkeypatch.chdir(tmp_path)
    _scrub_key_env(monkeypatch)
    api.get_room(cid)
    assert api._check_vault_interlock(cid) is False
    # Anahtarsız dosya kilidi AÇMAZ (eski kusur: bool(dict) True idi).
    (tmp_path / ".pineal_vault.json").write_text(
        json.dumps({"use_local": True}), encoding="utf-8")
    assert api._check_vault_interlock(cid) is False
    # Gerçek malzeme kilidi açar.
    (tmp_path / ".pineal_vault.json").write_text(
        json.dumps({"api_key": "sk-or-v1-real"}), encoding="utf-8")
    assert api._check_vault_interlock(cid) is True


def test_get_room_skips_placeholder_provider_keys(tmp_path, monkeypatch):
    cid = f"psk_{uuid.uuid4().hex[:8]}"
    (tmp_path / ".pineal_vault.json").write_text(json.dumps({
        "providers": {
            "deepseek": {"api_key": "D1"},
            "groq": {"api_key": "YOUR_GROQ_KEY"},
        },
    }), encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    _scrub_key_env(monkeypatch)
    room = api.get_room(cid)
    gateway = room["executor"].llm_gateway
    assert gateway._provider_keys.get("deepseek") == "D1"
    assert "groq" not in gateway._provider_keys
    assert room["vault"].get("provider_keys_set") == ["deepseek"]


# ------------------------------------------------------- V2: /api/vault kapısı

async def test_api_vault_rejects_placeholder_key_atomically(tmp_path, monkeypatch):
    cid = f"vrej_{uuid.uuid4().hex[:8]}"
    monkeypatch.chdir(tmp_path)
    _scrub_key_env(monkeypatch)
    api.get_room(cid)
    resp = await api.api_vault(api.VaultPayload(client_id=cid, api_key="sk-or-v1-YOUR-KEY"))
    assert resp.status_code == 400
    body = json.loads(resp.body.decode("utf-8"))
    assert body["error"]["code"] == "PLACEHOLDER_KEY"
    assert api.get_vault(cid).get("or_key") is not True
    assert api._check_vault_interlock(cid) is False


async def test_api_vault_rejects_placeholder_cookie(tmp_path, monkeypatch):
    cid = f"vcrej_{uuid.uuid4().hex[:8]}"
    monkeypatch.chdir(tmp_path)
    _scrub_key_env(monkeypatch)
    api.get_room(cid)
    resp = await api.api_vault(api.VaultPayload(client_id=cid, x_cookie="YOUR_COOKIE"))
    assert resp.status_code == 400
    assert "x_cookie" not in api.get_vault(cid)


async def test_api_vault_skips_placeholder_provider_keys(tmp_path, monkeypatch):
    cid = f"vpsk_{uuid.uuid4().hex[:8]}"
    monkeypatch.chdir(tmp_path)
    _scrub_key_env(monkeypatch)
    api.get_room(cid)
    resp = await api.api_vault(api.VaultPayload(
        client_id=cid,
        provider_keys={"deepseek": "D1", "groq": "PLACEHOLDER"},
    ))
    assert resp == {"status": "secured"}
    vault = api.get_vault(cid)
    assert vault.get("provider_keys_set") == ["deepseek"]
    assert "PLACEHOLDER" not in json.dumps(vault)


# ------------------------------------------------------- R1/R2: raf kablolama

def test_rack_map_is_one_to_one_no_borrowed_slots():
    from agent_core.services.agent_status_tracker import AGENT_DEFINITIONS

    rack_ids = {a["id"] for a in AGENT_DEFINITIONS}
    assert len(rack_ids) == 12
    mapping = PinealExecutor._AGENT_RACK_MAP
    writers: dict = {}
    for agent, slot in mapping.items():
        writers.setdefault(slot, []).append(agent)
    for slot in rack_ids:
        assert len(writers.get(slot, [])) <= 1, (
            f"raf slotu '{slot}' birden fazla yazar taşıyor: {writers[slot]}")
    # Yardımcılar kendi slotunu boyar; raf slotlarını ödünç almaz.
    assert mapping["shadow_executor"] == "shadow_executor"
    assert mapping["pineal_7pillar"] == "pineal_7pillar"
    assert mapping["vision_analyzer"] == "vision_analyzer"
    # Gerçek sahipler slotlarında.
    assert mapping["depth_analyst"] == "depth_analyst"
    assert mapping["pattern_interrupt"] == "pattern_interrupt"


def test_rack_update_sync_fallback_writes_known_slot():
    from agent_core.services.agent_status_tracker import AgentStatusTracker

    executor = PinealExecutor.__new__(PinealExecutor)
    tracker = AgentStatusTracker.__new__(AgentStatusTracker)
    tracker._statuses = {"depth_analyst": {"status": "Wait"}}
    executor._agent_tracker = tracker
    # Senkron testte çalışan loop YOKTUR -> yedek yol devreye girer.
    executor._rack_update("depth_analyst", "active")
    assert tracker._statuses["depth_analyst"]["status"] == "active"


# ------------------------------------------------------- G1: gravity determinizmi

def _tied_gravity_input():
    posts = [
        "alpha word here now",
        "alpha word here now",
        "bravo word here now",
        "bravo word here now",
    ]
    meta = [{"like_count": 10} for _ in posts]
    return {"target_profile": {"posts": posts, "posts_meta": meta}}


async def test_gravity_ties_break_alphabetically_and_repeat():
    data = _tied_gravity_input()
    first = await GravityEngine(min_recurrence=2).analyze(data)
    second = await GravityEngine(min_recurrence=2).analyze(data)
    seq_first = [(w.anchor, w.pull, w.mass) for w in first.wells]
    seq_second = [(w.anchor, w.pull, w.mass) for w in second.wells]
    assert seq_first == seq_second
    assert first.dominant_attractor == second.dominant_attractor
    assert len(seq_first) >= 2
    for _key, group in groupby(seq_first, key=lambda t: (t[1], t[2])):
        anchors = [t[0] for t in group]
        assert anchors == sorted(anchors), f"tie-break alfabetik değil: {anchors}"


def test_gravity_stable_across_hash_seeds(tmp_path):
    """Farklı PYTHONHASHSEED süreçlerinde BİREBİR aynı çıktı (gerçek kanıt)."""
    root = Path(__file__).resolve().parents[2]
    script = tmp_path / "gravity_probe.py"
    script.write_text(
        "import json, sys\n"
        f"sys.path.insert(0, {str(root)!r})\n"
        "from agent_core.engines.gravity_engine import GravityEngine\n"
        "posts = ['alpha word here now'] * 2 + ['bravo word here now'] * 2\n"
        "data = {'target_profile': {'posts': posts, "
        "'posts_meta': [{'like_count': 10} for _ in posts]}}\n"
        "rep = GravityEngine(min_recurrence=2)._sync(data)\n"
        "print(json.dumps({'wells': [(w.anchor, w.pull, w.mass) for w in rep.wells], "
        "'dominant': rep.dominant_attractor}))\n",
        encoding="utf-8",
    )
    outputs = []
    import os

    for seed in ("0", "42"):
        env = dict(os.environ)
        env["PYTHONHASHSEED"] = seed
        proc = subprocess.run(
            [sys.executable, str(script)],
            capture_output=True, text=True, env=env, timeout=120,
        )
        assert proc.returncode == 0, proc.stderr[-500:]
        outputs.append(proc.stdout.strip())
    assert outputs[0] == outputs[1]
    payload = json.loads(outputs[0])
    wells = [(anchor, pull, mass) for anchor, pull, mass in payload["wells"]]
    assert wells, "bağlı test girdisi en az bir kuyu üretmeli"
    assert payload["dominant"] == wells[0][0]
    for _key, group in groupby(wells, key=lambda t: (t[1], t[2])):
        anchors = [t[0] for t in group]
        assert anchors == sorted(anchors), f"tie-break alfabetik değil: {anchors}"


# ------------------------------------------------------- T1: taşıyıcı dürüstlüğü

async def test_redis_transport_live_ping_matrix():
    assert await api._redis_transport_live(None) is False

    class NoRedis:
        _use_redis = False
        _client = object()

    assert await api._redis_transport_live(NoRedis()) is False

    class NoClient:
        _use_redis = True
        _client = None

    assert await api._redis_transport_live(NoClient()) is False

    class Dead:
        _use_redis = True

        class Client:
            def ping(self):
                raise ConnectionError("down")

        _client = Client()

    assert await api._redis_transport_live(Dead()) is False

    class AsyncLive:
        _use_redis = True

        class Client:
            async def ping(self):
                return True

        _client = Client()

    assert await api._redis_transport_live(AsyncLive()) is True

    class SyncLive:
        _use_redis = True

        class Client:
            def ping(self):
                return True

        _client = Client()

    assert await api._redis_transport_live(SyncLive()) is True


async def test_agents_status_reports_in_memory_without_redis():
    assert api.HAS_AGENT_RACK and api.get_tracker is not None
    tracker = api.get_tracker()
    original_bus = tracker.redis_bus

    class FallbackBus:
        _use_redis = False
        _client = None

    tracker.redis_bus = FallbackBus()
    try:
        resp = await api.api_agents_status()
    finally:
        tracker.redis_bus = original_bus
    assert resp["source"] == "in_memory"
    assert resp["count"] == len(resp["agents"])
    assert resp["count"] >= 12


async def test_agents_status_reports_redis_bus_when_ping_ok():
    assert api.HAS_AGENT_RACK and api.get_tracker is not None
    tracker = api.get_tracker()
    original_bus = tracker.redis_bus

    class LiveBus:
        _use_redis = True

        class Client:
            async def ping(self):
                return True

        _client = Client()

    tracker.redis_bus = LiveBus()
    try:
        resp = await api.api_agents_status()
    finally:
        tracker.redis_bus = original_bus
    assert resp["source"] == "redis_bus"
