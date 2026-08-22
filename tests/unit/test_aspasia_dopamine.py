import pytest
import random
from agent_core.aspasia.dopamine_engine import DopamineEngine, DopamineProfile, RewardSchedule

@pytest.fixture
def engine():
    return DopamineEngine()

def test_analyze_addiction_profile_validation_heavy(engine):
    # Text heavy on validation markers
    target_data = {
        'posts': ['Lütfen beğeni atın', 'Yorum bekliyorum', 'Sizce nasıl görünüyor, fikriniz nedir?']
    }
    profile = engine.analyze_addiction_profile(target_data)
    assert isinstance(profile, DopamineProfile)
    assert profile.validation_need > 0.1
    # Check that chase_sensitivity or novelty_seeking doesn't blow up
    assert 0.0 <= profile.chase_sensitivity <= 1.0

def test_analyze_addiction_profile_chase_heavy(engine):
    target_data = {
        'posts': ['Asla pes etmem', 'Bir daha denemeliyim', 'son bir kez deneyeceğim, devam etmeliyim']
    }
    profile = engine.analyze_addiction_profile(target_data)
    assert profile.chase_sensitivity > 0.5
    assert profile.loss_chasing is False  # 'kaybettim' vb. yok

def test_generate_interaction_sequence(engine):
    profile = DopamineProfile(
        validation_need=0.8,
        novelty_seeking=0.5,
        uncertainty_tolerance=0.5,
        chase_sensitivity=0.8,
        loss_chasing=True,
        near_miss_sensitivity=0.7,
        optimal_reward=RewardSchedule.VARIABLE_RATIO,
        optimal_interval=300
    )
    
    # Fix the random seed to ensure determinism in tests
    random.seed(42)
    sequence = engine.generate_interaction_sequence(profile, message_count=5)
    
    assert len(sequence) == 5
    for msg in sequence:
        assert 'type' in msg
        assert msg['type'] in ['jackpot', 'near_miss', 'loss']
        assert 'content' in msg
        assert 'delay_after' in msg
        assert 'dopamine_spike' in msg
        
    # Reset random seed
    random.seed()

def test_should_reward_fixed_ratio(engine):
    profile = DopamineProfile(
        validation_need=0.5,
        novelty_seeking=0.5,
        uncertainty_tolerance=0.5,
        chase_sensitivity=0.5,
        loss_chasing=False,
        near_miss_sensitivity=0.4,
        optimal_reward=RewardSchedule.FIXED_RATIO,
        optimal_interval=300
    )
    
    assert engine._should_reward(profile, 0) is True  # 0 % 4 == 0
    assert engine._should_reward(profile, 1) is False
    assert engine._should_reward(profile, 4) is True

def test_estimate_dopamine(engine):
    profile = DopamineProfile(
        validation_need=1.0,
        novelty_seeking=0.5,
        uncertainty_tolerance=0.5,
        chase_sensitivity=1.0,
        loss_chasing=False,
        near_miss_sensitivity=0.4,
        optimal_reward=RewardSchedule.FIXED_RATIO,
        optimal_interval=300
    )
    
    spike_jackpot = engine._estimate_dopamine('jackpot', profile)
    spike_near = engine._estimate_dopamine('near_miss', profile)
    spike_loss = engine._estimate_dopamine('loss', profile)
    
    assert spike_jackpot > spike_near > spike_loss
