"""Deterministic evidence collection for the human-behaviour analysis agent.

The LLM is only given observations produced here; it is not used to invent
visual or temporal evidence.  The module deliberately describes signals as
observations rather than diagnoses.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

import cv2
import httpx
import numpy as np
from pydantic import BaseModel, ConfigDict, Field
from urllib.parse import urlparse


class MicroSignal(BaseModel):
    """A single deterministic micro-observation.  Not a diagnosis."""
    signal_type: str  # tension, contradiction, void, authentic, defense, insomnia_isolation
    confidence: float = Field(ge=0.0, le=1.0)
    location: str  # image_bg / shoulder_region / text_subtext / temporal / linguistic
    evidence: str
    psychological_weight: float  # Aşil Tendonu ağırlığı; legacy integrations may use 0-100 scale


class DigitalColdReading(BaseModel):
    surface_identity: str
    detected_wound: str
    defense_mechanism: str
    micro_signals: List[MicroSignal]
    achilles_score: float = Field(ge=0.0, le=100.0)
    resonance_potential: float = Field(ge=0.0, le=1.0)

    model_config = ConfigDict(extra="forbid")


class HumanBehaviorAnalyzer:
    """
    Dijital Cold Reading & Mikro-Analiz Ajanı
    Görev: Görünenin altını kazımak, boşlukları okumak
    """

    MAX_IMAGES = 3
    MAX_IMAGE_BYTES = 10 * 1024 * 1024

    # ------------------------------------------------------------------ #
    # Public entrypoint
    # ------------------------------------------------------------------ #
    async def execute(
        self, input_data: Dict[str, Any], memory: Any, llm_gateway: Any
    ) -> DigitalColdReading:
        profile = input_data.get("target_profile") or {}
        sacred_rules = input_data.get("sacred_rules", "")

        bio = self._as_text(profile.get("bio", ""))
        posts = [self._as_text(p) for p in (profile.get("posts") or [])]
        post_times = profile.get("post_times") or []
        images = profile.get("images") or []

        # 1. Temporal forensics
        temporal_signals = self._temporal_forensics(post_times)

        # 2. Text / linguistic forensics
        text_data = self._linguistic_forensics(bio, posts)
        text_signals = text_data["signals"]

        # 3. Visual micro-analysis (remote URLs only; capped)
        visual_signals: List[MicroSignal] = []

        try:
            async with httpx.AsyncClient(
                follow_redirects=True,
                timeout=httpx.Timeout(10.0, connect=5.0),
            ) as client:
                for image_url in images[: self.MAX_IMAGES]:
                    if not self._is_http_url(image_url):
                        continue
                    try:
                        response = await client.get(image_url)
                        response.raise_for_status()
                        if len(response.content) > self.MAX_IMAGE_BYTES:
                            logging.warning("Skipping oversized image: %s", image_url)
                            continue
                        arr = np.frombuffer(response.content, dtype=np.uint8)
                        image = cv2.imdecode(arr, cv2.IMREAD_COLOR)
                        if image is not None:
                            visual_signals.extend(self._analyze_visual_micro_img(image))
                    except (httpx.HTTPError, ValueError) as exc:
                        logging.warning("Visual analysis failed for %s: %s", image_url, exc)
        except httpx.HTTPError as exc:
            logging.warning("Unable to initialize visual analysis client: %s", exc)

        # 4. Combine and mine contradictions
        all_signals = temporal_signals + text_signals + visual_signals
        contradictions = self._mine_contradictions(visual_signals, text_data)

        hard_data = {
            "signals": [s.model_dump() for s in all_signals],
            "contradictions": contradictions,
        }

        # 5. Construct the observation-only prompt (no invented evidence)
        prompt = (
            "Sen 'Human Behavior Analyzer' ajanısın. Görevin hedefin görünen kimliğinin altını kazımak "
            "ve çelişkilerini bulmak.\n"
            "Yalnızca verilen gözlemlere dayan; gözlemleri klinik tanı veya kesin kişilik yargısı "
            "gibi sunma.\n\n"
            f"Hedef Profili:\nBio: {bio}\nTweetler: {posts}\n\n"
            "GERÇEK METRİKLER (OpenCV ve Linguistic Analiz Sonuçları):\n"
            f"{json.dumps(hard_data, ensure_ascii=False, indent=2)}\n\n"
            f"{sacred_rules}\n\n"
            "Bu verileri analiz et, mikro sinyalleri yakala ve Aşil tendonunu (hassas noktasını) "
            "tespit et. Beklenen formata (JSON) uygun cevap ver. "
            "Bu kanıtları temkinli biçimde özetle ve beklenen JSON formatında cevap ver."
        )

        return await llm_gateway.query_json(prompt, DigitalColdReading)

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    @staticmethod
    def _as_text(value: Any) -> str:
        return value if isinstance(value, str) else str(value)

    @staticmethod
    def _is_http_url(value: Any) -> bool:
        if not isinstance(value, str):
            return False
        parsed = urlparse(value)
        return parsed.scheme in {"http", "https"} and bool(parsed.netloc)

    # ------------------------------------------------------------------ #
    # Visual forensics
    # ------------------------------------------------------------------ #
    def _analyze_visual_micro(self, images: List[str]) -> List[MicroSignal]:
        """Analyze local image paths (kept for callers and offline tests)."""
        signals: List[MicroSignal] = []
        for image_path in images or []:
            image = cv2.imread(image_path)
            if image is not None:
                signals.extend(self._analyze_visual_micro_img(image))
        return signals

    def _analyze_visual_micro_img(self, img: np.ndarray) -> List[MicroSignal]:
        signals: List[MicroSignal] = []
        if img is None or img.size == 0 or len(img.shape) < 2:
            return signals

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        height, width = img.shape[:2]

        # Shoulder tension / edge density (kas gerginliği)
        shoulder_roi = img[
            int(height * 0.3) : int(height * 0.6), int(width * 0.2) : int(width * 0.8)
        ]
        if shoulder_roi.size > 0:
            edges = cv2.Canny(shoulder_roi, 100, 200)
            tension_level = float(np.mean(edges))
            if tension_level > 50:
                signals.append(
                    MicroSignal(
                        signal_type="tension",
                        confidence=min(tension_level / 100.0, 1.0),
                        location="shoulder_region",
                        evidence=f"Omuz bölgesi kenar yoğunluğu (tension): {tension_level:.2f}",
                        psychological_weight=0.7,
                    )
                )

        # Background blur / intentional obscurity (void)
        laplacian_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        if laplacian_var < 100:
            signals.append(
                MicroSignal(
                    signal_type="void",
                    confidence=0.8,
                    location="background_blur",
                    evidence=f"Görüntü netliği düşük (Laplacian varyansı: {laplacian_var:.1f})",
                    psychological_weight=0.6,
                )
            )

        return signals

    # ------------------------------------------------------------------ #
    # Linguistic forensics
    # ------------------------------------------------------------------ #
    def _linguistic_forensics(self, bio: str, posts: List[str]) -> Dict[str, Any]:
        full_text = f"{bio} {' '.join(posts)}"
        signals: List[MicroSignal] = []

        # Emoji density (duyusal ifade ihtiyacı / subtext)
        emoji_count = sum(1 for char in full_text if ord(char) > 127000)
        if full_text and emoji_count > len(full_text) * 0.05:
            signals.append(
                MicroSignal(
                    signal_type="authentic",
                    confidence=0.75,
                    location="emoji_density",
                    evidence=f"Yüksek emoji kullanımı: {emoji_count}",
                    psychological_weight=0.5,
                )
            )

        # Passive voice markers (kontrol kaybı / ötekileştirme)
        passive_markers = ("oldu", "edildi", "yapıldı", "gerekiyor")
        passive_count = sum(full_text.lower().count(m) for m in passive_markers)
        if passive_count > 3:
            signals.append(
                MicroSignal(
                    signal_type="contradiction",
                    confidence=0.8,
                    location="passive_voice",
                    evidence=f"Pasif kipi kullanım: {passive_count}",
                    psychological_weight=0.85,
                )
            )

        # Defense / boundary-drawing ("sadece")
        if "sadece" in full_text.lower():
            signals.append(
                MicroSignal(
                    signal_type="defense",
                    confidence=0.9,
                    location="linguistic",
                    evidence="'Sadece' kelimesi tespiti - sınır çizme/savunma",
                    psychological_weight=0.8,
                )
            )

        return {
            "signals": signals,
            "claimed_identity": self._extract_claimed_identity(bio),
        }

    # ------------------------------------------------------------------ #
    # Temporal forensics
    # ------------------------------------------------------------------ #
    def _temporal_forensics(self, post_times: List[str]) -> List[MicroSignal]:
        signals: List[MicroSignal] = []
        late_night_count = 0
        total_valid = 0

        for value in post_times or []:
            try:
                hour = int(str(value).strip().split(":", 1)[0])
                if 0 <= hour <= 23:
                    total_valid += 1
                    if hour >= 23 or hour <= 4:
                        late_night_count += 1
            except (TypeError, ValueError):
                continue

        if total_valid > 0:
            ratio = late_night_count / total_valid
            if ratio > 0.3:
                signals.append(
                    MicroSignal(
                        signal_type="insomnia_isolation",
                        confidence=min(ratio, 1.0),
                        location="temporal_post_distribution",
                        evidence=f"Gece (23:00-04:00) paylaşım oranı: %{ratio*100:.1f}",
                        psychological_weight=0.75,
                    )
                )

        return signals

    # ------------------------------------------------------------------ #
    # Contradiction mining
    # ------------------------------------------------------------------ #
    def _mine_contradictions(
        self, visual_signals: List[MicroSignal], text_signals: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        contradictions: List[Dict[str, Any]] = []
        signals = text_signals.get("signals", [])

        has_tension_or_void = any(
            s.signal_type in ("tension", "void") for s in visual_signals
        )
        has_positive_claim = any(
            s.signal_type in ("authentic", "defense") for s in signals
        )

        if has_tension_or_void and has_positive_claim:
            contradictions.append(
                {
                    "type": "visual_linguistic_mismatch",
                    "evidence": "Görsel sinyaller ile metinsel sunum arasında fark gözlendi",
                    "severity": 0.85,
                }
            )

        for s in signals:
            if s.signal_type == "contradiction":
                contradictions.append(
                    {
                        "type": "linguistic_contradiction",
                        "evidence": s.evidence,
                        "severity": s.psychological_weight,
                    }
                )

        return contradictions

    # ------------------------------------------------------------------ #
    # Identity / wound / resonance (bridge methods, not direct LLM input)
    # ------------------------------------------------------------------ #
    def _extract_claimed_identity(self, bio: str) -> str:
        if not bio:
            return "Unknown Identity"
        first_line = bio.split(".")[0].strip()
        return first_line[:60] or "Unknown Identity"

    def _calculate_achilles(
        self, contradictions: List[Dict], text_signals: Dict[str, Any]
    ) -> float:
        base_score = len(contradictions) * 15
        for signal in text_signals.get("signals", []):
            base_score += signal.psychological_weight * 10
        return min(base_score, 100.0)

    def _identify_wound_as_bridge(
        self, contradictions: List[Dict], text_signals: Dict[str, Any]
    ) -> Dict[str, Any]:
        if not contradictions:
            return {"type": "unknown", "defense": "unknown", "approach": "generic"}

        def sort_key(item: Dict) -> float:
            return item.get("severity", item.get("weight", 0))

        primary = max(contradictions, key=sort_key)
        wound_types = {
            "visual_linguistic_mismatch": {
                "type": "yalnizlik_köprüsü",
                "defense": "kalabalik_maskesi",
                "approach": "bosluk_rezonansi",
            },
            "linguistic_contradiction": {
                "type": "bagimsizlik_celiskisi",
                "defense": "kontrol_mekanizmasi",
                "approach": "guven_insaati",
            },
            "social_vs_alone": {
                "type": "yalnizlik_köprüsü",
                "defense": "kalabalik_maskesi",
                "approach": "bosluk_rezonansi",
            },
            "independent_vs_needy": {
                "type": "bagimsizlik_celiskisi",
                "defense": "kontrol_mekanizmasi",
                "approach": "guven_insaati",
            },
            "happy_vs_tired": {
                "type": "tukenmislik_yarasi",
                "defense": "pozitif_maske",
                "approach": "izin_verme_alani",
            },
        }
        return wound_types.get(
            primary.get("type"), {"type": "tukenmislik_yarasi", "defense": "pozitif_maske", "approach": "izin_verme_alani"}
        )

    def _calculate_resonance_potential(
        self, wound: Dict[str, Any], input_data: Dict[str, Any]
    ) -> float:
        authenticity = min(
            max(float(input_data.get("user_authenticity_score", 0.5)), 0.0), 1.0
        )
        defense_strength = float(wound.get("defense_strength", 0.5))
        openness = 1.0 - min(max(defense_strength, 0.0), 1.0)
        return float((authenticity * openness) ** 0.5)
