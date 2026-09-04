"""Dalga 3 düzeltmelerinin regresyon sözleşmeleri.

[011] VisualEvidence fail-closed defaults
[012] vision prompt'ta numeric confidence yok
[013] doğrulamalı indirme: magic bytes / content-type / boyut / status
[015] provider confidence'a güvenilmez; yerel türetim geçerli
[019] tek OBSERVATION_FRAME
[020] _extract_micro_signal gerçek kanıt döner
[021] peak_hour "--" sentinel'ı sızamaz
[022] GeneratedMessage fail-closed default + LLM yolunda doğrulama işareti
[033] DERINLIK_UYUSMAZLIGI gerçek vektör farkından üretilir
[034] telemetri: varsayımsal tasarruf/sahte ağırlık güncellemesi yok
[036] memory confidence yalnızca ajan çıktılarından
[037] aggressiveness/evidence_th API sözleşmesinden kaldırıldı
"""

import httpx
import pytest

from agent_core.agents.pattern_interrupt import GeneratedMessage, PatternInterrupt
from agent_core.agents.resonance_calculator import ResonanceCalculator
from agent_core.services.canonical_memory import CanonicalMemory
from agent_core.services.vision_analyzer import VisionAnalyzer, VisualEvidence, _sniff_image_mime


# ------------------------------------------------------------------ #
# [011] fail-closed defaults
# ------------------------------------------------------------------ #
def test_visual_evidence_defaults_are_fail_closed():
    ev = VisualEvidence()
    assert ev.confidence == 0.0
    assert ev.data_confidence is False
    assert ev.fallback_reason == "not_analyzed"
    assert ev.image_provenance == []


# ------------------------------------------------------------------ #
# [013] doğrulamalı indirme
# ------------------------------------------------------------------ #
JPG = b"\xff\xd8\xff\xe0" + b"x" * 64
PNG = b"\x89PNG\r\n\x1a\n" + b"y" * 64
HTML = b"<html><body>login wall</body></html>"


def _transport(payload: bytes, content_type: str, status: int = 200):
    def handler(request: httpx.Request) -> httpx.Response:
        headers = {"content-type": content_type} if content_type else {}
        return httpx.Response(status, content=payload, headers=headers)
    return httpx.MockTransport(handler)


async def _download(payload, content_type, status=200):
    va = VisionAnalyzer()
    # Public literal IP makes this network-free MockTransport test independent
    # of DNS while still exercising the production SSRF-pinned request path.
    async with httpx.AsyncClient(transport=_transport(payload, content_type, status)) as client:
        return await va._download_image_record("https://93.184.216.34/img", client=client)


@pytest.mark.asyncio
async def test_download_accepts_real_jpeg():
    rec = await _download(JPG, "image/jpeg")
    assert rec["status"] == "downloaded"
    assert rec["mime"] == "image/jpeg"
    assert rec["sha256"] and rec["bytes"] == len(JPG)
    assert rec.get("b64")


@pytest.mark.asyncio
async def test_download_rejects_html_disguised_as_200():
    """HTTP 200 + text/html -> login duvarı base64 olarak vision'a GİREMEZ."""
    rec = await _download(HTML, "text/html")
    assert rec["status"] == "failed"
    assert rec["reason"] == "content_type_text/html"
    assert "b64" not in rec


@pytest.mark.asyncio
async def test_download_rejects_non_image_bytes_with_image_content_type():
    """Başlık 'image/jpeg' ama gövde HTML -> magic bytes kazanır."""
    rec = await _download(HTML, "image/jpeg")
    assert rec["status"] == "failed"
    assert rec["reason"] == "not_an_image"


@pytest.mark.asyncio
async def test_download_rejects_oversized_body():
    huge = b"\xff\xd8\xff\xe0" + b"z" * (10 * 1024 * 1024 + 1)
    rec = await _download(huge, "image/jpeg")
    assert rec["status"] == "failed"
    assert rec["reason"] == "too_large"


@pytest.mark.asyncio
async def test_download_rejects_non_200():
    rec = await _download(JPG, "image/jpeg", status=403)
    assert rec["status"] == "failed"
    assert rec["reason"] == "http_403"


def test_sniff_mime_covers_real_signatures():
    assert _sniff_image_mime(JPG) == "image/jpeg"
    assert _sniff_image_mime(PNG) == "image/png"
    assert _sniff_image_mime(b"RIFFxxxxWEBP") == "image/webp"
    assert _sniff_image_mime(b"BM\x00\x00") == "image/bmp"
    assert _sniff_image_mime(b"plain text") is None


# ------------------------------------------------------------------ #
# [019]/[020]/[021]/[022] pattern kalıntıları
# ------------------------------------------------------------------ #
def test_single_observation_frame_no_dead_tuple():
    assert isinstance(PatternInterrupt.OBSERVATION_FRAME, str)
    assert not hasattr(PatternInterrupt, "OBSERVATION_FRAMES")


def test_micro_signal_extraction_returns_real_evidence():
    p = PatternInterrupt()
    analysis = {"micro_signals": [
        {"signal_type": "defense", "psychological_weight": 0.4, "evidence": "zayıf sinyal"},
        {"signal_type": "authentic", "psychological_weight": 0.9, "evidence": "'Sadece' kelimesi tespiti"},
    ]}
    out = p._extract_micro_signal(analysis)
    assert out == "'Sadece' kelimesi tespiti", "[020] sabit 'observation' etiketi dönmemeli"
    assert p._extract_micro_signal({}) == "unavailable"


