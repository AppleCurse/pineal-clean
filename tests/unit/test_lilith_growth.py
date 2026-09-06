import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from agent_core.agents.lilith_growth import (
    FreeTextGateway,
    LilithContentPackage,
    LilithGrowthAgent,
    NeurochemicalProfile,
    NeuroMetrics,
    OpenAICompatibleGateway,
)


# --------------------------------------------------------------------------- #
# Mevcut Uçtan Uca Testler
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
async def test_lilith_growth_agent_execution():
    mock_gateway = MagicMock()
    mock_response = MagicMock()
    mock_choice = MagicMock()
    mock_message = MagicMock()

    mock_json = """{
      "hook": "Çoğu insan başarısızlıktan değil, parlamaktan korkar.",
      "psychological_angle": "Görünürlük kaygısı ve statü tehdidi",
      "content_body": "Gölgede kalmak konforludur. Ortaya çıktığınızda herkes sizi hedef alır.",
      "call_to_action": "Bu konfor alanını ne zaman terk edeceksiniz?",
      "pollinations_image_prompt": "cinematic dark moody photography of a silhouetted figure in spotlight",
      "confidence": 0.95
    }"""
    mock_message.content = mock_json
    mock_choice.message = mock_message
    mock_response.choices = [mock_choice]
    mock_gateway.chat = AsyncMock(return_value=mock_response)

    agent = LilithGrowthAgent(llm_gateway=mock_gateway)

    payload = {
        "topic": "Görünürlük Korkusu",
        "platform": "x_twitter",
        "friction_profile": {
            "sensitivities": ["yargılanma korkusu"],
            "stress_triggers": ["aşırı dikkat çekme"],
        },
        "passion_profile": {
            "core_passions": ["özgünlük"],
            "energizing_topics": ["felsefe"],
        },
        "cognitive_style": {"communication_tone": "keskin"},
    }

    result = await agent.execute(payload)

    assert isinstance(result, LilithContentPackage)
    assert result.hook == "Çoğu insan başarısızlıktan değil, parlamaktan korkar."
    assert result.platform == "x_twitter"
    assert "https://image.pollinations.ai/prompt/" in result.pollinations_image_url
    assert result.data_confidence is True
    assert result.confidence == 0.95
    assert result.neurochemical_profile is not None
    assert result.neurochemical_profile.dopamine_potential >= 0.05
    assert result.neuro_metrics is not None
    assert 0.0 <= result.neuro_metrics.viral_coefficient_score <= 10.0
    assert result.neuro_metrics.dominant_neurotransmitter in {
        "dopamine", "serotonin", "cortisol", "oxytocin"
    }


@pytest.mark.asyncio
async def test_lilith_growth_agent_fallback_resilience():
    """Hata anında bile nörobilimsel fallback paketinin eksiksiz üretildiğini doğrula."""
    failing_gateway = MagicMock()
    failing_gateway.chat = AsyncMock(side_effect=RuntimeError("LLM Gateway down"))

    agent = LilithGrowthAgent(llm_gateway=failing_gateway)
    pkg = await agent.execute({"topic": "Statü Kaygısı"})

    assert isinstance(pkg, LilithContentPackage)
    assert pkg.confidence == 0.5
    assert pkg.data_confidence is False
    assert "error" in (pkg.fallback_reason or "")
    assert pkg.neurochemical_profile is not None
    assert pkg.neuro_metrics is not None
    assert pkg.neuro_metrics.viral_coefficient_score > 0.0


