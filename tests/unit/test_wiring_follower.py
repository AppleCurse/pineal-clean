"""Wiring W2: follower audit makine-okunur sozlesmesi.

UI eskiden Turkce 'verdict' metnine ('healthy'/'inflated') gore kiyas
yapiyordu -> rozet hep yanlis cikiyordu. Yeni sozlesme: verdict_code.
"""

from agent_core.services.follower_audit import audit_followers


def test_follower_verdict_codes_follow_contract():
    assert audit_followers(0, 0, []).verdict_code == "insufficient"
    assert (
        audit_followers(1000, 50, [{"like_count": None, "comment_count": None}]).verdict_code
        == "insufficient"
    )
    assert (
        audit_followers(1000, 50, [{"like_count": 40, "comment_count": 2}]).verdict_code
        == "healthy"
    )
    assert (
        audit_followers(11000, 900, [{"like_count": 25, "comment_count": 2}]).verdict_code
        == "suspicious"
    )
    assert (
        audit_followers(100000, 5000, [{"like_count": 5, "comment_count": 0}]).verdict_code
        == "inflated"
    )
