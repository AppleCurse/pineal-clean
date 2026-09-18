"""P1-B1: config -> Pydantic sözleşme kilidi.

config/decision_config.yaml içindeki her field_weight gerçek bir Pydantic
model alanını referans etmelidir. Model ile config tekrar ayrışırsa bu
testler AÇIKÇA fail eder (uygulama sessizce yanlış skor üretmez).

Yeni bir ağırlıklı ajan config'e eklenirse AGENT_MODELS mapping'i
güncellenene kadar test kırmızı kalır (test_all_weighted_agents_mapped).
"""

from agent_core.agents.mirror_truth import MirrorReflection
from agent_core.agents.osint_investigator import OsintProfile
from agent_core.config_loader import DecisionConfig
from agent_core.domain.memory_models import PassionProfile
from agent_core.shadow.shadow_executor import ShadowResult

# Ajan adi (config) -> Pydantic cikti modeli
AGENT_MODELS = {
    "passion_mapper": PassionProfile,
    "mirror_truth": MirrorReflection,
    "shadow_executor": ShadowResult,
    "osint_investigator": OsintProfile,
}


def test_all_weighted_agents_have_model_mapping():
    """Config'te ağırlığı olan HER ajanın bir model mapping'i olmalı.

    Aksi halde yeni eklenen ajanlar sözleşme doğrulamasından sessizce kaçar.
    """
    cfg = DecisionConfig.load()
    weighted = {name for name, agent in cfg.agents.items() if agent.field_weights}
    assert weighted == set(AGENT_MODELS), (
        f"Mapping eksik/fazla: weighted={weighted}, mapped={set(AGENT_MODELS)}"
    )


def test_every_config_field_weight_is_a_real_model_field():
    """B1 kapısı: ağırlıklandırılan her alan gerçek Pydantic alanı olmalı."""
    cfg = DecisionConfig.load()
    for agent_name, model in AGENT_MODELS.items():
        agent_cfg = cfg.get_agent_config(agent_name)
        real_fields = set(model.model_fields)
        for field in agent_cfg.field_weights:
            assert field in real_fields, (
                f"{agent_name} ağırlığı {field!r} {model.__name__} modelinde YOK "
                f"(gerçek alanlar: {sorted(real_fields)})"
            )


def test_every_config_weight_set_sums_to_one():
    """B1 kapısı: her ajanın ağırlık toplamı tam 1.0 olmalı."""
    cfg = DecisionConfig.load()
    for agent_name in AGENT_MODELS:
        weights = cfg.get_agent_config(agent_name).field_weights
        total = sum(weights.values())
        assert abs(total - 1.0) < 1e-9, f"{agent_name} ağırlık toplamı {total} != 1.0"


def test_passion_mapper_weights_are_real_passions_fields():
    """passion_mapper ağırlıkları yalnızca PassionProfile alanlarını kullanır."""
    cfg = DecisionConfig.load()
    weights = cfg.get_agent_config("passion_mapper").field_weights
    real = set(PassionProfile.model_fields)
    extra = set(weights) - real
    assert not extra, f"Modelde olmayan ağırlık alanları: {extra}"
    assert set(weights) == {"core_passions", "energizing_topics", "flow_triggers",
                            "evidence_quotes", "sentiment_polarity"}


# ---------------------------------------------------------------------------
# [2026-09-18 C8] Ölü config anahtarı kilidi.
# config_loader.DecisionConfig.load YALNIZCA aşağıdaki anahtarları okur;
# başka bir anahtar YAML'da dursa bile hiçbir davranışı yönetmez (sessiz
# ölü config). require_data_confidence / min_final_confidence / critical /
# fallback_enabled bu sınıftaydı ve kaldırıldı. Yeni anahtar eklemek
# isteyen önce loader'a bağlar, sonra bu kümeyi genişletir.
# ---------------------------------------------------------------------------
import yaml
from pathlib import Path

_CONSUMED_DEFAULT_KEYS = {"min_data_score", "min_llm_confidence", "graceful_degradation"}
_CONSUMED_AGENT_KEYS = _CONSUMED_DEFAULT_KEYS | {"field_weights", "empty_list_penalty"}
_CONSUMED_PIPELINE_KEYS = {"default", "critical_agents"}


def _raw_config() -> dict:
    root = Path(__file__).resolve().parents[2]
    with open(root / "config" / "decision_config.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def test_decision_config_has_no_dead_keys():
    raw = _raw_config()
    assert set(raw) <= {"version", "pipeline", "agents"}, f"bilinmeyen üst anahtar: {set(raw)}"
    pipeline = raw.get("pipeline", {})
    assert set(pipeline) <= _CONSUMED_PIPELINE_KEYS, f"pipeline ölü anahtar: {set(pipeline) - _CONSUMED_PIPELINE_KEYS}"
    dead_default = set(pipeline.get("default", {})) - _CONSUMED_DEFAULT_KEYS
    assert not dead_default, f"pipeline.default ölü anahtar (loader okumuyor): {dead_default}"
    for name, agent in (raw.get("agents") or {}).items():
        dead = set(agent) - _CONSUMED_AGENT_KEYS
        assert not dead, f"agents.{name} ölü anahtar (loader okumuyor): {dead}"


def test_critical_agents_single_source_is_pipeline_list():
    """'critical: true' ajan-içi bayrağı YOK; tek kaynak pipeline.critical_agents.

    mirror_truth eskiden hem listede hem 'critical: true' taşıyordu; ikinci
    bayrak hiçbir yerde okunmuyordu. Listede olduğu sürece davranış aynı.
    """
    cfg = DecisionConfig.load()
    assert "mirror_truth" in cfg.critical_agents
    assert "passion_mapper" in cfg.critical_agents