@pytest.mark.asyncio
async def test_lilith_growth_agent_partial_malformed_llm_fields_do_not_crash():
    """LLM'in tek bir alanı bozuk döndürmesi TÜM üretimi fallback'e düşürmemeli."""
    mock_gateway = MagicMock()
    mock_response = MagicMock()
    mock_choice = MagicMock()
    mock_message = MagicMock()
    mock_message.content = """{
      "hook": "test hook",
      "psychological_angle": "test angle",
      "content_body": "test body",
      "call_to_action": "test cta",
      "pollinations_image_prompt": "test prompt",
      "dopamine": "çok yüksek",
      "cortisol": null,
      "confidence": "yüksek"
    }"""
    mock_choice.message = mock_message
    mock_response.choices = [mock_choice]
    mock_gateway.chat = AsyncMock(return_value=mock_response)

    agent = LilithGrowthAgent(llm_gateway=mock_gateway)
    result = await agent.execute({"topic": "Test"})

    assert isinstance(result, LilithContentPackage)
    assert result.fallback_reason is None  # bozuk alanlar toplam üretimi ÇÖKERTMEMELİ
    assert result.hook == "test hook"
    assert 0.0 <= result.neuro_metrics.viral_coefficient_score <= 10.0


# --------------------------------------------------------------------------- #
# $V_c$ Formülü — Matematiksel Sınır ve Uç-Durum Testleri
# --------------------------------------------------------------------------- #

class TestComputeNeuroFormulaEdgeCases:

    def test_default_values_produce_high_viral_score(self):
        metrics = LilithGrowthAgent.compute_neuro_formula(
            dopamine=0.95, serotonin=0.90, cortisol=0.70, oxytocin=0.60, cognitive_friction=0.20
        )
        assert metrics.viral_coefficient_score > 5.0
        assert metrics.dominant_neurotransmitter == "dopamine"
        assert "nucleus_accumbens" in metrics.target_brain_region

    def test_high_threat_profile_selects_amygdala(self):
        metrics = LilithGrowthAgent.compute_neuro_formula(
            dopamine=0.30, serotonin=0.40, cortisol=0.98, oxytocin=0.20, cognitive_friction=0.50
        )
        assert metrics.dominant_neurotransmitter == "cortisol"
        assert "amygdala" in metrics.target_brain_region

    def test_zero_and_negative_inputs_never_crash(self):
        metrics = LilithGrowthAgent.compute_neuro_formula(
            dopamine=0.0, serotonin=-5.0, cortisol=0.0, oxytocin=-1.0, cognitive_friction=0.0
        )
        assert isinstance(metrics, NeuroMetrics)
        assert 0.5 <= metrics.viral_coefficient_score <= 10.0
        assert 0.0 <= metrics.pattern_interrupt_index <= 1.0
        assert 0.0 <= metrics.cognitive_dissonance_score <= 1.0

    def test_zero_cognitive_friction_never_divides_by_zero(self):
        """cognitive_friction=0.0 -> ZeroDivisionError riski; floor=0.10 ile imkânsız kılınmalı."""
        metrics = LilithGrowthAgent.compute_neuro_formula(cognitive_friction=0.0)
        assert metrics.viral_coefficient_score > 0.0

    def test_nan_and_infinite_inputs_fall_back_to_safe_defaults(self):
        metrics = LilithGrowthAgent.compute_neuro_formula(
            dopamine=float("nan"),
            serotonin=float("inf"),
            cortisol=float("-inf"),
            oxytocin=float("nan"),
            cognitive_friction=float("nan"),
        )
        assert isinstance(metrics, NeuroMetrics)
        assert 0.5 <= metrics.viral_coefficient_score <= 10.0
        assert metrics.dominant_neurotransmitter in {"dopamine", "serotonin", "cortisol", "oxytocin"}

    def test_non_numeric_and_wrong_type_inputs_never_raise(self):
        metrics = LilithGrowthAgent.compute_neuro_formula(
            dopamine="çok yüksek",       # type: ignore[arg-type]
            serotonin=None,               # type: ignore[arg-type]
            cortisol="0.9",
            oxytocin=[1, 2, 3],           # type: ignore[arg-type]
            cognitive_friction="abc",
        )
        assert isinstance(metrics, NeuroMetrics)
        assert 0.5 <= metrics.viral_coefficient_score <= 10.0

    def test_extreme_upper_bound_inputs_are_clamped_to_ten(self):
        metrics = LilithGrowthAgent.compute_neuro_formula(
            dopamine=999.0, serotonin=999.0, cortisol=999.0, oxytocin=999.0,
            cognitive_friction=0.0001,
        )
        assert metrics.viral_coefficient_score <= 10.0

    def test_pydantic_validators_clamp_out_of_range_direct_construction(self):
        """compute_neuro_formula bypass edilip model doğrudan çağrılsa bile kenetleme çalışmalı."""
        chem = NeurochemicalProfile(
            dopamine_potential=5.0,
            serotonin_status_currency=-3.0,
            cortisol_urgency=float("nan"),
            oxytocin_affinity="bozuk",  # type: ignore[arg-type]
        )
        assert 0.0 <= chem.dopamine_potential <= 1.0
        assert 0.0 <= chem.serotonin_status_currency <= 1.0
        assert 0.0 <= chem.cortisol_urgency <= 1.0
        assert 0.0 <= chem.oxytocin_affinity <= 1.0

        metrics = NeuroMetrics(
            viral_coefficient_score=999.0,
            pattern_interrupt_index=-1.0,
            cognitive_dissonance_score=2.0,
            dominant_neurotransmitter="unknown_hormone",
        )
        assert 0.0 <= metrics.viral_coefficient_score <= 10.0
        assert 0.0 <= metrics.pattern_interrupt_index <= 1.0
        assert 0.0 <= metrics.cognitive_dissonance_score <= 1.0
        assert metrics.dominant_neurotransmitter == "dopamine"


