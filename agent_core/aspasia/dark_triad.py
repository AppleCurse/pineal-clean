from typing import Dict
from .psychological_profiler import PsychologicalDecomposer

class DarkTriadAnalyzer:
    def __init__(self):
        self.decomposer = PsychologicalDecomposer()

    def analyze(self, target_data: Dict) -> Dict[str, float]:
        text = self.decomposer._extract_text(target_data)
        return self.decomposer._calculate_dark_triad(text)
