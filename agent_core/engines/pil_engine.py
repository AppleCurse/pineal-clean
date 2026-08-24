
import spacy
from typing import List

class PIL_Engine:
    def __init__(self, model_name: str = "en_core_web_sm"):
        try:
            self.nlp_processor = spacy.load(model_name)
        except OSError:
            self.nlp_processor = None

    def analyze_and_synthesize(self, target_text: str, desired_state: str) -> str:
        if not self.nlp_processor:
            return f"Hedef durum: {desired_state} (SpaCy modeli yüklenmedi)"
        doc = self.nlp_processor(target_text)
        detected_triggers = self._detect_triggers(doc)
        entities = [ent.text for ent in doc.ents]
        return f"stek işlendi. Tetikleyiciler: {detected_triggers}. Hedef: {desired_state} - Varlıklar: {entities}"

    def _detect_triggers(self, doc) -> List[str]:
        triggers = []
        for token in doc:
            if token.lower_ in ["no", "not", "but", "however", "can't", "won't"]:
                triggers.append("resistance")
        return triggers

