"""B-3 — AutonomousVerifier deterministik kaynak kapısı.

Kural: LLM bir iddiayı ancak döndürdüğü evidence_url GERÇEKTEN o istemde
getirilmiş arama sonuçlarından biriyse kesin statüye (DOĞRULANDI/YALAN/ÇELİŞKİLİ)
bağlayabilir. Hallusine edilmiş URL, eksik URL veya tanınmayan statü → BİLİNMİYOR.
Ayrıca raporun epistemik damgası hiçbir yolda VERIFIED'a çıkmaz (en yüksek
INTERPRETED) — `status` alanındaki "VERIFIED" süreç kararıdır, damga değil.
"""
import pytest

from agent_core.agents.autonomous_verifier import AutonomousVerifier
from agent_core.schemas.epistemic import EpistemicStatus


class _Result:
    def __init__(self, url, content="snippet"):
        self.source_url = url
        self.content = content


class _Outcome:
    def __init__(self, results):
        self.available = True
        self.results = results


class _Search:
    tavily_key = "k"
    serpapi_key = None
    exa_key = None

    def __init__(self, results):
        self._results = results

    async def search(self, query, num_results=2):
        return _Outcome(self._results)


class _Gateway:
    """İki kademeli chain'i taklit eder: claim çıkarımı + tek-iddia sınıflandırma."""

    def __init__(self, claims, verify_payloads):
        self._claims = claims
        self._verify_payloads = list(verify_payloads)

    async def query_json_chain(self, prompt, schema, **kwargs):
        agent = kwargs.get("agent_name", "")
        if agent == "autonomous_verifier_extract":
            return schema(claims=[{"claim_text": c} for c in self._claims])
        payload = self._verify_payloads.pop(0)
        return schema(**payload)


def _input():
    return {"target_profile": {"bio": "X Üniversitesi'nde okudu", "name": "Deniz"}}


@pytest.mark.asyncio
async def test_conclusive_status_survives_only_with_fetched_url():
    """LLM DOĞRULANDI + getirilmiş URL -> statü korunur; rapor INTERPRETED damgalı."""
    url = "https://ornek.edu/mezunlar/deniz"
    verifier = AutonomousVerifier(search_engine=_Search([_Result(url)]))
    gw = _Gateway(
        claims=["X Üniversitesi mezunu"],
        verify_payloads=[{
            "claim_text": "X Üniversitesi mezunu",
            "truth_status": "DOĞRULANDI",
            "evidence_url": url,
        }],
    )
    report = await verifier.execute(_input(), None, gw)
    assert report.verifications[0].truth_status == "DOĞRULANDI"
    assert report.status == "VERIFIED"  # süreç kararı
    assert report.epistemic == EpistemicStatus.INTERPRETED  # damga VERIFIED'a çıkamaz
    assert report.evidence_refs == [url]


@pytest.mark.asyncio
async def test_hallucinated_url_demotes_conclusive_status():
    """LLM DOĞRULANDI ama URL getirilmiş set'te yok -> BİLİNMİYOR (kanıt uydurulamaz)."""
    verifier = AutonomousVerifier(search_engine=_Search([_Result("https://gercek.com/a")]))
    gw = _Gateway(
        claims=["X Üniversitesi mezunu"],
        verify_payloads=[{
            "claim_text": "X Üniversitesi mezunu",
            "truth_status": "DOĞRULANDI",
            "evidence_url": "https://llm-uydurdu.com/sahte",
        }],
    )
    report = await verifier.execute(_input(), None, gw)
    v = report.verifications[0]
    assert v.truth_status == "BİLİNMİYOR"
    assert v.evidence_url == ""  # hallusine URL zincire girmez
    assert "deterministik kaynak kapısı" in v.contradiction_detail
    assert report.status == "UNVERIFIED"
    assert report.overall_authenticity_score == 0.0
    assert report.evidence_refs == []


@pytest.mark.asyncio
async def test_falsification_also_requires_fetched_url():
    """Kapı simetrik: YALAN damgası bile kaynaksız basılamaz
    (yalanlama yönünde de kanıt uydurulmasın)."""
    verifier = AutonomousVerifier(search_engine=_Search([_Result("https://gercek.com/a")]))
    gw = _Gateway(
        claims=["X Üniversitesi mezunu"],
        verify_payloads=[{
            "claim_text": "X Üniversitesi mezunu",
            "truth_status": "YALAN",
            "evidence_url": "",  # kaynak yok
        }],
    )
    report = await verifier.execute(_input(), None, gw)
    assert report.verifications[0].truth_status == "BİLİNMİYOR"
    assert report.status == "UNVERIFIED"


@pytest.mark.asyncio
async def test_unknown_truth_status_is_demoted():
    """İzinli dört statü dışındaki herhangi bir model çıktısı güvenli tarafa düşer."""
    url = "https://ornek.edu/mezunlar/deniz"
    verifier = AutonomousVerifier(search_engine=_Search([_Result(url)]))
    gw = _Gateway(
        claims=["X Üniversitesi mezunu"],
        verify_payloads=[{
            "claim_text": "X Üniversitesi mezunu",
            "truth_status": "KESİNLİKLE DOĞRU",  # izinli set dışı
            "evidence_url": url,
        }],
    )
    report = await verifier.execute(_input(), None, gw)
    assert report.verifications[0].truth_status == "BİLİNMİYOR"


@pytest.mark.asyncio
async def test_fail_closed_paths_stamp_unavailable():
    """Tüm erken-çıkış yolları epistemik UNAVAILABLE damgalı doğar."""
    v = AutonomousVerifier(search_engine=_Search([]))
    # bio yok
    r1 = await v.execute({"target_profile": {}}, None, None)
    assert r1.epistemic == EpistemicStatus.UNAVAILABLE
    # sağlayıcı anahtarı yok (hepsi None olmalı — kapı üçünü de OR'lar)
    class _NoKeys:
        tavily_key = None
        serpapi_key = None
        exa_key = None

        async def search(self, query, num_results=2):  # çağrılmamalı
            raise AssertionError("sağlayıcı yokken arama yapılmamalı")

    r2 = await v.__class__(search_engine=_NoKeys()).execute(_input(), None, None)
    assert r2.epistemic == EpistemicStatus.UNAVAILABLE
    assert r2.fallback_reason == "no_search_provider"
    # LLM hiç iddia çıkaramadı
    r3 = await v.execute(_input(), None, _Gateway(claims=[], verify_payloads=[]))
    assert r3.epistemic == EpistemicStatus.UNAVAILABLE