def test_temporal_signal_never_emits_dash_sentinel():
    p = PatternInterrupt()
    # 3+ saat damgası var ama (hypotetik) peak_hour yok ise None
    out = p._extract_temporal_signal({"evidence_timestamps": ["2024-05-01T23:00", "2024-05-02T23:30", "2024-05-03T04:10"]})
    if out is not None:
        assert "--" not in out
    assert p._extract_temporal_signal({"evidence_timestamps": []}) is None


def test_generated_message_fail_closed_defaults():
    msg = GeneratedMessage(message="x", strategy="y", confidence=0.5, compliance_score=100.0, dialogue_tree=[])
    assert msg.data_confidence is False
    assert msg.fallback_reason == "not_verified"


@pytest.mark.asyncio
async def test_llm_path_marks_message_verified():
    class _Gateway:
        async def query_json_chain(self, prompt, schema, **kwargs):
            return GeneratedMessage(
                message="gözleme dayalı", strategy="observation",
                confidence=0.8, compliance_score=100.0, dialogue_tree=[],
                data_confidence=False, fallback_reason="not_verified",
            )

    result = await PatternInterrupt().execute({
        "target_analysis": {"micro_signals": [
            {"signal_type": "defense", "confidence": 0.9, "location": "linguistic",
             "evidence": "'Sadece' kelimesi tespiti", "psychological_weight": 0.8}
        ]},
        "user_mirror": {}, "sacred_rules": "",
    }, None, _Gateway())

    assert result.data_confidence is True, "[022] gerçek LLM sonucu işaretlenmeli"
    assert result.fallback_reason is None


# ------------------------------------------------------------------ #
# [033] rezonans kırmızı bayrakları
# ------------------------------------------------------------------ #
def test_depth_mismatch_flag_is_producible():
    calc = ResonanceCalculator()
    flags = calc._detect_red_flags({"depth": 0.9, "energy": 0.5}, {"depth": 0.2, "energy": 0.5})
    assert "DERINLIK_UYUSMAZLIĞI" in flags, "[033] ölü dal canlandırılmalı"


def test_depth_aligned_vectors_raise_no_depth_flag():
    calc = ResonanceCalculator()
    flags = calc._detect_red_flags({"depth": 0.6, "energy": 0.5}, {"depth": 0.7, "energy": 0.5})
    assert "DERINLIK_UYUSMAZLIĞI" not in flags


def test_energy_flag_still_detectable_with_type_safety():
    calc = ResonanceCalculator()
    flags = calc._detect_red_flags({"depth": 0.5, "energy": 0.2}, {"depth": 0.5, "energy": 0.9})
    assert "ENERJI_UYUSMAZLIĞI" in flags
    # tip güvenliği: string değerler patlamaz, bayrak üretmez
    assert calc._detect_red_flags({"depth": "x"}, {"depth": "y"}) == []


# ------------------------------------------------------------------ #
# [034] telemetri gerçek gözlemlenebilirler
# ------------------------------------------------------------------ #
def test_snapshot_telemetry_has_no_fabricated_metrics():
    from agent_core.task_executor import PinealExecutor
    from agent_core.domain.memory_models import TaskSnapshot
    from datetime import datetime, timezone

    executor = PinealExecutor()
    status = TaskStatus = TaskSnapshot(task_id="fx_t", status="processing", created_at=datetime.now(timezone.utc))
    executor._snapshot(status)
    t = status.telemetry
    assert "saved_llm_cost" not in t, "[034] varsayımsal $/call tasarrufu kaldırılmalı"
    assert "decision_weight_updates" not in t, "[034] sahte ağırlık güncellemesi kaldırılmalı"
    assert "cache_hits" in t and "llm_calls_observed" in t
    assert isinstance(t["llm_spend_usd"], (int, float))


# ------------------------------------------------------------------ #
# [036] memory confidence seyreltilmesi
# ------------------------------------------------------------------ #
@pytest.mark.asyncio
async def test_memory_confidence_not_diluted_by_non_agent_records(tmp_path):
    mem = CanonicalMemory(storage_path=str(tmp_path))
    chain = [
        {"agent": "mirror_truth", "evidence_type": "agent_output",
         "result": {"confidence": 0.9, "x": 1}},
        {"agent": "deep_research", "evidence_type": "verification_note",
         "result": {"note": "doğrulama notu"}},
        {"agent": "pineal_7pillar",
         "result": {"frequency": "insufficient", "elapsed_ms": 5}},
        {"agent": "x", "evidence_type": "execution_failure",
         "result": {"error_code": "Boom"}},
    ]
    await mem.merge_evidence("fxmem", chain)
    stored = mem.get_task_memory("fxmem")
    assert stored["confidence"] == 0.9, "[036] doğrulama notu güveni düşürmemeli"


@pytest.mark.asyncio
async def test_memory_confidence_zero_when_no_agent_evidence(tmp_path):
    mem = CanonicalMemory(storage_path=str(tmp_path))
    await mem.merge_evidence("fxmem2", [
        {"agent": "deep_research", "evidence_type": "verification_note", "result": {"note": "n"}},
    ])
    assert mem.get_task_memory("fxmem2")["confidence"] == 0.0


# ------------------------------------------------------------------ #
# [037] ölü API parametreleri
# ------------------------------------------------------------------ #
def test_initiate_payload_drops_dead_knobs():
    from backend.api import InitiatePayload
    fields = InitiatePayload.model_fields
    assert "aggressiveness" not in fields
    assert "evidence_th" not in fields
    # eski istemciler bu alanları gönderirse sessizce yok sayılır (extra=ignore)
    payload = InitiatePayload(
        client_id="c", url="", rituals="", playlist="", envies="",
        aggressiveness=1.0, evidence_th=3,
    )
    assert payload.client_id == "c"
