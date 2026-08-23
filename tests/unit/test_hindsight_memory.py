"""
HindsightMemory birim testleri.

Canlı LLM/ağ/para çağrısı YOKTUR. sentence-transformers kurulu olmasa bile
çalışır: gerçek embedding modeli yerine sahte (deterministik) embedder
enjekte edilir. Amaç, HindsightMemory'nin CanonicalMemory sözleşmesini
bozmadığını ve anlamsal arama/deduplamanın doğru çalıştığını kilitlemektir.
"""
import math
import tempfile

import pytest

from agent_core.services.canonical_memory import CanonicalMemory
from agent_core.services.hindsight_memory import (
    HindsightMemory,
    build_memory_from_env,
)


def _fake_embedder(monkeypatch):
    """Gerçek model indirmeden, deterministik, kelime-frekansı tabanlı embedder."""

    def _encode(text, convert_to_numpy=True, normalize_embeddings=False):
        low = text.lower()
        vec = [0.0] * 32
        # Alt-dizi eşleşmesi (JSON tırnak/noktalama içerse de çalışır)
        if any(w in low for w in ("muzik", "studio", "prod", "ekipman")):
            vec[0] = 1.0
        if any(w in low for w in ("spor", "kos", "sabah")):
            vec[1] = 1.0
        if vec[0] == 0.0 and vec[1] == 0.0:
            vec[hash(low) % 30 + 2] = 1.0
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        if normalize_embeddings:
            vec = [v / norm for v in vec]
        return vec

    dummy = type("DummyModel", (), {"encode": staticmethod(_encode)})()
    monkeypatch.setattr(HindsightMemory, "_get_embedder", lambda self: dummy)


@pytest.fixture
def memory_service(monkeypatch):
    tmpdir = tempfile.mkdtemp()
    _fake_embedder(monkeypatch)
    mem = HindsightMemory(storage_path=tmpdir, db_path=f"{tmpdir}/hindsight.db")
    yield mem


# ---------------- CanonicalMemory uyumluluğu ----------------

@pytest.mark.asyncio
async def test_hindsight_is_a_canonical_memory(memory_service):
    """HindsightMemory, CanonicalMemory'nin alt sınıfıdır (drop-in uyum)."""
    assert isinstance(memory_service, CanonicalMemory)


@pytest.mark.asyncio
async def test_merge_evidence_still_writes_json(memory_service):
    """Eski JSON tabanlı get_task_memory sözleşmesi bozulmamalı."""
    task_id = "task_compat"
    await memory_service.merge_evidence(task_id, [{"target_authentic_vector": {"depth": 0.8}}])

    data = memory_service.get_task_memory(task_id)
    assert data["evidence"][0]["target_authentic_vector"]["depth"] == 0.8


@pytest.mark.asyncio
async def test_merge_evidence_accumulates(memory_service):
    task_id = "task_acc"
    await memory_service.merge_evidence(task_id, [{"key1": "v1"}])
    await memory_service.merge_evidence(task_id, [{"key2": "v2"}])

    data = memory_service.get_task_memory(task_id)
    assert data["evidence"][0]["key1"] == "v1"
    assert data["evidence"][1]["key2"] == "v2"


@pytest.mark.asyncio
async def test_missing_task_returns_empty(memory_service):
    assert memory_service.get_task_memory("yok") == {}


# ---------------- Anlamsal arama ----------------

@pytest.mark.asyncio
async def test_semantic_search_returns_relevant(memory_service):
    await memory_service.merge_evidence("t1", [
        {"topic": "Muzik produksiyon", "obs": "stüdyo ekipman"},
        {"topic": "Spor", "obs": "sabah kosu"},
    ])

    results = await memory_service.semantic_search("muzik studio", task_id="t1", top_k=2)
    assert len(results) >= 1
    # En alakalı ilk sonuç müzikle ilgili olmalı
    top = results[0]["content"]
    assert "Muzik" in str(top) or "muzik" in str(top).lower()
    assert 0.0 <= results[0]["similarity"] <= 1.0


@pytest.mark.asyncio
async def test_semantic_search_unknown_task_empty(memory_service):
    results = await memory_service.semantic_search("bir şey", task_id="olmayan_task")
    assert results == []


# ---------------- Embedding modeli yokken graceful davranış ----------------

@pytest.mark.asyncio
async def test_semantic_search_without_embedder_returns_empty(monkeypatch):
    """sentence-transformers/numpy yoksa arama hata vermez, boş döner."""
    tmpdir = tempfile.mkdtemp()
    mem = HindsightMemory(storage_path=tmpdir, db_path=f"{tmpdir}/h2.db")
    # Embedding modeli hiç yüklenemesin
    monkeypatch.setattr(mem, "_get_embedder", lambda: None)

    await mem.merge_evidence("t", [{"x": 1}])
    assert await mem.semantic_search("sorgu", task_id="t") == []
    # Ama kanıt JSON'a yine de yazılmış olmalı
    assert mem.get_task_memory("t")["evidence"][0]["x"] == 1


def test_stats_reports_disabled_when_no_embedder(monkeypatch):
    tmpdir = tempfile.mkdtemp()
    mem = HindsightMemory(storage_path=tmpdir, db_path=f"{tmpdir}/h3.db")
    monkeypatch.setattr(mem, "_get_embedder", lambda: None)
    stats = mem.get_stats()
    assert stats["semantic_enabled"] is False
    assert stats["engine"] == "hindsight"


# ---------------- Factory ----------------

def test_factory_defaults_to_canonical(monkeypatch):
    monkeypatch.delenv("PINEAL_MEMORY_ENGINE", raising=False)
    assert isinstance(build_memory_from_env(), CanonicalMemory)


def test_factory_selects_hindsight(monkeypatch, tmp_path):
    monkeypatch.setenv("PINEAL_MEMORY_ENGINE", "hindsight")
    monkeypatch.setenv("PINEAL_MEMORY_PATH", str(tmp_path / "mem"))
    monkeypatch.setenv("PINEAL_MEMORY_DB", str(tmp_path / "mem" / "h.db"))
    mem = build_memory_from_env()
    assert isinstance(mem, HindsightMemory)
