import pytest
from unittest.mock import MagicMock, patch
from agent_core.aspasia.integrated_strategy import IntegratedStrategyEngine, SuperStrategy, generate_strategy_for_rust
from agent_core.aspasia.psychological_profiler import PsychologicalProfile, AttachmentStyle
from agent_core.aspasia.dopamine_engine import DopamineProfile, RewardSchedule
from agent_core.services.llm_gateway import LLMGateway

@pytest.fixture
def engine():
    return IntegratedStrategyEngine()

@pytest.fixture
def mock_profiles():
    psych = PsychologicalProfile(
        attachment=AttachmentStyle.ANXIOUS,
        core_wound='abandonment', fear='Terk edilme', emotional_need='Güvenlik',
        dark_triad={'machiavellianism': 0.1, 'narcissism': 0.8, 'psychopathy': 0.1},
        exploitability=0.9, attention_seeking=0.8, validation_frequency=0.2
    )
    dop = DopamineProfile(
        validation_need=0.9, novelty_seeking=0.8, uncertainty_tolerance=0.2,
        chase_sensitivity=0.9, loss_chasing=True, near_miss_sensitivity=0.8,
        optimal_reward=RewardSchedule.VARIABLE_RATIO, optimal_interval=60
    )
    return psych, dop

def test_analyze_and_synthesize_full_flow(engine):
    strategy = engine.analyze_and_synthesize({'posts': ['Lütfen beğeni atın', 'Yorum bekliyorum', 'terk edildim', 'yalnızım']})
    assert isinstance(strategy, SuperStrategy)
    assert strategy.psychological is not None
    assert strategy.dopamine is not None
    assert len(strategy.message_sequence) == 10
    phases = [msg['phase'] for msg in strategy.message_sequence]
    assert 'wound_hook' in phases
    assert 'variable_reward_2' in phases
    assert 'open_loop' in phases
    assert 'maintenance_6' in phases

def test_calculate_addiction_risk(engine, mock_profiles):
    psych, dop = mock_profiles
    risk = engine._calculate_addiction_risk(psych, dop)
    assert risk > 0.8
    assert engine._assess_risk(risk) == "addictive"
    assert "Etik sınırları aşıyor" in engine._generate_warning(risk)

def test_craft_wound_hook_fallback(engine, mock_profiles):
    psych, dop = mock_profiles
    hook = engine._craft_wound_hook(psych, dop, llm_gateway=None)
    assert len(hook) > 0
    assert "Bir daha denemeliyim" in hook

def test_craft_wound_hook_llm_success(engine, mock_profiles):
    psych, dop = mock_profiles
    mock_llm = MagicMock(spec=LLMGateway)
    mock_llm.query = MagicMock(return_value="Yalnızlığını anlıyorum.")
    with patch('asyncio.get_event_loop') as mock_loop:
        mock_loop_instance = MagicMock()
        mock_loop_instance.is_running.return_value = False
        mock_loop_instance.run_until_complete.return_value = "Yalnızlığını anlıyorum."
        mock_loop.return_value = mock_loop_instance
        hook = engine._craft_wound_hook(psych, dop, llm_gateway=mock_llm)
        assert "Yalnızlığını anlıyorum." in hook
        assert "Bir daha denemeliyim" in hook

def test_craft_wound_hook_llm_exception_fallback(engine, mock_profiles):
    psych, dop = mock_profiles
    mock_llm = MagicMock(spec=LLMGateway)
    with patch('asyncio.get_event_loop') as mock_loop:
        mock_loop_instance = MagicMock()
        mock_loop_instance.is_running.return_value = False
        mock_loop_instance.run_until_complete.side_effect = Exception("Network Error")
        mock_loop.return_value = mock_loop_instance
        hook = engine._craft_wound_hook(psych, dop, llm_gateway=mock_llm)
        assert len(hook) > 0
        assert "Bir daha denemeliyim" in hook

def test_generate_strategy_for_rust():
    result = generate_strategy_for_rust({'posts': ['harikayım']})
    assert 'psychological_profile' in result
    assert 'dopamine_profile' in result
    assert 'strategy' in result
    assert 'warning' in result
    assert isinstance(result['strategy']['sequence'], list)
    assert len(result['strategy']['sequence']) == 10