# --------------------------------------------------------------------------- #
# Rapor Formatlama — Tek Kaynak Doğrulaması
# --------------------------------------------------------------------------- #

def test_render_console_report_contains_key_sections():
    pkg = LilithContentPackage(
        platform="x_twitter",
        hook="test hook",
        psychological_angle="test angle",
        content_body="test body",
        call_to_action="test cta",
        pollinations_image_prompt="test prompt",
        pollinations_image_url="https://image.pollinations.ai/prompt/test",
        neurochemical_profile=NeurochemicalProfile(),
        neuro_metrics=LilithGrowthAgent.compute_neuro_formula(),
    )
    report = LilithGrowthAgent.render_console_report(pkg)
    assert "BİLİŞSEL KANCA" in report
    assert "BİLEŞİK VİRAL KATSAYI" in report
    assert "test hook" in report
    assert "CANLI ANALİZ" in report


def test_render_console_report_marks_fallback_mode():
    pkg = LilithContentPackage(
        platform="x_twitter",
        hook="fallback hook",
        psychological_angle="-",
        content_body="-",
        call_to_action="-",
        pollinations_image_prompt="-",
        pollinations_image_url="https://image.pollinations.ai/prompt/x",
        fallback_reason="error: boom",
    )
    report = LilithGrowthAgent.render_console_report(pkg)
    assert "NÖRAL BASELINE" in report
    assert "FALLBACK NEDENİ" in report


# --------------------------------------------------------------------------- #
# CLI Gateway Adaptörleri (DRY Doğrulaması)
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
async def test_free_text_gateway_strips_code_fences():
    gateway = FreeTextGateway()
    fake_response = MagicMock()
    fake_response.raise_for_status = MagicMock()
    fake_response.text = '```json\n{"hook": "x"}\n```'

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=fake_response)
        mock_client_cls.return_value.__aenter__.return_value = mock_client
        result = await gateway.chat(messages=[{"role": "user", "content": "hi"}])

    assert result.choices[0].message.content == '{"hook": "x"}'


def test_from_cli_credentials_selects_correct_gateway():
    agent_with_key = LilithGrowthAgent.from_cli_credentials(
        api_key="sk-test", base_url=None, model="gpt-4o"
    )
    assert isinstance(agent_with_key.llm_gateway, OpenAICompatibleGateway)

    agent_without_key = LilithGrowthAgent.from_cli_credentials(
        api_key=None, base_url=None, model="gpt-4o"
    )
    assert isinstance(agent_without_key.llm_gateway, FreeTextGateway)
